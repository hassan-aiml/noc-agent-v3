"""
ingestion_agent.py
NOC Triage Agent v3 — Ingestion Agent

LangGraph pipeline that:
  1. Validates a raw alarm batch (Stratum or Orion)
  2. Normalizes each alarm to a canonical model
  3. Groups alarms by site_id + zone_id
  4. Aggregates groups into site events within a 15-minute window
  5. Flags isolated single-alarm groups as stray alarms

Canonical equipment types: REMOTE, OPTICAL_MODULE, MAIN_HUB, EXPANSION_HUB, POI
OEM field mapping:
  Stratum: RU->REMOTE, OM->OPTICAL_MODULE, MU->MAIN_HUB, EU->EXPANSION_HUB, IU->POI
  Orion:   RAU->REMOTE, OTRx->OPTICAL_MODULE, MH->MAIN_HUB, EH->EXPANSION_HUB, POI->POI
           fault_description -> alarm_name (Orion-specific field rename)

Severity:
  Stratum: critical / major / minor / warning / info  (5 levels)
  Orion:   critical / major / minor / info            (4 levels — no warning)
  Canonical: critical / major / minor / warning / info
  Orion severity gap: minor is the canonical floor for degraded-but-active alarms.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

# ── Constants ──────────────────────────────────────────────────────────

AGGREGATION_WINDOW_MINUTES = 15

# OEM component name -> canonical equipment type
STRATUM_COMPONENT_MAP: dict[str, str] = {
    "RU": "REMOTE",
    "OM": "OPTICAL_MODULE",
    "MU": "MAIN_HUB",
    "EU": "EXPANSION_HUB",
    "IU": "POI",
}

ORION_COMPONENT_MAP: dict[str, str] = {
    "RAU": "REMOTE",
    "OTRx": "OPTICAL_MODULE",
    "MH": "MAIN_HUB",
    "EH": "EXPANSION_HUB",
    "POI": "POI",
}

# Ordered from longest prefix to shortest to avoid prefix collisions (e.g. OTRx vs OM)
_ORION_PREFIXES: list[tuple[str, str]] = sorted(
    ORION_COMPONENT_MAP.items(), key=lambda kv: -len(kv[0])
)
_STRATUM_PREFIXES: list[tuple[str, str]] = sorted(
    STRATUM_COMPONENT_MAP.items(), key=lambda kv: -len(kv[0])
)

# Severity rank: lower index = higher severity
SEVERITY_ORDER = ["critical", "major", "minor", "warning", "info"]

# Alarm name keyword sets -> canonical alarm category
# Evaluated in order — first match wins.
ALARM_CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["timing reference", "sync loss", "clock loss", "timing ref"], "TDD_SYNC_LOST"),
    (["optical link", "fiber loss", "fiber fault", "optical fail"], "OPTICAL_LINK_FAIL"),
    (
        ["power supply failure", "offline", "communication loss", "hub offline"],
        "ELEMENT_OFFLINE",
    ),
    (["power input", "power fail", "psu fault"], "POWER_FAULT"),
    (["downlink power", "downlink output", "dl power", "dl output"], "DL_POWER_DEGRADED"),
    (["uplink noise", "ul noise", "noise rise"], "UL_NOISE_RISE"),
    (["vswr", "reflected power"], "RF_FAULT"),
    (["overtemp", "temperature", "fan fault"], "THERMAL"),
    (["pim"], "PIM_DETECTED"),
]

# Category dominance order — highest priority first
CATEGORY_PRIORITY = [
    "TDD_SYNC_LOST",
    "ELEMENT_OFFLINE",
    "OPTICAL_LINK_FAIL",
    "POWER_FAULT",
    "DL_POWER_DEGRADED",
    "UL_NOISE_RISE",
    "RF_FAULT",
    "THERMAL",
    "PIM_DETECTED",
    "UNKNOWN",
]

# Alarm name keywords that indicate a degraded-but-active condition (Orion severity gap)
_DEGRADED_KEYWORDS = ["degraded", "low output", "output degraded", "degrad"]


# ── State schema ───────────────────────────────────────────────────────


class IngestionState(TypedDict):
    """LangGraph state shared across all pipeline nodes."""

    raw_alarms: list[dict]
    aggregation_window_minutes: int
    normalized_alarms: list[dict]
    field_mappings_log: list[dict]   # global, deduplicated field mapping records
    severity_gaps_log: list[dict]    # per-alarm severity gap records
    site_events: list[dict]          # final aggregated output
    errors: list[str]


# ── Internal helpers ───────────────────────────────────────────────────


def _classify_alarm(alarm_name: str) -> str:
    """Return canonical alarm category from alarm name."""
    lower = alarm_name.lower()
    for keywords, category in ALARM_CATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return category
    return "UNKNOWN"


def _dominant_severity(severities: list[str]) -> str:
    """Return the highest-priority severity from a list."""
    for sev in SEVERITY_ORDER:
        if sev in severities:
            return sev
    return "info"


def _dominant_category(categories: list[str]) -> str:
    """Return the highest-priority alarm category from a list."""
    for cat in CATEGORY_PRIORITY:
        if cat in categories:
            return cat
    return "UNKNOWN"


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _dedup(items: list[dict]) -> list[dict]:
    """Deduplicate a list of dicts preserving order."""
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        key = str(sorted(item.items()))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _infer_component_type(equip_id: str, prefixes: list[tuple[str, str]]) -> str | None:
    """
    Infer canonical component type from an equipment ID by matching OEM prefixes.
    e.g. "OTRx-3" with Orion prefixes → "OPTICAL_MODULE"
    Returns None if no prefix matches.
    """
    for prefix, canonical in prefixes:
        if equip_id.startswith(prefix):
            return canonical
    return None


def _oem_component_map_entries(oem: str) -> list[dict]:
    """
    Return all known component-type mapping records for an OEM.
    Used to declare the full OEM translation table in field_mappings_resolved
    so downstream agents can rely on it even for component types not seen as
    source_equipment_type in this particular batch.
    """
    if oem == "stratum":
        component_map = STRATUM_COMPONENT_MAP
    elif oem == "orion":
        component_map = ORION_COMPONENT_MAP
    else:
        return []
    return [
        {"oem_field": "source_equipment_type", "oem_value": k, "canonical_value": v}
        for k, v in component_map.items()
    ]


# ── OEM normalizers ────────────────────────────────────────────────────


def _normalize_stratum(
    alarm: dict,
    mappings: list[dict],
    gaps: list[dict],
) -> dict:
    """Normalize a Stratum alarm to the canonical model."""
    raw_eq_type = alarm.get("source_equipment_type", "")
    canonical_eq_type = STRATUM_COMPONENT_MAP.get(raw_eq_type, raw_eq_type)

    if raw_eq_type and raw_eq_type != canonical_eq_type:
        mappings.append(
            {
                "oem_field": "source_equipment_type",
                "oem_value": raw_eq_type,
                "canonical_value": canonical_eq_type,
            }
        )

    alarm_name: str = alarm.get("alarm_name", "")

    return {
        "site_id": alarm["site_id"],
        "site_name": alarm.get("site_name", ""),
        "zone_id": alarm["zone_id"],
        "alarm_name": alarm_name,
        "alarm_code": alarm.get("alarm_code", ""),
        "alarm_category": _classify_alarm(alarm_name),
        "source_equipment_type": canonical_eq_type,
        "source_equipment_id": alarm.get("source_equipment_id", ""),
        "parent_equipment_id": alarm.get("parent_equipment_id"),
        "severity": alarm.get("severity", "info"),
        "timestamp": alarm["timestamp"],
        "das_oem": "stratum",
        "raw_alarm_ref": alarm.get("alarm_id", ""),
    }


def _normalize_orion(
    alarm: dict,
    mappings: list[dict],
    gaps: list[dict],
) -> dict:
    """Normalize an Orion alarm to the canonical model."""
    # Orion uses fault_description instead of alarm_name
    if "fault_description" in alarm:
        alarm_name: str = alarm["fault_description"]
        mappings.append(
            {
                "oem_field": "fault_description",
                "canonical_field": "alarm_name",
            }
        )
    else:
        alarm_name = alarm.get("alarm_name", "")

    raw_eq_type = alarm.get("source_equipment_type", "")
    canonical_eq_type = ORION_COMPONENT_MAP.get(raw_eq_type, raw_eq_type)

    if raw_eq_type and raw_eq_type != canonical_eq_type:
        mappings.append(
            {
                "oem_field": "source_equipment_type",
                "oem_value": raw_eq_type,
                "canonical_value": canonical_eq_type,
            }
        )

    severity: str = alarm.get("severity", "info")

    # Severity gap: Orion has no warning level.
    # Flag minor alarms that represent degraded-but-active conditions.
    if severity == "minor" and any(kw in alarm_name.lower() for kw in _DEGRADED_KEYWORDS):
        gaps.append(
            {
                "oem": "orion",
                "missing_severity": "warning",
                "alarm_id": alarm.get("alarm_id", ""),
                "arrived_as": "minor",
                "canonical_severity": "minor",
                "note": (
                    "Orion has no warning level. "
                    "Minor is canonical floor for degraded-but-active alarms."
                ),
            }
        )

    return {
        "site_id": alarm["site_id"],
        "site_name": alarm.get("site_name", ""),
        "zone_id": alarm["zone_id"],
        "alarm_name": alarm_name,
        "alarm_code": alarm.get("alarm_code", ""),
        "alarm_category": _classify_alarm(alarm_name),
        "source_equipment_type": canonical_eq_type,
        "source_equipment_id": alarm.get("source_equipment_id", ""),
        "parent_equipment_id": alarm.get("parent_equipment_id"),
        "severity": severity,
        "timestamp": alarm["timestamp"],
        "das_oem": "orion",
        "raw_alarm_ref": alarm.get("alarm_id", ""),
    }


# ── LangGraph nodes ────────────────────────────────────────────────────


def validate_batch(state: IngestionState) -> IngestionState:
    """
    Node 1 — Validate raw alarm batch.
    Logs errors for malformed alarms but does not abort the pipeline;
    invalid alarms are skipped during normalization.
    """
    errors: list[str] = []
    required = ("site_id", "zone_id", "das_oem", "timestamp")

    for i, alarm in enumerate(state["raw_alarms"]):
        alarm_ref = alarm.get("alarm_id", f"index[{i}]")
        for field in required:
            if field not in alarm or alarm[field] is None:
                errors.append(f"Alarm {alarm_ref} missing required field: {field}")

        oem = str(alarm.get("das_oem", "")).lower()
        if oem not in ("stratum", "orion") and not errors:
            errors.append(
                f"Alarm {alarm_ref} has unknown das_oem={alarm.get('das_oem')!r}; "
                "will attempt pass-through normalization."
            )

    return {**state, "errors": errors}


def normalize_alarms(state: IngestionState) -> IngestionState:
    """
    Node 2 — Normalize each alarm to the canonical model.

    Mapping log strategy:
    - Per-alarm: log source_equipment_type mappings and Orion fault_description rename.
    - Per-alarm: scan parent_equipment_id prefix to log any additional component
      type mappings encountered (e.g. OTRx-3 parent → OTRx→OPTICAL_MODULE).
    - Per OEM (once): emit the complete OEM component-type map so downstream
      agents have the full translation table even for equipment types not seen
      directly in source_equipment_type this batch.
    """
    normalized: list[dict] = []
    mappings: list[dict] = []
    gaps: list[dict] = []
    errors: list[str] = list(state.get("errors", []))
    seen_oems: set[str] = set()

    for alarm in state["raw_alarms"]:
        oem = str(alarm.get("das_oem", "")).lower()
        alarm_ref = alarm.get("alarm_id", "?")
        try:
            if oem == "stratum":
                norm = _normalize_stratum(alarm, mappings, gaps)
                prefixes = _STRATUM_PREFIXES
            elif oem == "orion":
                norm = _normalize_orion(alarm, mappings, gaps)
                prefixes = _ORION_PREFIXES
            else:
                norm = {
                    "site_id": alarm.get("site_id", ""),
                    "site_name": alarm.get("site_name", ""),
                    "zone_id": alarm.get("zone_id", ""),
                    "alarm_name": alarm.get("alarm_name")
                    or alarm.get("fault_description", ""),
                    "alarm_code": alarm.get("alarm_code", ""),
                    "alarm_category": "UNKNOWN",
                    "source_equipment_type": alarm.get("source_equipment_type", ""),
                    "source_equipment_id": alarm.get("source_equipment_id", ""),
                    "parent_equipment_id": alarm.get("parent_equipment_id"),
                    "severity": alarm.get("severity", "info"),
                    "timestamp": alarm.get("timestamp", ""),
                    "das_oem": oem,
                    "raw_alarm_ref": alarm_ref,
                }
                prefixes = []

            # Emit the full OEM component map once per OEM seen in this batch
            if oem not in seen_oems:
                seen_oems.add(oem)
                mappings.extend(_oem_component_map_entries(oem))

            # Also log any component type implied by parent_equipment_id prefix
            parent_id = alarm.get("parent_equipment_id") or ""
            if parent_id and prefixes:
                parent_canonical = _infer_component_type(parent_id, prefixes)
                if parent_canonical:
                    # Find which OEM prefix matched
                    oem_prefix = next(
                        (p for p, c in prefixes if parent_id.startswith(p)), None
                    )
                    if oem_prefix and oem_prefix != parent_id:  # guard against exact-match IDs
                        mappings.append(
                            {
                                "oem_field": "source_equipment_type",
                                "oem_value": oem_prefix,
                                "canonical_value": parent_canonical,
                            }
                        )

            normalized.append(norm)
        except Exception as exc:
            errors.append(f"Normalization failed for alarm {alarm_ref}: {exc}")

    return {
        **state,
        "normalized_alarms": normalized,
        "field_mappings_log": _dedup(mappings),
        "severity_gaps_log": gaps,
        "errors": errors,
    }


def group_and_aggregate(state: IngestionState) -> IngestionState:
    """
    Node 3 — Group normalized alarms by (site_id, zone_id) and aggregate
    within the configured window.  Produces one site event per group.
    """
    window_minutes = state.get("aggregation_window_minutes", AGGREGATION_WINDOW_MINUTES)

    # Group by (site_id, zone_id)
    groups: dict[tuple[str, str], list[dict]] = {}
    for alarm in state["normalized_alarms"]:
        key = (alarm["site_id"], alarm["zone_id"])
        groups.setdefault(key, []).append(alarm)

    site_events: list[dict] = []
    for (site_id, zone_id), alarms in groups.items():
        # Sort alarms chronologically
        alarms_sorted = sorted(alarms, key=lambda a: a["timestamp"])

        # Window anchored to the first alarm timestamp
        first_ts = _parse_ts(alarms_sorted[0]["timestamp"])
        window_end_ts = first_ts + timedelta(minutes=window_minutes)

        # Keep only alarms that fall within the window
        in_window = [
            a for a in alarms_sorted if _parse_ts(a["timestamp"]) <= window_end_ts
        ]

        alarm_count = len(in_window)
        is_aggregated = alarm_count > 1
        is_stray = alarm_count == 1

        dom_sev = _dominant_severity([a["severity"] for a in in_window])
        dom_cat = _dominant_category([a["alarm_category"] for a in in_window])
        oems = sorted({a["das_oem"] for a in in_window})

        site_events.append(
            {
                "site_id": site_id,
                "zone_id": zone_id,
                "site_name": in_window[0].get("site_name", ""),
                "alarm_count": alarm_count,
                "dominant_severity": dom_sev,
                "alarm_category": dom_cat,
                "alarm_list": in_window,
                "aggregated": is_aggregated,
                "stray_alarm": is_stray,
                "aggregation_window_start": _fmt_ts(first_ts),
                "aggregation_window_end": _fmt_ts(window_end_ts),
                "normalization_applied": True,
                "das_oems": oems,
            }
        )

    return {**state, "site_events": site_events}


def attach_metadata(state: IngestionState) -> IngestionState:
    """
    Node 4 — Attach per-event field-mapping and severity-gap metadata.
    Filters global logs to only include records relevant to each event's alarms.
    """
    all_mappings = state["field_mappings_log"]
    all_gaps = state["severity_gaps_log"]

    updated: list[dict] = []
    for event in state["site_events"]:
        refs = {a["raw_alarm_ref"] for a in event["alarm_list"]}
        oems = set(event.get("das_oems", []))

        # Field mappings: filter to OEMs present in this event
        # fault_description mapping is Orion-only; equipment-type mappings are OEM-specific
        event_mappings: list[dict] = []
        for m in all_mappings:
            # fault_description -> alarm_name is Orion-only
            if m.get("oem_field") == "fault_description" and "orion" not in oems:
                continue
            event_mappings.append(m)

        # Severity gaps: filter to alarms in this event
        event_gaps = [g for g in all_gaps if g.get("alarm_id") in refs]

        updated.append(
            {
                **event,
                "field_mappings_resolved": _dedup(event_mappings),
                "severity_gaps_resolved": event_gaps,
            }
        )

    return {**state, "site_events": updated}


# ── Graph assembly ─────────────────────────────────────────────────────


def _build_graph() -> Any:
    builder = StateGraph(IngestionState)

    builder.add_node("validate_batch", validate_batch)
    builder.add_node("normalize_alarms", normalize_alarms)
    builder.add_node("group_and_aggregate", group_and_aggregate)
    builder.add_node("attach_metadata", attach_metadata)

    builder.set_entry_point("validate_batch")
    builder.add_edge("validate_batch", "normalize_alarms")
    builder.add_edge("normalize_alarms", "group_and_aggregate")
    builder.add_edge("group_and_aggregate", "attach_metadata")
    builder.add_edge("attach_metadata", END)

    return builder.compile()


# Module-level compiled graph (reused across calls)
_graph = _build_graph()


# ── Public API ─────────────────────────────────────────────────────────


def run_ingestion(
    raw_alarms: list[dict],
    aggregation_window_minutes: int = AGGREGATION_WINDOW_MINUTES,
) -> dict:
    """
    Run the ingestion pipeline on a batch of raw alarms.

    Args:
        raw_alarms: List of raw alarm dicts from Stratum or Orion.
        aggregation_window_minutes: Aggregation window in minutes (default 15).

    Returns:
        dict with keys:
          - site_events: list of aggregated site events
          - errors: list of validation/normalization error strings
          - field_mappings_log: global deduplicated field mapping records
          - severity_gaps_log: per-alarm severity gap records
    """
    initial_state: IngestionState = {
        "raw_alarms": raw_alarms,
        "aggregation_window_minutes": aggregation_window_minutes,
        "normalized_alarms": [],
        "field_mappings_log": [],
        "severity_gaps_log": [],
        "site_events": [],
        "errors": [],
    }

    final_state = _graph.invoke(initial_state)

    return {
        "site_events": final_state["site_events"],
        "errors": final_state["errors"],
        "field_mappings_log": final_state["field_mappings_log"],
        "severity_gaps_log": final_state["severity_gaps_log"],
    }

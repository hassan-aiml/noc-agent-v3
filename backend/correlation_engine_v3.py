"""
correlation_engine_v3.py
NOC Triage Agent v3 — Correlation Agent

LangGraph pipeline that takes aggregated site events (from ingestion_agent.py)
and determines:
  1. Cascade type (OPTICAL_CASCADE, SYNC_CASCADE, POWER_CASCADE, HUB_CASCADE, STRAY)
  2. Root cause node (highest-priority alarming equipment)
  3. Downstream alarms (causally related via parent chain traversal)
  4. Blast radius: affected equipment, carriers, bands, service impact
  5. Triage priority (P1–P5) and recommended action

Topology context (site topology + carrier/band data from the NOC inventory) must be
supplied separately as `topology_map: {site_id -> {topology: dict, carriers: list}}`.

Pipeline graph:
  analyze_cascade → identify_downstream → compute_blast_radius → finalize_results → END

Equipment type priority (root cause selection):
  MAIN_HUB > EXPANSION_HUB > OPTICAL_MODULE > REMOTE > POI
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

# ── Equipment type constants ───────────────────────────────────────────

EQUIP_PRIORITY = ["MAIN_HUB", "EXPANSION_HUB", "OPTICAL_MODULE", "REMOTE", "POI"]
SEVERITY_ORDER = ["critical", "major", "minor", "warning", "info"]

# ── Cascade type labels ────────────────────────────────────────────────

CASCADE_SYNC    = "SYNC_CASCADE"
CASCADE_POWER   = "POWER_CASCADE"
CASCADE_OPTICAL = "OPTICAL_CASCADE"
CASCADE_HUB     = "HUB_CASCADE"
CASCADE_STRAY   = "STRAY"
CASCADE_POI     = "POI_SIGNAL_LOSS"

# Keywords for power-related hub alarms
_POWER_KEYWORDS = ("power supply failure", "psu fault", "power input", "power fail")


# ── SiteTopology ──────────────────────────────────────────────────────


class SiteTopology:
    """
    Parses a site topology dict (from scenarios.yaml) into fast lookup maps.

    Topology dict structure (flexible — handles both SCN-001 and SCN-002 shapes):
        main_hub: str | {id: str, ...}
        optical_modules: [{id, parent, remotes, expansion_hub?}]
        expansion_hubs: [{id, parent, optical_modules: [{id, remotes}]}]
        poi | pois: str | list[str]
    """

    def __init__(self, topology: dict, carriers: list[dict]):
        self.parent_map: dict[str, str] = {}    # child_id -> parent_id
        self.node_types: dict[str, str] = {}    # equip_id -> canonical type
        self.carriers: list[dict] = carriers
        self._parse(topology)

    def _register(self, equip_id: str, node_type: str, parent_id: str | None = None) -> None:
        self.node_types[equip_id] = node_type
        if parent_id:
            self.parent_map[equip_id] = parent_id

    def _parse(self, topo: dict) -> None:
        # ── Main hub ──
        mh_raw = topo.get("main_hub", "")
        mh_id: str = mh_raw if isinstance(mh_raw, str) else mh_raw.get("id", "")
        if mh_id:
            self._register(mh_id, "MAIN_HUB")

        # ── Top-level optical modules ──
        for om in topo.get("optical_modules", []):
            om_id = om["id"]
            om_parent = om.get("parent", mh_id)
            self._register(om_id, "OPTICAL_MODULE", om_parent)
            for ru_id in om.get("remotes", []):
                self._register(ru_id, "REMOTE", om_id)
            # expansion_hub field is a reference pointer; actual parent set via expansion_hubs

        # ── Expansion hubs (and their sub-OMs / remotes) ──
        for eh in topo.get("expansion_hubs", []):
            eh_id = eh["id"]
            eh_parent = eh.get("parent", mh_id)
            self._register(eh_id, "EXPANSION_HUB", eh_parent)
            for om in eh.get("optical_modules", []):
                om_id = om["id"]
                self._register(om_id, "OPTICAL_MODULE", eh_id)
                for ru_id in om.get("remotes", []):
                    self._register(ru_id, "REMOTE", om_id)

        # ── POIs ──
        if "pois" in topo:
            for poi_id in (topo["pois"] if isinstance(topo["pois"], list) else [topo["pois"]]):
                self._register(poi_id, "POI")
        elif "poi" in topo:
            self._register(topo["poi"], "POI")

    # ── Navigation helpers ─────────────────────────────────────────────

    def get_parent(self, equip_id: str) -> str | None:
        return self.parent_map.get(equip_id)

    def get_ancestors(self, equip_id: str) -> list[str]:
        """Ordered ancestor chain from immediate parent to root."""
        ancestors: list[str] = []
        current = equip_id
        visited: set[str] = set()
        while True:
            parent = self.parent_map.get(current)
            if not parent or parent in visited:
                break
            ancestors.append(parent)
            visited.add(parent)
            current = parent
        return ancestors

    def is_descendant_of(self, equip_id: str, ancestor_id: str) -> bool:
        return ancestor_id in self.get_ancestors(equip_id)

    def get_expansion_hub_ancestor(self, equip_id: str) -> str | None:
        """Return the nearest EXPANSION_HUB in the parent chain, or None."""
        for anc in self.get_ancestors(equip_id):
            if self.node_types.get(anc) == "EXPANSION_HUB":
                return anc
        return None

    def get_immediate_om_parent(self, equip_id: str) -> str | None:
        """Return the nearest OPTICAL_MODULE ancestor (immediate parent of a remote)."""
        parent = self.parent_map.get(equip_id)
        if parent and self.node_types.get(parent) == "OPTICAL_MODULE":
            return parent
        return None

    def get_all_descendants_of_type(
        self, root_id: str, include_types: set[str]
    ) -> list[str]:
        """
        BFS from root_id; return all descendant IDs whose node_type is in include_types.
        OMs (OPTICAL_MODULE) are traversed but NOT added to the result unless explicitly
        included in include_types.
        """
        # Build children map once
        children_map: dict[str, list[str]] = {}
        for child, parent in self.parent_map.items():
            children_map.setdefault(parent, []).append(child)

        result: list[str] = []
        visited: set[str] = {root_id}
        queue: list[str] = [root_id]

        while queue:
            current = queue.pop(0)
            for child in children_map.get(current, []):
                if child in visited:
                    continue
                visited.add(child)
                if self.node_types.get(child, "") in include_types:
                    result.append(child)
                queue.append(child)  # always traverse, even if type not included

        return result

    # ── Carrier helpers ───────────────────────────────────────────────

    def get_all_carriers(self) -> list[str]:
        seen: list[str] = []
        for c in self.carriers:
            name = c.get("carrier", "")
            if name and name not in seen:
                seen.append(name)
        return seen

    def get_all_bands(self) -> list[str]:
        seen: list[str] = []
        for c in self.carriers:
            for b in c.get("bands", []):
                if b not in seen:
                    seen.append(b)
        return seen

    def get_tdd_carriers(self) -> list[dict]:
        """Carriers that carry any n-prefix (NR/TDD) band."""
        return [c for c in self.carriers if any(b.startswith("n") for b in c.get("bands", []))]

    def carrier_count(self) -> int:
        return len(self.get_all_carriers())


# ── State ─────────────────────────────────────────────────────────────


class CorrelationState(TypedDict):
    site_events: list[dict]      # Input: from ingestion_agent.run_ingestion()
    topology_map: dict           # Input: site_id -> {"topology": dict, "carriers": list}
    event_analyses: list[dict]   # Intermediate: per-event analysis
    results: list[dict]          # Output: one result per site event
    errors: list[str]


# ── Internal helpers ──────────────────────────────────────────────────


def _severity_rank(sev: str) -> int:
    try:
        return SEVERITY_ORDER.index(sev)
    except ValueError:
        return len(SEVERITY_ORDER)


def _equip_priority(eq_type: str) -> int:
    try:
        return EQUIP_PRIORITY.index(eq_type)
    except ValueError:
        return len(EQUIP_PRIORITY)


def _select_root_cause(alarms: list[dict]) -> dict:
    """
    Pick the root cause alarm by equipment type priority (MAIN_HUB first),
    then severity (critical first), then earliest timestamp.
    """
    return sorted(
        alarms,
        key=lambda a: (
            _equip_priority(a.get("source_equipment_type", "")),
            _severity_rank(a.get("severity", "info")),
            a.get("timestamp", ""),
        ),
    )[0]


def _detect_cascade_type(
    site_event: dict, root_alarm: dict
) -> str:
    """
    Classify the alarm pattern into a cascade type.
    Evaluated in priority order — first match wins.
    """
    alarm_category = site_event.get("alarm_category", "")
    alarm_list = site_event.get("alarm_list", [])
    alarm_count = site_event.get("alarm_count", 1)
    stray = site_event.get("stray_alarm", False)

    # POI cascade takes priority — single POI alarm is a distinct fault type, not a stray
    root_type_check = root_alarm.get("source_equipment_type", "")
    if root_type_check == "POI":
        return CASCADE_POI

    if stray or alarm_count == 1:
        return CASCADE_STRAY

    if alarm_category == "TDD_SYNC_LOST":
        return CASCADE_SYNC

    root_type = root_alarm.get("source_equipment_type", "")
    root_name = root_alarm.get("alarm_name", "").lower()

    if root_type == "MAIN_HUB" and any(kw in root_name for kw in _POWER_KEYWORDS):
        return CASCADE_POWER

    if any(a.get("source_equipment_type") == "OPTICAL_MODULE" for a in alarm_list):
        return CASCADE_OPTICAL

    if root_type in ("MAIN_HUB", "EXPANSION_HUB"):
        return CASCADE_HUB

    return CASCADE_STRAY


def _deduplicate_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _group_downstream_by_om(
    downstream_alarms: list[dict],
    topo: SiteTopology | None,
) -> list[tuple[str, list[str], str | None]]:
    """
    Group downstream REMOTE alarms by their immediate OM parent.
    Returns list of (om_id, [remote_ids], eh_id_or_None).
    """
    groups: dict[str, list[str]] = {}
    om_eh: dict[str, str | None] = {}

    for alarm in downstream_alarms:
        if alarm.get("source_equipment_type") != "REMOTE":
            continue
        equip_id = alarm["source_equipment_id"]
        parent_id = alarm.get("parent_equipment_id") or ""

        # Use direct parent from alarm data
        om_id = parent_id if parent_id else equip_id
        groups.setdefault(om_id, []).append(equip_id)

        # Find EH above this OM
        if topo and om_id not in om_eh:
            om_eh[om_id] = topo.get_expansion_hub_ancestor(om_id)

    result = []
    for om_id, remotes in groups.items():
        result.append((om_id, sorted(remotes), om_eh.get(om_id)))
    return result


# ── LangGraph nodes ───────────────────────────────────────────────────


def analyze_cascade(state: CorrelationState) -> CorrelationState:
    """
    Node 1 — For each site event, detect cascade type and select root cause alarm.
    Also builds SiteTopology from topology_map (if available for the site).
    """
    analyses: list[dict] = []
    errors: list[str] = list(state.get("errors", []))

    for event in state["site_events"]:
        site_id = event["site_id"]
        alarm_list = event.get("alarm_list", [])

        if not alarm_list:
            errors.append(f"{site_id}: alarm_list is empty, skipping.")
            continue

        # Build topology (optional — gracefully skipped if missing)
        topo_entry = state.get("topology_map", {}).get(site_id)
        topo: SiteTopology | None = None
        if topo_entry:
            try:
                topo = SiteTopology(
                    topo_entry.get("topology", {}),
                    topo_entry.get("carriers", []),
                )
            except Exception as exc:
                errors.append(f"{site_id}: topology parse failed — {exc}")

        root_alarm = _select_root_cause(alarm_list)
        cascade_type = _detect_cascade_type(event, root_alarm)

        analyses.append(
            {
                "site_id": site_id,
                "zone_id": event["zone_id"],
                "cascade_type": cascade_type,
                "root_alarm": root_alarm,
                "topo": topo,
                "site_event": event,
            }
        )

    return {**state, "event_analyses": analyses, "errors": errors}


def identify_downstream(state: CorrelationState) -> CorrelationState:
    """
    Node 2 — For each analysis, identify downstream alarms and infer intermediate hubs.

    Downstream = causally explained by root cause, determined by:
      1. Topology ancestry check: is_descendant_of(source_id, root_id)
      2. Direct parent fallback: alarm.parent_equipment_id == root_id

    EH inference rule: include an expansion hub in the blast radius if
    ≥2 distinct optical modules under that EH have at least one downstream alarm.
    """
    updated: list[dict] = []

    for analysis in state["event_analyses"]:
        event = analysis["site_event"]
        root_alarm = analysis["root_alarm"]
        topo: SiteTopology | None = analysis["topo"]
        cascade_type = analysis["cascade_type"]
        alarm_list = event.get("alarm_list", [])
        root_id = root_alarm["source_equipment_id"]
        root_ref = root_alarm["raw_alarm_ref"]

        if cascade_type == CASCADE_STRAY:
            updated.append(
                {
                    **analysis,
                    "downstream_alarms": [],
                    "co_alarms": [],    # other root-level alarms (same equip, different alarm)
                    "inferred_hubs": [],
                }
            )
            continue

        downstream: list[dict] = []
        co_alarms: list[dict] = []  # same equipment as root, different alarm

        for alarm in alarm_list:
            if alarm["raw_alarm_ref"] == root_ref:
                continue  # this IS the root alarm

            src_id = alarm["source_equipment_id"]

            if src_id == root_id:
                # Another alarm on the same root equipment
                co_alarms.append(alarm)
                continue

            # Check causal relationship
            is_downstream = False
            if topo:
                is_downstream = topo.is_descendant_of(src_id, root_id)
            if not is_downstream:
                # Direct parent fallback (works without topology)
                is_downstream = alarm.get("parent_equipment_id") == root_id

            if is_downstream:
                downstream.append(alarm)

        # EH inference: group downstream by EH ancestor, count distinct OMs per EH
        eh_oms: dict[str, set[str]] = {}  # eh_id -> set of OM ids routing through it
        for alarm in downstream:
            src_id = alarm["source_equipment_id"]
            parent_id = alarm.get("parent_equipment_id") or ""

            if topo:
                eh = topo.get_expansion_hub_ancestor(src_id)
                om = parent_id or topo.get_immediate_om_parent(src_id) or src_id
            else:
                # Without topology, check if parent_id starts with EH prefix
                eh = None
                om = parent_id

            if eh:
                eh_oms.setdefault(eh, set()).add(om)

        inferred_hubs = [eh for eh, oms in eh_oms.items() if len(oms) >= 2]

        updated.append(
            {
                **analysis,
                "downstream_alarms": downstream,
                "co_alarms": co_alarms,
                "inferred_hubs": inferred_hubs,
            }
        )

    return {**state, "event_analyses": updated}


def compute_blast_radius(state: CorrelationState) -> CorrelationState:
    """
    Node 3 — Compute affected_equipment, carriers, bands, and service_impact string.
    """
    updated: list[dict] = []

    for analysis in state["event_analyses"]:
        event = analysis["site_event"]
        topo: SiteTopology | None = analysis["topo"]
        cascade_type = analysis["cascade_type"]
        root_alarm = analysis["root_alarm"]
        downstream = analysis["downstream_alarms"]
        inferred_hubs = analysis["inferred_hubs"]
        zone_id = analysis["zone_id"]

        root_id = root_alarm["source_equipment_id"]
        root_type = root_alarm.get("source_equipment_type", "")

        # ── affected_equipment ──────────────────────────────────────
        # FIX 1: Full topology traversal for hub/module root causes;
        #        OMs are always filtered out from the blast radius.
        if topo and root_type == "MAIN_HUB":
            all_desc = topo.get_all_descendants_of_type(root_id, {"EXPANSION_HUB", "REMOTE"})
            affected_equipment = _deduplicate_ordered([root_id] + all_desc)
        elif topo and root_type == "EXPANSION_HUB":
            all_desc = topo.get_all_descendants_of_type(root_id, {"REMOTE"})
            affected_equipment = _deduplicate_ordered([root_id] + all_desc)
        elif topo and root_type == "OPTICAL_MODULE":
            all_desc = topo.get_all_descendants_of_type(root_id, {"REMOTE"})
            affected_equipment = _deduplicate_ordered([root_id] + all_desc)
        elif cascade_type == CASCADE_POI:
            affected_equipment = [root_id]
        else:
            # STRAY or no topology: use alarmed equipment only
            equip: list[str] = [root_id]
            equip.extend(inferred_hubs)
            equip.extend(a["source_equipment_id"] for a in downstream)
            affected_equipment = _deduplicate_ordered(equip)

        # ── carriers / bands ────────────────────────────────────────
        if topo:
            all_carriers = topo.get_all_carriers()
            all_bands = topo.get_all_bands()
            tdd_carriers = topo.get_tdd_carriers()
            n_carriers = topo.carrier_count()
        else:
            all_carriers = []
            all_bands = []
            tdd_carriers = []
            n_carriers = 0

        # ── POI cascade: scope to the specific carrier/band served by this POI ──
        poi_carrier_name = ""
        poi_band = ""
        if cascade_type == CASCADE_POI and topo:
            for c in topo.carriers:
                poi_ids = c.get("pois", [])
                if root_id in poi_ids:
                    idx = poi_ids.index(root_id)
                    bands = c.get("bands", [])
                    poi_band = bands[idx] if idx < len(bands) else (bands[0] if bands else "")
                    poi_carrier_name = c.get("carrier", "")
                    break

        if cascade_type == CASCADE_POI:
            affected_carriers = [poi_carrier_name] if poi_carrier_name else all_carriers
            affected_bands = [poi_band] if poi_band else all_bands
        else:
            affected_carriers = all_carriers
            affected_bands = all_bands

        # ── service_impact ──────────────────────────────────────────
        if cascade_type == CASCADE_OPTICAL and topo and n_carriers == 1:
            c = topo.carriers[0]
            bands_str = ", ".join(c.get("bands", []))
            tech = c.get("tech", "LTE")
            if isinstance(tech, list):
                tech = tech[0]
            service_impact = (
                f"{c['carrier']} {bands_str} {tech} coverage loss — {zone_id}"
            )

        elif cascade_type == CASCADE_SYNC:
            # FIX 2: Only mention TDD risk if TDD carriers actually exist at this site.
            eh_id = inferred_hubs[0] if inferred_hubs else root_id
            if tdd_carriers:
                tdd = tdd_carriers[0]
                tdd_band = next(
                    (b for b in tdd.get("bands", []) if b.startswith("n")), "n41"
                )
                service_impact = (
                    f"Sync loss affecting all carriers on {eh_id} zone"
                    f" — {tdd['carrier']} {tdd_band} NR at highest risk"
                )
            else:
                service_impact = (
                    f"Sync loss degrading all carriers on {eh_id} zone"
                    " — all LTE carriers impacted, no TDD carriers at site"
                )

        elif cascade_type in (CASCADE_POWER, CASCADE_HUB) and tdd_carriers and n_carriers > 1:
            tdd = tdd_carriers[0]
            tdd_bands = [b for b in tdd.get("bands", []) if b.startswith("n")]
            tdd_band = tdd_bands[0] if tdd_bands else ""
            service_impact = (
                f"Full site outage — all {n_carriers} carriers, all bands"
                f" including {tdd['carrier']} {tdd_band} NR/TDD"
            )

        elif cascade_type == CASCADE_POI:
            carrier_band = f"{poi_carrier_name} {poi_band}".strip()
            service_impact = (
                f"POI signal loss on {root_id} — {carrier_band} service degraded"
            )

        elif cascade_type == CASCADE_STRAY:
            alarm_category = event.get("alarm_category", "")
            alarm_name = root_alarm.get("alarm_name", "alarm")
            if alarm_category == "UL_NOISE_RISE":
                service_impact = (
                    f"Degraded uplink on {root_id} only — service partially impacted"
                )
            else:
                service_impact = (
                    f"Isolated {alarm_name.lower()} on {root_id}"
                    " — no correlated alarms in window"
                )

        else:
            # Fallback: generic impact description
            carriers_str = ", ".join(affected_carriers) if affected_carriers else "unknown carriers"
            service_impact = (
                f"Service impact on {carriers_str} — {len(affected_equipment)} equipment affected"
            )

        updated.append(
            {
                **analysis,
                "affected_equipment": affected_equipment,
                "affected_carriers": affected_carriers,
                "affected_bands": affected_bands,
                "service_impact": service_impact,
                "poi_carrier_name": poi_carrier_name,
                "poi_band": poi_band,
            }
        )

    return {**state, "event_analyses": updated}


def finalize_results(state: CorrelationState) -> CorrelationState:
    """
    Node 4 — Generate probable_root_cause text, triage priority, recommended action,
    and assemble the final result dict for each site event.
    """
    results: list[dict] = []

    for analysis in state["event_analyses"]:
        event = analysis["site_event"]
        topo: SiteTopology | None = analysis["topo"]
        cascade_type = analysis["cascade_type"]
        root_alarm = analysis["root_alarm"]
        downstream = analysis["downstream_alarms"]
        inferred_hubs = analysis["inferred_hubs"]

        root_id = root_alarm["source_equipment_id"]
        root_type = root_alarm["source_equipment_type"]
        root_parent = root_alarm.get("parent_equipment_id") or ""
        alarm_category = event.get("alarm_category", "UNKNOWN")
        dominant_sev = event.get("dominant_severity", "info")
        poi_carrier_name = analysis.get("poi_carrier_name", "")
        poi_band = analysis.get("poi_band", "")

        # ── probable_root_cause ─────────────────────────────────────

        if cascade_type == CASCADE_OPTICAL:
            downstream_ids = ", ".join(
                a["source_equipment_id"] for a in downstream
                if a.get("source_equipment_type") == "REMOTE"
            )
            probable_root_cause = (
                f"Optical module {root_id} failure on {root_parent}"
                f" causing downstream {downstream_ids} loss"
            )

        elif cascade_type == CASCADE_SYNC:
            eh_id = inferred_hubs[0] if inferred_hubs else (
                topo.get_expansion_hub_ancestor(
                    downstream[0]["source_equipment_id"]
                ) if topo and downstream else "expansion hub"
            )
            # FIX 3: Use OEM-native remote label, not hardcoded "RAU"
            das_oems = event.get("das_oems", [])
            oem = das_oems[0] if das_oems else "stratum"
            remote_label = "RAU" if oem == "orion" else "RU"
            probable_root_cause = (
                f"Timing reference loss on {root_id}"
                f" cascading to {remote_label} communication failures on {eh_id}"
            )

        elif cascade_type == CASCADE_POI:
            carrier_band = f"{poi_carrier_name} {poi_band}".strip()
            probable_root_cause = (
                f"POI signal loss on {root_id} — {carrier_band} service degraded"
                " (physical DAS equipment healthy)"
            )

        elif cascade_type == CASCADE_POWER:
            om_groups = _group_downstream_by_om(downstream, topo)
            group_parts: list[str] = []
            for om_id, remotes, eh_id in om_groups:
                remotes_str = ", ".join(remotes)
                if eh_id:
                    group_parts.append(f"{remotes_str} on {eh_id}/{om_id}")
                else:
                    group_parts.append(f"{remotes_str} on {om_id}")
            groups_desc = " and ".join(group_parts) if group_parts else root_id
            probable_root_cause = (
                f"Power supply failure on {root_id}"
                f" causing full site outage — {groups_desc} offline"
            )

        elif cascade_type == CASCADE_HUB:
            downstream_ids = ", ".join(
                a["source_equipment_id"] for a in downstream
            )
            probable_root_cause = (
                f"Hub {root_id} failure causing downstream {downstream_ids} loss"
            )

        else:  # STRAY
            alarm_name = root_alarm.get("alarm_name", "alarm")
            probable_root_cause = (
                f"Isolated {alarm_name.lower()} on {root_id}"
                " — no correlated alarms in 15-min window"
            )

        # ── triage_priority ─────────────────────────────────────────

        stray = event.get("stray_alarm", False)

        if cascade_type == CASCADE_POI:
            triage_priority = "P2"
        elif alarm_category == "TDD_SYNC_LOST":
            triage_priority = "P1"
        elif alarm_category in ("ELEMENT_OFFLINE", "POWER_FAULT") and dominant_sev == "critical":
            triage_priority = "P1"
        elif alarm_category in ("ELEMENT_OFFLINE", "POWER_FAULT") and dominant_sev == "major":
            triage_priority = "P2"
        elif alarm_category == "OPTICAL_LINK_FAIL" and dominant_sev == "critical":
            triage_priority = "P1"
        elif alarm_category == "DL_POWER_DEGRADED" and dominant_sev in ("critical", "major"):
            triage_priority = "P2"
        elif alarm_category == "UL_NOISE_RISE" and stray:
            triage_priority = "P4"
        elif alarm_category == "UL_NOISE_RISE":
            triage_priority = "P3"
        else:
            triage_priority = "P3"

        # ── recommended_action ──────────────────────────────────────

        if cascade_type == CASCADE_POI:
            carrier_band = f"{poi_carrier_name} {poi_band}".strip()
            recommended_action = (
                f"Check {root_id} signal levels and carrier interface. "
                f"Contact {poi_carrier_name or 'carrier'} operations center to verify source signal. "
                "No dispatch required until carrier confirms signal issue on their end."
            )
        elif cascade_type == CASCADE_SYNC:
            recommended_action = (
                f"Notify Operations and affected TDD carrier(s) immediately. "
                f"Check timing source at {root_id}. "
                "Consider disabling TDD carrier ports to prevent sync-drift interference."
            )
        elif cascade_type == CASCADE_OPTICAL:
            recommended_action = (
                f"Check fiber path from {root_id} to {root_parent}. "
                "Verify connector integrity and optical power levels. "
                "Passive spares only (fiber/coax/connectors) without Operations approval. "
                "Active equipment requires RMA/Sparing approval per OPS-003."
            )
        elif cascade_type == CASCADE_POWER:
            recommended_action = (
                f"Check power feed and UPS status at {root_id}. "
                "Escalate to site landlord/facilities for power restoration. "
                "Active equipment replacement requires RMA/Sparing approval per OPS-003."
            )
        elif alarm_category == "UL_NOISE_RISE":
            recommended_action = (
                f"Monitor uplink RSSI on {root_id}. "
                "Check for external RF interference sources. "
                "No dispatch required at this time — escalate if degradation continues."
            )
        elif alarm_category == "DL_POWER_DEGRADED":
            recommended_action = (
                "Check donor signal level at POI. "
                "Verify source equipment. "
                "If source underpowered, notify carrier before adjusting DAS gain."
            )
        else:
            recommended_action = (
                f"Investigate {root_id} ({root_type}). "
                "Verify passive path first. "
                "Active equipment requires RMA/Sparing approval per OPS-003."
            )

        # ── assemble result ─────────────────────────────────────────

        all_correlated = [root_alarm] + analysis.get("co_alarms", []) + downstream
        correlated_refs = [a["raw_alarm_ref"] for a in all_correlated]

        # POI signal loss is a named fault type, not a stray — override ingestion flag
        result_stray = False if cascade_type == CASCADE_POI else event.get("stray_alarm", False)

        results.append(
            {
                "site_id": event["site_id"],
                "zone_id": event["zone_id"],
                "site_name": event.get("site_name", ""),
                "alarm_count": event["alarm_count"],
                "dominant_severity": dominant_sev,
                "alarm_category": alarm_category,
                "cascade_type": cascade_type,
                "root_cause_node": root_id,
                "root_cause_type": root_type,
                "probable_root_cause": probable_root_cause,
                "blast_radius": {
                    "affected_equipment": analysis["affected_equipment"],
                    "affected_carriers": analysis["affected_carriers"],
                    "affected_bands": analysis["affected_bands"],
                    "service_impact": analysis["service_impact"],
                },
                "triage_priority": triage_priority,
                "recommended_action": recommended_action,
                "correlated_alarm_refs": correlated_refs,
                "stray_alarm": result_stray,
                "aggregated": event.get("aggregated", False),
                "aggregation_window_start": event.get("aggregation_window_start", ""),
                "aggregation_window_end": event.get("aggregation_window_end", ""),
                "normalization_applied": event.get("normalization_applied", True),
                "das_oems": event.get("das_oems", []),
            }
        )

    return {**state, "results": results}


# ── Graph assembly ─────────────────────────────────────────────────────


def _build_graph() -> Any:
    builder = StateGraph(CorrelationState)
    builder.add_node("analyze_cascade", analyze_cascade)
    builder.add_node("identify_downstream", identify_downstream)
    builder.add_node("compute_blast_radius", compute_blast_radius)
    builder.add_node("finalize_results", finalize_results)

    builder.set_entry_point("analyze_cascade")
    builder.add_edge("analyze_cascade", "identify_downstream")
    builder.add_edge("identify_downstream", "compute_blast_radius")
    builder.add_edge("compute_blast_radius", "finalize_results")
    builder.add_edge("finalize_results", END)

    return builder.compile()


_graph = _build_graph()


# ── Public API ─────────────────────────────────────────────────────────


def run_correlation(
    site_events: list[dict],
    topology_map: dict | None = None,
) -> dict:
    """
    Run the correlation pipeline on aggregated site events.

    Args:
        site_events:    Output of ingestion_agent.run_ingestion()["site_events"].
        topology_map:   Dict of {site_id -> {"topology": dict, "carriers": list}}.
                        Optional — blast radius carrier/band data requires it.

    Returns:
        {
            "results": list[dict],  # one correlation result per site event
            "errors": list[str],
        }
    """
    initial: CorrelationState = {
        "site_events": site_events,
        "topology_map": topology_map or {},
        "event_analyses": [],
        "results": [],
        "errors": [],
    }
    final = _graph.invoke(initial)
    return {"results": final["results"], "errors": final["errors"]}

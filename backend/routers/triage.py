"""
routers/triage.py
NOC Triage Agent v3 — POST /triage endpoint

Accepts a list of raw alarms, runs them through the ingestion agent and
correlation engine, persists results to Supabase, and returns the full
triage output.

Supabase persistence:
  - canonical_alarms  — one row per normalized alarm
  - site_events       — one row per aggregated site event
  - triage_results    — one row per correlation result
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Ensure backend/ is on sys.path so sibling-module imports work regardless
# of whether the app is launched from inside backend/ or from the project root.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ingestion_agent import run_ingestion
from correlation_engine_v3 import run_correlation
from rag_pipeline import enrich_results

router = APIRouter(prefix="/triage", tags=["triage"])

# Path to scenarios.yaml
_SCENARIOS_YAML = _BACKEND / "tests" / "ground_truth" / "scenarios.yaml"


# ── Pydantic request models ────────────────────────────────────────────


class RawAlarm(BaseModel):
    alarm_id: str
    das_oem: str
    site_id: str
    site_name: str = ""
    zone_id: str
    alarm_name: str = ""
    alarm_code: str = ""
    fault_description: str | None = None   # Orion field alias for alarm_name
    source_equipment_type: str = ""
    source_equipment_id: str = ""
    parent_equipment_id: str | None = None
    severity: str = "info"
    timestamp: str


class TriageRequest(BaseModel):
    alarms: list[RawAlarm] = Field(..., min_length=1)
    aggregation_window_minutes: int = 15
    topology_map: dict[str, Any] | None = None  # site_id -> {topology, carriers}


class SimulateRequest(BaseModel):
    scenario: str
    site_id: str


# ── Supabase client (lazy init) ────────────────────────────────────────


def _get_supabase():
    """Return a Supabase client, or None if credentials are not configured."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


# ── Persistence helpers ────────────────────────────────────────────────


def _persist_results(
    run_id: str,
    site_events: list[dict],
    correlation_results: list[dict],
) -> list[str]:
    """
    Write ingestion + correlation output to Supabase.
    Returns a list of warning strings if any insert fails.
    Non-fatal: failures are collected and returned but do not abort the response.
    """
    warnings: list[str] = []
    sb = _get_supabase()
    if sb is None:
        warnings.append("Supabase not configured — results not persisted.")
        return warnings

    now = datetime.now(timezone.utc).isoformat()

    # ── canonical_alarms ──────────────────────────────────────────────
    alarm_rows: list[dict] = []
    for event in site_events:
        for alarm in event.get("alarm_list", []):
            alarm_rows.append(
                {
                    "run_id": run_id,
                    "raw_alarm_ref": alarm.get("raw_alarm_ref", ""),
                    "site_id": alarm.get("site_id", ""),
                    "zone_id": alarm.get("zone_id", ""),
                    "site_name": alarm.get("site_name", ""),
                    "alarm_name": alarm.get("alarm_name", ""),
                    "alarm_code": alarm.get("alarm_code", ""),
                    "alarm_category": alarm.get("alarm_category", ""),
                    "source_equipment_type": alarm.get("source_equipment_type", ""),
                    "source_equipment_id": alarm.get("source_equipment_id", ""),
                    "parent_equipment_id": alarm.get("parent_equipment_id"),
                    "severity": alarm.get("severity", "info"),
                    "das_oem": alarm.get("das_oem", ""),
                    "alarm_timestamp": alarm.get("timestamp", ""),
                    "created_at": now,
                }
            )

    if alarm_rows:
        try:
            sb.table("canonical_alarms").insert(alarm_rows).execute()
        except Exception as exc:
            warnings.append(f"canonical_alarms insert failed: {exc}")

    # ── site_events ───────────────────────────────────────────────────
    event_rows: list[dict] = []
    for event in site_events:
        event_rows.append(
            {
                "run_id": run_id,
                "site_id": event.get("site_id", ""),
                "zone_id": event.get("zone_id", ""),
                "site_name": event.get("site_name", ""),
                "alarm_count": event.get("alarm_count", 0),
                "dominant_severity": event.get("dominant_severity", "info"),
                "alarm_category": event.get("alarm_category", "UNKNOWN"),
                "aggregated": event.get("aggregated", False),
                "stray_alarm": event.get("stray_alarm", False),
                "das_oems": event.get("das_oems", []),
                "aggregation_window_start": event.get("aggregation_window_start"),
                "aggregation_window_end": event.get("aggregation_window_end"),
                "normalization_applied": event.get("normalization_applied", True),
                "created_at": now,
            }
        )

    if event_rows:
        try:
            sb.table("site_events").insert(event_rows).execute()
        except Exception as exc:
            warnings.append(f"site_events insert failed: {exc}")

    # ── triage_results ────────────────────────────────────────────────
    result_rows: list[dict] = []
    for r in correlation_results:
        br = r.get("blast_radius", {})
        result_rows.append(
            {
                "run_id": run_id,
                "site_id": r.get("site_id", ""),
                "zone_id": r.get("zone_id", ""),
                "site_name": r.get("site_name", ""),
                "alarm_count": r.get("alarm_count", 0),
                "dominant_severity": r.get("dominant_severity", "info"),
                "alarm_category": r.get("alarm_category", "UNKNOWN"),
                "cascade_type": r.get("cascade_type", ""),
                "root_cause_node": r.get("root_cause_node", ""),
                "root_cause_type": r.get("root_cause_type", ""),
                "probable_root_cause": r.get("probable_root_cause", ""),
                "affected_equipment": br.get("affected_equipment", []),
                "affected_carriers": br.get("affected_carriers", []),
                "affected_bands": br.get("affected_bands", []),
                "service_impact": br.get("service_impact", ""),
                "triage_priority": r.get("triage_priority", "P3"),
                "recommended_action": r.get("recommended_action", ""),
                "correlated_alarm_refs": r.get("correlated_alarm_refs", []),
                "stray_alarm": r.get("stray_alarm", False),
                "aggregated": r.get("aggregated", False),
                "aggregation_window_start": r.get("aggregation_window_start"),
                "aggregation_window_end": r.get("aggregation_window_end"),
                "das_oems": r.get("das_oems", []),
                "created_at": now,
            }
        )

    if result_rows:
        try:
            sb.table("triage_results").insert(result_rows).execute()
        except Exception as exc:
            warnings.append(f"triage_results insert failed: {exc}")

    return warnings


# ── Topology helpers ───────────────────────────────────────────────────


def _load_scenarios() -> list[dict]:
    """Load and return the scenarios list from scenarios.yaml."""
    with open(_SCENARIOS_YAML, "r") as f:
        data = yaml.safe_load(f)
    return data.get("scenarios", [])


def _build_topology_for_site(site_id: str) -> dict:
    """
    Build the v2 topology shape that FlowContainer.jsx expects for a given site_id.

    FlowContainer hardcodes 'MH-01' as the main hub node in its graph builder,
    so we always use main_hub.id = 'MH-01' in the response regardless of the
    real hub ID (MU-01 for Stratum, MH-01 for Orion).
    """
    scenarios = _load_scenarios()

    # Locate topology dict + carriers for the requested site
    topology_dict: dict | None = None
    carriers_list: list[dict] = []
    site_name: str = site_id

    for scn in scenarios:
        # Single-site scenarios have site_id directly on the scenario
        if scn.get("site_id") == site_id:
            topology_dict = scn.get("topology", {})
            carriers_list = scn.get("carriers", [])
            site_name = scn.get("site_name", site_id)
            break

        # Multi-site scenarios (SCN-003) embed per-site data under sub-keys
        for key, val in scn.items():
            if isinstance(val, dict) and val.get("site_id") == site_id:
                topology_dict = val.get("topology", {})
                carriers_list = val.get("carriers", [])
                site_name = val.get("site_name", site_id)
                break
        if topology_dict is not None:
            break

    if topology_dict is None:
        raise ValueError(f"No topology found for site_id={site_id}")

    # ── Build pois list ────────────────────────────────────────────────
    # For each carrier, zip its pois[] with bands[] → one entry per poi.
    pois: list[dict] = []
    for carrier in carriers_list:
        carrier_name = carrier.get("carrier", "")
        bands = carrier.get("bands", [])
        poi_ids = carrier.get("pois", [])
        for poi_id, band in zip(poi_ids, bands):
            pois.append({
                "id": poi_id,
                "carrier": carrier_name,
                "carrier_name": carrier_name,
                "band": band,
            })

    # ── Build expansion_hubs ───────────────────────────────────────────
    # Real EHs first: for each eh in topology.expansion_hubs,
    #   flatten remotes from all eh.optical_modules[].remotes.
    # Then pseudo-EHs: for each top-level OM with direct remotes.
    #
    # NOTE: Top-level OMs can be parents of a real EH AND still have their
    # own direct remotes (e.g. OTRx-1 → EH-01 but also → RAU-01, RAU-02).
    # Always create a pseudo-EH for any top-level OM that has direct remotes.

    real_ehs_raw = topology_dict.get("expansion_hubs", [])
    top_level_oms = topology_dict.get("optical_modules", [])

    expansion_hubs: list[dict] = []

    # Real EHs — flatten all remotes from their sub-OMs
    for eh in real_ehs_raw:
        remotes: list[str] = []
        for sub_om in eh.get("optical_modules", []):
            remotes.extend(sub_om.get("remotes", []))
        expansion_hubs.append({
            "id": eh["id"],
            "location": eh.get("label", f"Expansion Hub {eh['id']}"),
            "is_critical": False,
            "remotes": remotes,
        })

    # FIX 4: Group ALL direct-connect remotes (from top-level OMs) into a single
    # virtual DIRECT hub instead of exposing individual OM nodes in the topology view.
    direct_remotes: list[str] = []
    for om in top_level_oms:
        direct_remotes.extend(om.get("remotes", []))
    if direct_remotes:
        mh_raw = topology_dict.get("main_hub", "MH-01")
        mh_str = mh_raw if isinstance(mh_raw, str) else mh_raw.get("id", "MH-01")
        expansion_hubs.append({
            "id": f"{mh_str}-DIRECT",
            "location": "Direct Connect",
            "is_critical": False,
            "remotes": direct_remotes,
        })

    # ── Build nodes dict ───────────────────────────────────────────────
    nodes: dict[str, dict] = {}
    nodes["MH-01"] = {}
    for eh in expansion_hubs:
        nodes[eh["id"]] = {}
        for ru in eh["remotes"]:
            nodes[ru] = {}
    for poi in pois:
        nodes[poi["id"]] = {}

    return {
        "sites": [
            {
                "site_id": site_id,
                "site_name": site_name,
                "main_hub": {
                    "id": "MH-01",
                    "expansion_hubs": expansion_hubs,
                },
            }
        ],
        "pois": pois,
        "nodes": nodes,
    }


# ── v3 → v2 incident mapping helpers ──────────────────────────────────


def _map_root_cause_type(v3_type: str) -> str:
    return {
        "MAIN_HUB": "main_hub",
        "EXPANSION_HUB": "expansion_hub",
        "OPTICAL_MODULE": "expansion_hub",
        "REMOTE": "remote",
        "POI": "poi",
    }.get(v3_type, "remote")


def _make_v2_incident(result: dict) -> dict:
    br = result.get("blast_radius", {})
    cascade_labels = {
        "OPTICAL_CASCADE": "Optical Cascade",
        "SYNC_CASCADE": "Sync Cascade",
        "POWER_CASCADE": "Power Cascade",
        "HUB_CASCADE": "Hub Cascade",
        "STRAY": "Isolated Alarm",
        "POI_SIGNAL_LOSS": "POI Signal Loss",
    }
    cascade_type = result.get("cascade_type", "")
    scope_label = cascade_labels.get(cascade_type, cascade_type)
    scope_label += f" · {len(br.get('affected_equipment', []))} equip."

    return {
        "incident_id": f"{result['site_id']}-{result['zone_id']}",
        "title": f"{result.get('alarm_category', '')} — {result.get('cascade_type', '')}",
        "severity": result.get("triage_priority", "P3"),   # P1-P5 — TriageTerminal uses this
        "scope_label": scope_label,
        "root_cause_node": result.get("root_cause_node", ""),
        "root_cause_type": _map_root_cause_type(result.get("root_cause_type", "")),
        "affected_nodes": br.get("affected_equipment", []),
        "is_critical_zone": result.get("triage_priority", "P3") in ("P1", "P2"),
        "sparing_advice": None,
    }


def _build_triage_brief(result: dict) -> str:
    br = result.get("blast_radius", {})
    affected_equipment = ", ".join(br.get("affected_equipment", []))
    affected_carriers = ", ".join(br.get("affected_carriers", []))
    affected_bands = ", ".join(br.get("affected_bands", []))
    service_impact = br.get("service_impact", "")
    probable_root_cause = result.get("probable_root_cause", "")
    recommended_action = result.get("recommended_action", "")

    return (
        f"PROBABLE ROOT CAUSE:\n"
        f"{probable_root_cause}\n\n"
        f"BLAST RADIUS:\n"
        f"  Equipment : {affected_equipment}\n"
        f"  Carriers  : {affected_carriers}\n"
        f"  Bands     : {affected_bands}\n"
        f"  Impact    : {service_impact}\n\n"
        f"RECOMMENDED ACTION:\n"
        f"{recommended_action}"
    )


# ── Endpoints ──────────────────────────────────────────────────────────


@router.post("")
def run_triage(req: TriageRequest) -> dict:
    """
    POST /triage

    Run ingestion + correlation on a raw alarm batch and return the full
    triage output. Results are persisted to Supabase if credentials are set.

    Request body:
      alarms                    — list of raw alarms (Stratum or Orion)
      aggregation_window_minutes — default 15
      topology_map              — optional {site_id: {topology, carriers}}

    Response:
      run_id          — UUID for this triage run
      site_events     — aggregated site events from the ingestion agent
      results         — correlation results (one per site event)
      ingestion_errors
      correlation_errors
      persistence_warnings
    """
    run_id = str(uuid.uuid4())

    # Serialize Pydantic models to plain dicts
    raw_alarms = [a.model_dump(exclude_none=False) for a in req.alarms]
    # Drop None fault_description to avoid confusing stratum normalizer
    for alarm in raw_alarms:
        if alarm.get("fault_description") is None:
            alarm.pop("fault_description", None)

    # ── Ingestion ──────────────────────────────────────────────────────
    try:
        ingestion_out = run_ingestion(
            raw_alarms,
            aggregation_window_minutes=req.aggregation_window_minutes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion pipeline failed: {exc}")

    site_events = ingestion_out["site_events"]
    ingestion_errors = ingestion_out["errors"]

    if not site_events:
        raise HTTPException(
            status_code=422,
            detail="Ingestion produced no site events. Check alarm fields.",
        )

    # ── Correlation ────────────────────────────────────────────────────
    try:
        corr_out = run_correlation(
            site_events,
            topology_map=req.topology_map,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Correlation pipeline failed: {exc}")

    results = corr_out["results"]
    correlation_errors = corr_out["errors"]

    # ── RAG enrichment ─────────────────────────────────────────────────
    results = enrich_results(results)

    # ── Persist ────────────────────────────────────────────────────────
    persistence_warnings = _persist_results(run_id, site_events, results)

    return {
        "run_id": run_id,
        "site_events": site_events,
        "results": results,
        "ingestion_errors": ingestion_errors,
        "correlation_errors": correlation_errors,
        "persistence_warnings": persistence_warnings,
    }


@router.get("/topology")
def get_topology(site_id: str = Query(..., description="Site ID, e.g. SITE-ATX-001")) -> dict:
    """
    GET /triage/topology?site_id=SITE-ATX-001

    Returns the topology for the given site in the v2 shape that
    FlowContainer.jsx expects. Built from scenarios.yaml.

    FlowContainer hardcodes 'MH-01' for the main hub node, so main_hub.id
    is always 'MH-01' regardless of the real hub ID in the YAML.
    """
    try:
        topology = _build_topology_for_site(site_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Topology build failed: {exc}")

    return topology


@router.post("/simulate")
def simulate_scenario(req: SimulateRequest) -> dict:
    """
    POST /triage/simulate

    Accepts {scenario, site_id}. Loads alarms from scenarios.yaml for that
    (scenario, site_id) pair, runs ingestion + correlation, maps v3 results
    to v2 incident shape, and returns the full UI payload.
    """
    scenarios = _load_scenarios()

    # ── Find raw alarms for (scenario_id, site_id) ─────────────────────
    raw_alarms: list[dict] = []
    topology_carriers: dict | None = None  # for topology_map

    for scn in scenarios:
        if scn.get("id") != req.scenario:
            continue

        all_alarms: list[dict] = scn.get("raw_alarms", [])

        # For multi-site scenarios (e.g. SCN-003), filter by site_id
        site_alarms = [a for a in all_alarms if a.get("site_id") == req.site_id]

        if not site_alarms:
            break  # scenario found but no alarms for this site

        raw_alarms = site_alarms

        # Find topology + carriers for this site (could be top-level or sub-key)
        if scn.get("site_id") == req.site_id:
            topology_carriers = {
                req.site_id: {
                    "topology": scn.get("topology", {}),
                    "carriers": scn.get("carriers", []),
                }
            }
        else:
            for key, val in scn.items():
                if isinstance(val, dict) and val.get("site_id") == req.site_id:
                    topology_carriers = {
                        req.site_id: {
                            "topology": val.get("topology", {}),
                            "carriers": val.get("carriers", []),
                        }
                    }
                    break
        break

    if not raw_alarms:
        raise HTTPException(
            status_code=404,
            detail=f"No alarms found for scenario={req.scenario}, site_id={req.site_id}",
        )

    # ── Ingestion ──────────────────────────────────────────────────────
    # Pass alarms directly — ingestion_agent handles fault_description→alarm_name
    # and all OEM normalization internally.
    try:
        ingestion_out = run_ingestion(raw_alarms)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion pipeline failed: {exc}")

    site_events: list[dict] = ingestion_out.get("site_events", [])

    if not site_events:
        raise HTTPException(
            status_code=500,
            detail="Ingestion produced no site events. Check alarm fields.",
        )

    # ── Correlation ────────────────────────────────────────────────────
    try:
        corr_out = run_correlation(site_events, topology_map=topology_carriers)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Correlation pipeline failed: {exc}")

    results: list[dict] = corr_out.get("results", [])

    # ── RAG enrichment ─────────────────────────────────────────────────
    results = enrich_results(results)

    # ── Build topology for this site (for the UI) ─────────────────────
    try:
        topology = _build_topology_for_site(req.site_id)
    except Exception:
        topology = None  # non-fatal; UI can still show incidents

    # ── Map v3 results → v2 incidents ─────────────────────────────────
    incidents = [_make_v2_incident(r) for r in results]

    # Primary = lowest priority number (P1 > P2 > P3 …)
    def _priority_key(inc: dict) -> int:
        sev = inc.get("severity", "P5")
        try:
            return int(sev[1])
        except (IndexError, ValueError):
            return 99

    primary_incident = min(incidents, key=_priority_key) if incidents else None

    # ── triage_brief from the highest-priority result ──────────────────
    triage_brief = ""
    if results:
        top_result = min(
            results,
            key=lambda r: int(r.get("triage_priority", "P5")[1:]) if r.get("triage_priority", "P5")[1:].isdigit() else 99,
        )
        triage_brief = _build_triage_brief(top_result)

    # ── ingestion_meta from first site event ──────────────────────────
    ingestion_meta: dict = {}
    if site_events:
        first = site_events[0]
        ingestion_meta = {
            "field_mappings": first.get("field_mappings_resolved", []),
            "severity_gaps": first.get("severity_gaps_resolved", []),
            "oem": first.get("das_oems", []),
        }

    return {
        "incidents": incidents,
        "primary_incident": primary_incident,
        "triage_brief": triage_brief,
        "ingestion_meta": ingestion_meta,
        "topology": topology,
        "site_events": site_events,   # FIX 6: Panel 2 ingestion animation
        "results": results,           # FIX 6: Panel 3 triage detail
    }

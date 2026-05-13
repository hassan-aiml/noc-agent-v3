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
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ingestion_agent import run_ingestion
from correlation_engine_v3 import run_correlation

router = APIRouter(prefix="/triage", tags=["triage"])


# ── Pydantic request model ────────────────────────────────────────────


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


# ── Endpoint ───────────────────────────────────────────────────────────


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

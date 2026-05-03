"""
main.py — FastAPI entry point for NOC Triage Agent v2
Scenarios updated to use canonical alarm codes matching new runbook schema.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import dataclasses

from topology_manager import TopologyManager
from correlation_engine import CorrelationEngine
from triage_logic import generate_triage_brief

app = FastAPI(title="NOC Triage Agent v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

topo   = TopologyManager()
engine = CorrelationEngine(topo)

# ── Models ────────────────────────────────────────────────────────────
class AlarmEvent(BaseModel):
    node_id: str
    alarm_code: str
    carrier: str | None = None
    band: str | None = None

class ScenarioRequest(BaseModel):
    scenario: str

# ── Scenarios ─────────────────────────────────────────────────────────
# Alarm codes match ALARM_CODE_TO_RUNBOOK_ID in triage_logic.py
# and ALARM_BASE_SEVERITY in correlation_engine.py.
SCENARIOS = {
    # INT-005 VSWR — single remote, passive fault
    "single_ru": [
        {"node_id": "RU-01", "alarm_code": "VSWR_HIGH"},
    ],
    # INT-001 Optical Link Outage — all 5 RUs under EH-01
    # Correlation engine identifies EH-01 as root cause
    "hub_failure": [
        {"node_id": "RU-01", "alarm_code": "FIBER_LOS"},
        {"node_id": "RU-02", "alarm_code": "FIBER_LOS"},
        {"node_id": "RU-03", "alarm_code": "FIBER_LOS"},
        {"node_id": "RU-04", "alarm_code": "FIBER_LOS"},
        {"node_id": "RU-05", "alarm_code": "FIBER_LOS"},
    ],
    # EXT-002 Source Underpower — Meridian n41 POI signal loss
    # All 8 RUs show DL_POWER_LOW, POI-MDN-N41 identified as root cause
    "poi_signal_loss": [
        {"node_id": "RU-01", "alarm_code": "DL_POWER_LOW", "carrier": "MDN", "band": "n41"},
        {"node_id": "RU-02", "alarm_code": "DL_POWER_LOW", "carrier": "MDN", "band": "n41"},
        {"node_id": "RU-03", "alarm_code": "DL_POWER_LOW", "carrier": "MDN", "band": "n41"},
        {"node_id": "RU-04", "alarm_code": "DL_POWER_LOW", "carrier": "MDN", "band": "n41"},
        {"node_id": "RU-05", "alarm_code": "DL_POWER_LOW", "carrier": "MDN", "band": "n41"},
        {"node_id": "RU-06", "alarm_code": "DL_POWER_LOW", "carrier": "MDN", "band": "n41"},
        {"node_id": "RU-07", "alarm_code": "DL_POWER_LOW", "carrier": "MDN", "band": "n41"},
        {"node_id": "RU-08", "alarm_code": "DL_POWER_LOW", "carrier": "MDN", "band": "n41"},
    ],
}

# ── Routes ────────────────────────────────────────────────────────────
@app.get("/topology")
def get_topology():
    return topo.get_full_topology()

@app.post("/simulate")
def simulate_scenario(req: ScenarioRequest):
    raw_alarms = SCENARIOS.get(req.scenario)
    if not raw_alarms:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}")

    incidents = engine.correlate(raw_alarms)
    if not incidents:
        return {"incidents": [], "triage_brief": "No incidents generated.", "primary_incident": None}

    primary = max(incidents, key=lambda i: ({"P1": 3, "P2": 2, "P3": 1}.get(i.severity, 0), 1 if i.root_cause_type == "poi" else 0, len(i.affected_nodes)))
    brief = generate_triage_brief(primary)

    return {
        "incidents": [dataclasses.asdict(i) for i in incidents],
        "triage_brief": brief,
        "primary_incident": dataclasses.asdict(primary),
    }

@app.post("/correlate")
def correlate_alarms(alarms: list[AlarmEvent]):
    raw = [a.model_dump() for a in alarms]
    incidents = engine.correlate(raw)
    return {"incidents": [dataclasses.asdict(i) for i in incidents]}

@app.get("/health")
def health():
    return {"status": "ok"}

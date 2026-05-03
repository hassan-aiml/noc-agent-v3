"""
triage_logic.py
Full RAG pipeline — Voyage AI + Supabase pgvector + Claude.
Alarm codes mapped to new runbook IDs (v2 schema).
"""

import os
from dotenv import load_dotenv
import anthropic
import voyageai
from supabase import create_client
from correlation_engine import Incident

load_dotenv()

# ── Lazy client init ──────────────────────────────────────────────────
_ac = None
_vo = None
_sb = None

def _get_clients():
    global _ac, _vo, _sb
    if _ac is None:
        _ac = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        _vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
        _sb = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"],
        )
    return _ac, _vo, _sb


# ── Canonical alarm code → runbook ID ────────────────────────────────
# Maps v2 canonical alarm codes to runbook IDs in noc_kb.
# Updated for new runbook numbering schema.
ALARM_CODE_TO_RUNBOOK_ID = {
    # Internal alarms
    "FIBER_LOS":        "INT-001",   # Optical Link Outage
    "PSU_FAULT":        "INT-002",   # Power Supply Failure
    "DL_POWER_LOW":     "INT-003",   # Downlink Power Low
    "DL_POWER_HIGH":    "INT-004",   # Downlink Power High
    "VSWR_HIGH":        "INT-005",   # Reflected Power (VSWR)
    "UL_NOISE_RISE":    "INT-006",   # Uplink Noise / RSSI Rise
    "OVERTEMP":         "INT-007",   # High Temperature
    "FAN_FAULT":        "INT-008",   # Fan Fault
    "SYNC_LOSS":        "INT-009",   # Clock / Sync Loss
    "LNA_PA_FAULT":     "INT-010",   # LNA / PA Hard Fault
    "PIM_DETECTED":     "INT-011",   # PIM Detection
    "OPT_SATURATION":   "INT-012",   # Optical Over-Saturation
    "COMM_ERROR":       "INT-013",   # Communication Error
    "RU_OFFLINE":       "INT-001",   # RU offline → optical/power runbook
    "HUB_OFFLINE":      "INT-002",   # Hub offline → power runbook
    "MGMT_UNREACHABLE": "INT-013",   # Maps to comm error
    # External alarms
    "DL_OVERDRIVE":     "EXT-001",   # Source Overdrive
    "DL_INPUT_LOW":     "EXT-002",   # Source Underpower
    "DRY_CONTACT":      "EXT-003",   # Dry Contact / Aux Alarm
}


# ── RAG pipeline ──────────────────────────────────────────────────────
def _embed_alarm(runbook_id: str, description: str) -> list[float]:
    _, vo, _ = _get_clients()
    result = vo.embed(
        [f"Alarm {runbook_id}: {description}"],
        model="voyage-3",
        input_type="query"
    )
    return result.embeddings[0]


def _retrieve_context(embedding: list[float], runbook_id: str, top_k: int = 5) -> list[dict]:
    _, _, sb = _get_clients()

    # Pass 1: exact alarm ID match
    exact = sb.table("noc_kb_chunks") \
               .select("alarm_id, category, severity, alarm_name, section, content") \
               .eq("alarm_id", runbook_id) \
               .limit(3) \
               .execute()

    # Pass 2: semantic similarity
    semantic = sb.rpc("match_noc_chunks", {
        "query_embedding": embedding,
        "match_count": top_k,
        "filter_category": None,
        "filter_severity": None,
    }).execute()

    seen = set()
    chunks = []
    for row in (exact.data or []) + (semantic.data or []):
        key = row.get("content", "")[:100]
        if key not in seen:
            seen.add(key)
            chunks.append(row)

    return chunks[:8]


def _format_context(chunks: list[dict]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(
            f"[RUNBOOK {i}] {c.get('alarm_id','?')} — {c.get('alarm_name','?')} "
            f"| Section: {c.get('section','?')}\n{c.get('content','')}"
        )
    return "\n\n---\n\n".join(lines)


def _build_description(incident: Incident) -> str:
    poi = f" POI suspect: {incident.poi_suspect}." if incident.poi_suspect else ""
    critical = " Zone is CRITICAL." if incident.is_critical_zone else ""
    return (
        f"{incident.alarm_code} — {incident.scope_label}: {', '.join(incident.affected_nodes)}. "
        f"Root cause: {incident.root_cause_node} ({incident.root_cause_type}). "
        f"Severity {incident.severity}.{poi}{critical}"
    )


# ── Claude prompt ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a DAS (Distributed Antenna System) NOC triage agent for a neutral host third-party operator (3PO).

Produce a concise triage brief for the NOC operator. Use the retrieved runbook context to reason accurately.

CRITICAL RULES:
1. Always classify the alarm as INTERNAL (DAS hardware — our problem) or EXTERNAL (carrier BTS/RAN — notify carrier).
2. For Downlink Power Low across ALL remotes simultaneously: suspect Source Underpower at POI (EXT-002) before classifying as internal. This is the most common misdiagnosis.
3. For Source Overdrive (EXT-001): never adjust DAS gain to compensate — notify carrier immediately.
4. For Clock/Sync Loss (INT-009): always P1, notify Operations and affected TDD carrier(s), consider disabling TDD carrier ports.
5. For Fan Fault (INT-008) + High Temperature (INT-007) co-occurring: escalate to P1 immediately.
6. Passive spares only (fiber/coax/connectors) without Operations approval. Active electronics require RMA/Sparing check per OPS-003.
7. Reference specific runbook IDs, node IDs, and checklist steps in your brief.

Write 4–6 sentences. Lead with classification and root cause, then scope and severity, then immediate action."""


def _run_triage(incident: Incident, description: str, context: str) -> str:
    ac, _, _ = _get_clients()
    user_prompt = f"""INCIDENT:
ID: {incident.incident_id}
Title: {incident.title}
Alarm Code: {incident.alarm_code}
Root Cause: {incident.root_cause_node} ({incident.root_cause_type})
Affected Nodes: {', '.join(incident.affected_nodes)}
Scope: {incident.scope_label}
Severity: {incident.severity}
Critical Zone: {'YES' if incident.is_critical_zone else 'No'}
POI Suspect: {incident.poi_suspect or 'None'}
Sparing: {incident.sparing_advice}
Description: {description}

RUNBOOK CONTEXT:
{context}

Write the triage brief."""

    response = ac.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


# ── Public API ────────────────────────────────────────────────────────
def generate_triage_brief(incident: Incident) -> str:
    runbook_id = ALARM_CODE_TO_RUNBOOK_ID.get(incident.alarm_code, "INT-003")
    description = _build_description(incident)

    try:
        embedding = _embed_alarm(runbook_id, description)
        chunks = _retrieve_context(embedding, runbook_id)
        context = _format_context(chunks) if chunks else "No runbook context retrieved."
    except Exception as e:
        context = f"[RAG unavailable: {e}] — proceeding with direct reasoning."

    return _run_triage(incident, description, context)

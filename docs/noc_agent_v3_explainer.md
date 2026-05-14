# NOC Triage Agent v3 — Build Explainer
**Date:** May 4, 2026  
**Session:** Week 1–2 build sprint  
**Author:** Hassan Hai

---

## What We Built

Two agents connected in sequence:

```
Raw OEM Alarms → [Ingestion Agent] → Canonical Events → [Correlation Engine] → Triage Result
```

The ingestion agent cleans and standardizes the data. The correlation engine reasons about it. Together they take messy, OEM-specific alarm feeds and produce actionable triage output a NOC engineer can act on immediately.

---

## The Problem These Agents Solve

A NOC engineer watching an alarm console sees something like this arrive from a Stratum system:

```
STR-OPT-001  CRITICAL  OM-1   Optical Link Failure   08:01
STR-RU-003   CRITICAL  RU-01  Remote Unit Offline     08:03
STR-RU-003   CRITICAL  RU-02  Remote Unit Offline     08:04
STR-RU-003   CRITICAL  RU-03  Remote Unit Offline     08:05
STR-DL-007   MAJOR     RU-04  Downlink Power Low      08:06
```

Five separate alarms. Without domain knowledge the engineer sees 5 problems. With domain knowledge they see 1 problem — OM-1 failed and took down everything downstream. The agent replicates that domain reasoning automatically.

---

## Agent 1: The Ingestion Agent

**File:** `backend/ingestion_agent.py`  
**Framework:** LangGraph  
**What it does:** Normalizes raw OEM alarms into a single canonical format, then groups them by site and time window.

### Why Normalization is Necessary

Stratum and Orion are two different OEM vendors. They use different field names and different component names for the same physical equipment. Without normalization, downstream logic would need to handle both formats everywhere — a maintenance nightmare.

| What it represents | Stratum calls it | Orion calls it | Canonical name |
|---|---|---|---|
| Point of interface | IU | POI | POI |
| Main hub | MU | MH | MAIN_HUB |
| Expansion hub | EU | EH | EXPANSION_HUB |
| Optical module | OM | OTRx | OPTICAL_MODULE |
| Remote unit | RU | RAU | REMOTE |
| Alarm description field | `alarm_name` | `fault_description` | `alarm_name` |

The normalization rule is simple: **all OEM-specific translation happens once at ingestion. Everything downstream operates on canonical terminology only.** This is the canonical model principle — the core architectural decision of Phase 3.

### The Severity Gap

Stratum has 5 severity levels: critical, major, minor, warning, info.  
Orion has 4 severity levels: critical, major, minor, info — **no warning level**.

When an Orion alarm arrives that would be "warning" in Stratum, it arrives as "minor". The ingestion agent detects this gap and notes it:

```
Severity gaps noted (1):
  alarm ORN-20260503-012: arrived as 'minor' — Orion has no warning level.
  Minor is canonical floor for degraded-but-active alarms.
```

This is documented but not corrected — the canonical severity stays as minor. The note exists for traceability.

### The LangGraph Pipeline (Ingestion)

LangGraph is a framework for building agents as a graph of nodes. Each node does one job. The state — a Python dictionary — flows through each node and gets enriched at each step.

The ingestion agent has these nodes:

**Node 1: parse_alarms**  
Reads raw alarm dicts. Detects which OEM each alarm came from based on the `das_oem` field. Applies the field mapping rules — renames `fault_description` to `alarm_name` for Orion, maps OEM component names to canonical names.

**Node 2: validate_alarms**  
Checks that required canonical fields are present. Flags any alarms with missing site_id, timestamp, or severity. In this build, all alarms pass validation.

**Node 3: categorize_alarms**  
Assigns each normalized alarm an `alarm_category` — a canonical classification the correlation engine reasons on. Examples:
- Optical link failure → `OPTICAL_LINK_FAIL`
- Remote unit offline → `ELEMENT_OFFLINE`
- Downlink power low → `DL_POWER_DEGRADED`
- Timing reference lost → `TDD_SYNC_LOST`
- Uplink noise rise → `UL_NOISE_RISE`

**Node 4: aggregate_alarms**  
Groups canonical alarms by `site_id + zone_id`. Applies the 15-minute aggregation window — alarms within 15 minutes of the first alarm on a site get grouped into one site event. If a site has only one alarm with no correlated activity, it gets flagged as `stray_alarm: true`.

Output of the ingestion agent for each site: one aggregated site event with alarm count, dominant severity, alarm list, and window timestamps.

---

## Agent 2: The Correlation Engine

**File:** `backend/correlation_engine_v3.py`  
**Framework:** LangGraph  
**What it does:** Takes aggregated site events and determines root cause, blast radius, triage priority, and recommended action.

### The LangGraph Pipeline (Correlation)

**Node 1: analyze_cascade**  
Builds a `SiteTopology` object from the topology data — a map of every piece of equipment and its parent-child relationships. Then selects the root cause alarm using equipment type priority:

```
MAIN_HUB > EXPANSION_HUB > OPTICAL_MODULE > REMOTE
```

The logic: if a main hub is in alarm alongside several remotes, the main hub is almost certainly the root cause. The remotes are downstream victims. This reflects real DAS operational knowledge — upstream failures cascade downstream.

Also classifies the cascade type:
- `OPTICAL_CASCADE` — optical module failure taking down downstream remotes
- `SYNC_CASCADE` — timing/sync loss on hub affecting TDD carriers
- `POWER_CASCADE` — power failure at hub level
- `STRAY` — single isolated alarm, no cascade

**Node 2: identify_downstream**  
Traverses parent chains to find which alarms are causally related to the root cause. An alarm is downstream if its `parent_equipment_id` traces back to the root cause equipment.

Key rule: an expansion hub is included in the blast radius only if 2 or more distinct optical modules under it have affected remotes. This prevents false positives — one bad remote under an EH doesn't mean the EH itself is implicated.

**Node 3: compute_blast_radius**  
Builds the full impact picture:
- Affected equipment list (root cause + confirmed downstream)
- Affected carriers — pulled from site topology (which carriers have POIs feeding this site)
- Affected bands — all bands for each affected carrier
- Service impact text — generated from cascade type template

**Node 4: finalize_results**  
Generates the human-readable output:
- Probable root cause text (groups downstream RUs by their OM/EH path)
- Triage priority (P1–P5)
- Recommended action

**Triage priority scale:**
| Priority | Criteria |
|---|---|
| P1 | Critical cascade — multiple remotes offline, hub-level failure |
| P2 | Major cascade — degraded service, partial outage |
| P3 | Minor cascade — single element, limited impact |
| P4 | Stray alarm — isolated, no cascade confirmed |
| P5 | Info only — no service impact |

---

## Walking Through the Demo Output

### SCN-001: Austin Domain Tower (Stratum)

**What happened:** OM-1, the first optical module on MU-01, failed. Three remotes connected to it (RU-01, RU-02, RU-03) went offline as a direct result. A fourth remote (RU-04) on OM-2 shows a separate downlink power issue — unrelated.

**What the agent correctly did:**
- Identified OM-1 as root cause (OPTICAL_MODULE > REMOTE in priority)
- Included RU-01, RU-02, RU-03 in blast radius (all parented to OM-1)
- **Excluded RU-04** from blast radius — it's on OM-2, not downstream of OM-1
- Assigned P1 — critical cascade, carrier service lost
- Service impact: Vertex Wireless B4 LTE coverage loss on ZONE-B2

**Why RU-04 exclusion matters:** A less sophisticated system would bundle all 5 alarms together and tell the engineer "5 remotes down." The correlation engine correctly identifies that RU-04's downlink issue is a separate problem on a different optical branch. That's the difference between noise and signal.

---

### SCN-002: Austin Midtown Plaza (Orion)

**What happened:** MH-01 lost its timing reference. This cascaded to RAU-03 and RAU-05 on EH-01 going offline. RAU-04 shows a degraded downlink — a minor symptom on the same branch.

**What the agent correctly did:**
- Mapped Orion's `fault_description` → canonical `alarm_name`
- Mapped `MH` → `MAIN_HUB`, `RAU` → `REMOTE`, `OTRx` → `OPTICAL_MODULE`
- Identified MH-01 as root cause (MAIN_HUB highest priority)
- Classified as `SYNC_CASCADE` — timing loss is a specific cascade type
- Inferred EH-01 in blast radius — both OTRx-3 and OTRx-4 under it have affected remotes (2+ distinct OMs = EH inferred)
- Noted severity gap on RAU-04 (Orion minor vs Stratum warning)
- Service impact: all carriers on EH-01 zone affected, Meridian n41 NR at highest risk (TDD requires sync)

**Why TDD matters here:** Meridian n41 is NR/TDD. TDD carriers require precise timing synchronization. A sync loss on the main hub hits TDD carriers hardest — they can't operate without a valid timing reference. The agent knows this and calls it out in the service impact.

---

### SCN-003: Austin Rainey Street + Austin South Congress

This scenario tests two things simultaneously: a real multi-alarm event on one site, and a stray alarm on a different site at the same time.

**Austin Rainey Street (Stratum) — real event:**  
MU-01 had a power supply failure. RU-01 and RU-02 on OM-1 went offline. RU-04 on EU-01/OM-3 also went offline.

The agent correctly:
- Identified MU-01 as root cause (MAIN_HUB priority)
- Classified as `POWER_CASCADE`
- Did NOT infer EU-01 in blast radius — only OM-3 under EU-01 has an affected remote (only 1 OM, not 2+, so EH inference rule not triggered)
- Reported all 3 carriers affected (Vertex, PeakCell, Meridian) — all bands including n41
- Assigned P1

**Austin South Congress (Orion) — stray alarm:**  
A single minor uplink noise alarm on RAU-03. No other alarms on this site in the 15-minute window.

The agent correctly:
- Kept this completely separate from the Rainey Street event — no cross-site bleeding
- Flagged as `stray_alarm: true`
- Assigned P4 — monitor, no dispatch
- Recommended action: monitor RSSI, check for RF interference, no dispatch required

---

## Key Architectural Decisions

**1. Canonical model at ingestion only**  
OEM translation happens once, in the ingestion agent, at the boundary. The correlation engine never sees "MH" or "fault_description" — it only sees "MAIN_HUB" and "alarm_name". This means adding a third OEM later only requires updating the ingestion mapping — nothing else changes.

**2. Topology-aware correlation**  
The correlation engine doesn't just look at alarm codes. It knows the physical parent-child relationships between equipment. This is what allows it to distinguish a cascade from coincidence.

**3. Equipment priority for root cause**  
The priority order (MAIN_HUB > EXPANSION_HUB > OPTICAL_MODULE > REMOTE) reflects real DAS operational knowledge. Upstream failures cause downstream alarms. If a hub is in alarm alongside remotes, the hub is the cause — not 4 simultaneous remote failures.

**4. EH inference rule**  
An expansion hub is only included in the blast radius when 2+ distinct optical modules under it have affected remotes. One bad remote doesn't implicate the entire expansion hub. This reduces false positives in the blast radius report.

**5. Stray alarm detection**  
A single alarm with no correlated activity in the 15-minute window is flagged as stray. This is operationally important — it prevents a minor isolated event from being escalated to the same level as a full site outage.

---

## What's Next (Week 3)

- FastAPI layer — expose the ingestion + correlation pipeline as REST endpoints
- Supabase schema — persist canonical alarms, site events, and triage results
- Wire the two agents together into a single callable API

---

## File Reference

| File | Purpose |
|---|---|
| `backend/ingestion_agent.py` | LangGraph ingestion pipeline — normalize + aggregate |
| `backend/correlation_engine_v3.py` | LangGraph correlation pipeline — root cause + blast radius |
| `backend/demo_run.py` | CLI demo runner — feeds scenarios through both agents |
| `backend/tests/test_ingestion_agent.py` | Ground truth test runner — validates all 3 scenarios |
| `backend/tests/ground_truth/scenarios.yaml` | Ground truth — raw alarms + expected outputs for 3 scenarios |

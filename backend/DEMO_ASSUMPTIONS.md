# Demo project — architecture and scope

## Overview
This is a demo project for a neutral host DAS NOC AI triage agent.
The architecture described below reflects standard neutral host DAS deployment
practices. Where simplifications were made for demo scope, they are noted in
the Demo scope section.

---

## Network architecture

### POI (Point of Interface)
- Each carrier has a dedicated POI per band — no band sharing between carriers
- There can be more than one POI for the same band, one per carrier
- When a POI alarm fires, both the carrier and the band are known precisely
- Total of 9 POIs in this demo, all feeding into the main hub

### POI assignments
| POI ID          | Carrier           | Band  |
|-----------------|-------------------|-------|
| POI-VTX-B2      | Vertex Wireless   | B2    |
| POI-VTX-B4      | Vertex Wireless   | B4    |
| POI-VTX-B13     | Vertex Wireless   | B13   |
| POI-PKC-B2      | PeakCell Networks | B2    |
| POI-PKC-B4      | PeakCell Networks | B4    |
| POI-PKC-B13     | PeakCell Networks | B13   |
| POI-MDN-B2      | Meridian Mobile   | B2    |
| POI-MDN-B4      | Meridian Mobile   | B4    |
| POI-MDN-N41     | Meridian Mobile   | n41   |

### Signal flow
```
Carrier BTS
    ↓
POI (carrier and band specific)
    ↓
Main Hub  ←── All POI signals mix here (all carriers, all bands)
    ↓ fiber
Expansion Hub(s)  ←── Receives the same signal mix as main hub
    ↓ fiber
Remote Units (RUs)  ←── Band separation happens here
    ↓
Band-specific amplifier modules on each RU
    ↓
Antennas → Coverage
```

### Hub architecture
- One main hub per sector
- Each sector can have 1–2 expansion hubs
- Main hub failure = full sector outage — all carriers, all bands, all expansion hubs
  and their remotes go down
- Expansion hub failure = partial outage — only the zones served by that expansion
  hub and its remotes are affected
- If a hub fault is suspected, further investigation or testing is needed

### Remote units
- Each RU receives the full signal mix from the hub via fiber
- Band separation occurs at the RU level
- Each RU has band-specific amplifier modules
- Each amplifier module carries all participating carriers for that band

---

## Carrier band assignments

| Carrier           | Bands          | Technology        |
|-------------------|----------------|-------------------|
| Vertex Wireless   | B2, B4, B13    | LTE               |
| PeakCell Networks | B2, B4, B13    | LTE               |
| Meridian Mobile   | B2, B4, n41    | LTE + 5G NR (TDD) |

---

## Canonical alarm model

All downstream logic uses canonical alarm codes. OEM-specific alarm names are
translated to canonical codes at ingestion. The table below shows the mapping.

| Canonical Code  | Runbook | Alarm Name               | Severity Base |
|-----------------|---------|--------------------------|---------------|
| FIBER_LOS       | INT-001 | Optical Link Outage      | Critical — P1 |
| PSU_FAULT       | INT-002 | Power Supply Failure     | Critical — P1 |
| DL_POWER_LOW    | INT-003 | Downlink Power Low       | Major — P2    |
| DL_POWER_HIGH   | INT-004 | Downlink Power High      | Major — P2    |
| VSWR_HIGH       | INT-005 | Reflected Power (VSWR)   | Major — P2    |
| UL_NOISE_RISE   | INT-006 | Uplink Noise / RSSI Rise | Major — P2    |
| OVERTEMP        | INT-007 | High Temperature         | Major — P2    |
| FAN_FAULT       | INT-008 | Fan Fault                | Major — P2    |
| SYNC_LOSS       | INT-009 | Clock / Sync Loss        | Critical — P1 |
| LNA_PA_FAULT    | INT-010 | LNA / PA Hard Fault      | Critical — P1 |
| PIM_DETECTED    | INT-011 | PIM Detection            | Major — P2    |
| OPT_SATURATION  | INT-012 | Optical Over-Saturation  | Minor — P3    |
| COMM_ERROR      | INT-013 | Communication Error      | Critical — P1 |
| DL_OVERDRIVE    | EXT-001 | Source Overdrive         | Critical — P1 |
| DL_INPUT_LOW    | EXT-002 | Source Underpower        | Minor — P3    |
| DRY_CONTACT     | EXT-003 | Dry Contact / Aux Alarm  | Variable      |

### Severity escalation rules
- Critical alarm type → always P1 regardless of scope or zone
- Major alarm type → P2 base; escalates to P1 for hub scope, full site, or POI root cause
- Minor alarm type → always P3
- FAN_FAULT + OVERTEMP co-occurring → escalates to P1 regardless of individual severity
- Any alarm in a critical zone → bumps one level (P3→P2, P2→P1)

---

## Demo topology — Northpark Center Mall

### Site
- Site ID: NORTHPARK_MALL
- Controller IP: 10.0.45.1

### Hub chain
```
MH-01 (Main Hub)
├── EH-01 (Expansion Hub — Food Court, non-critical, 5 remotes)
│   ├── RU-01
│   ├── RU-02
│   ├── RU-03
│   ├── RU-04
│   └── RU-05
└── EH-02 (Expansion Hub — Security Center, CRITICAL, 3 remotes)
    ├── RU-06
    ├── RU-07
    └── RU-08
```

---

## Demo alarm scenarios

| Scenario         | Canonical Code | Runbook | Site / Node          | Description                                               | Expected Severity |
|------------------|---------------|---------|----------------------|-----------------------------------------------------------|-------------------|
| Single RU Fault  | VSWR_HIGH     | INT-005 | RU-01 (Food Court)   | Single remote VSWR — passive path fault                   | P2                |
| Hub Failure      | FIBER_LOS     | INT-001 | EH-01 (Food Court)   | All 5 RUs under EH-01 show optical LOS — hub is suspect   | P1                |
| POI Signal Loss  | DL_POWER_LOW  | INT-003 | POI-MDN-N41          | All 8 RUs low on MDN n41 — Source Underpower at POI       | P1                |

### Scenario notes

**Single RU Fault — VSWR_HIGH on RU-01:**
Isolated passive path fault. Antenna, coax, or connector issue at RU-01.
Root cause: RU-01. Scope: Single RU. Severity: P2 (major alarm, single RU).
No upstream or carrier impact. Passive repair first — no RMA required.

**Hub Failure — FIBER_LOS on all 5 RUs under EH-01:**
When all remotes under an expansion hub show optical LOS simultaneously,
the correlation engine identifies EH-01 as the root cause — not the 5
individual remotes. Check power to EH-01 before assuming fiber break.
Root cause: EH-01. Scope: Hub. Severity: P1 (critical alarm type).

**POI Signal Loss — DL_POWER_LOW on all RUs for MDN n41:**
When all remotes show DL_POWER_LOW for the same carrier and band simultaneously,
the correlation engine traces the fault to POI-MDN-N41 (Source Underpower).
This is the most common misdiagnosis in DAS NOC — looks like a DAS fault but
is actually a carrier BTS issue. Do NOT dispatch DAS vendor.
Notify Meridian Mobile per OPS-001. All other carriers and bands unaffected.
Root cause: POI-MDN-N41. Scope: Full Site (POI). Severity: P1.

---

## Demo scope

- Single sector per site — real deployments typically have multiple independent
  sectors, each with their own hub chain and POI set
- 1–2 expansion hubs per sector — real deployments may have more
- No public safety coverage — ERRCS/FirstNet not modeled
- Band-specific amplifier module alarms not modeled individually — RU alarms
  treat the remote as a single unit for simplicity
- OEM translation layer not yet implemented — canonical codes used directly

---

## Fictitious data disclosure
- All carrier names, contact persons, phone numbers, and portal URLs are fictitious
- All site names are used for illustration only
- SLA timelines are representative industry estimates, not contractual obligations
- Operations staff names and vendor contacts are fictitious
- ServiceNow instance URL is fictitious

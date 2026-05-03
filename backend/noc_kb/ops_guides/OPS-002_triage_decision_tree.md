---
doc_id: OPS-002
category: ops_guide
title: NOC triage decision tree — first 5 minutes
tags: [triage, decision, internal, external, carrier, escalation, procedure, servicenow]
---

# NOC triage decision tree — first 5 minutes

## Step 1: Classify the alarm — internal or external?

### External alarms — notify carrier, do NOT open internal ops ticket
| Alarm | ID | Action |
|---|---|---|
| Source Overdrive at POI | EXT-001 | Notify carrier AND Operations — hardware damage risk |
| Source Underpower at POI | EXT-002 | Notify carrier per OPS-001 |
| Dry Contact / Aux Alarm (UPS on battery) | EXT-003 | Notify facilities AND monitor DAS power alarms |

### Internal alarms — notify Operations, vendor dispatch requires Operations authorization
| Alarm | ID | Notes |
|---|---|---|
| Optical Link Outage | INT-001 | Check power first before assuming fiber fault |
| Power Supply Failure | INT-002 | Check building circuit breaker before dispatching vendor |
| Downlink Power Low | INT-003 | Check EXT-002 (Source Underpower) first — most common misdiagnosis |
| Downlink Power High | INT-004 | Check EXT-001 (Source Overdrive) first |
| Reflected Power (VSWR) | INT-005 | Passive repair first — no RMA until path confirmed faulty |
| Uplink Noise / RSSI Rise | INT-006 | Notify carrier AND Operations |
| High Temperature | INT-007 | Contact facilities for HVAC — check INT-008 co-occurrence |
| Fan Fault | INT-008 | Escalate immediately if INT-007 also active |
| Clock / Sync Loss | INT-009 | Always P1 — notify Operations and TDD carrier(s) immediately |
| LNA / PA Hard Fault | INT-010 | Hardware replacement required — confirm RMA before dispatch |
| PIM Detection | INT-011 | Notify carrier AND Operations — passive repair first |
| Optical Over-Saturation | INT-012 | Low urgency — schedule dispatch, bring attenuators |
| Communication Error | INT-013 | Check INT-001 and INT-002 first — often a secondary symptom |

---

## Step 2: Scope — how many elements are affected?

| Scope | Probable cause | Severity |
|---|---|---|
| Single remote, non-critical zone | Local fiber, connector, or hardware fault | P3 base — check alarm type for override |
| Single remote, critical zone | Same as above | P2 minimum |
| Multiple remotes, same hub | Hub upstream, trunk fiber, or EXT-002 at POI | P2 |
| All remotes on site, single carrier/band | POI signal loss — check EXT-002 | P1 |
| All remotes on site, all carriers/bands | Hub or site power loss — check INT-002, INT-001 | P1 |
| Multiple sites simultaneously | Check NMS health first — may be NMS or management network issue |

---

## Step 3: Alarm-type severity overrides — these always apply regardless of scope

These alarms override the scope-based severity. Check these before assigning severity:

| Alarm | Override Rule |
|---|---|
| INT-009 Clock / Sync Loss | Always P1 — no exceptions |
| INT-002 Power Supply Failure (hub or main hub) | Always P1 |
| INT-001 Optical Link Outage (hub branch) | Always P1 |
| INT-010 LNA / PA Hard Fault (multiple units) | Always P1 — suspect surge event |
| EXT-001 Source Overdrive (hardware damage risk) | Always P1 |
| INT-007 High Temperature + INT-008 Fan Fault co-occurring | Escalate to P1 regardless of individual severity |
| INT-013 Communication Error (hub unreachable) | Always P1 |

---

## Step 4: Zone criticality — adjust severity if in critical zone

<!-- ============================================================
     DEMO DATA — Critical zones and site classifications below are
     fictitious examples for demo purposes. Replace with your
     actual site inventory and criticality designations.
     ============================================================ -->

### Critical zones (upgrade severity by one level if affected)

| Site Name | Zone Type | Carriers | Notes |
|---|---|---|---|
| Grand Hyatt Dallas — Floors 1–3, Ballrooms | High-traffic hospitality | Vertex, PeakCell, Meridian | Events venue — frequent large gatherings |
| One Uptown Tower — Lobby, Floors 1–5 | Class A office, high density | Vertex, Meridian | Executive tenant SLA expectation |
| Northpark Center Mall — Food Court, Main Concourse | Retail, high footfall | All three carriers | Weekends especially high traffic |
| DFW Terminal B — Gates B1–B20 | Airport transit | Vertex, PeakCell | High visibility, traveler complaints escalate fast |
| Parkland Medical Center — Main Building | Healthcare facility | All three carriers | Patient and staff dependency — treat all alarms as P2 minimum |

<!-- END DEMO DATA — Zone criticality -->

---

## Step 5: SLA response time targets by severity

<!-- ============================================================
     DEMO DATA — Response time targets below are reasonable
     industry estimates for a neutral host 3PO operator.
     Replace with your actual contractual SLA obligations.
     ============================================================ -->

| Severity | Condition | NOC Notify Operations | Operations Begin Review | Target Restore |
|---|---|---|---|---|
| P1 | Full site outage — all carriers, all bands | Immediately (≤5 min) | ≤15 minutes | 4 hours |
| P1 | Full site outage — single carrier, all bands | ≤10 minutes | ≤20 minutes | 4 hours |
| P1 | Clock / Sync Loss with TDD carriers active | Immediately (≤5 min) | ≤15 minutes | 2 hours (disable TDD first) |
| P1 | Source Overdrive — hardware damage risk | Immediately (≤5 min) | ≤15 minutes | 2 hours |
| P2 | Partial outage — multiple remotes down | ≤20 minutes | ≤60 minutes | 8 hours |
| P2 | Single remote down — critical zone | ≤20 minutes | ≤60 minutes | 8 hours |
| P2 | Fan Fault + High Temperature co-occurring | ≤20 minutes | ≤60 minutes | 4 hours |
| P3 | Single remote — non-critical zone | ≤60 minutes | Next business day | 3 business days |
| P3 | Fan fault, VSWR, optical saturation | Log ticket | Next business day | 5 business days |

<!-- END DEMO DATA — SLA targets -->

---

## Step 6: Operations escalation contacts

<!-- ============================================================
     DEMO DATA — All names, phone numbers, and email addresses
     below are fictitious placeholders for demo purposes.
     Replace with actual Operations on-call personnel and
     escalation paths before using in production.
     ============================================================ -->

### Operations on-call rotation

| Role | Name | Phone | Email | Hours |
|---|---|---|---|---|
| On-Call Operations Engineer (primary) | Derek Sandoval | (214) 555-0461 | d.sandoval@texnetdas-demo.com | 24/7 rotation |
| On-Call Operations Engineer (backup) | Priya Nair | (214) 555-0478 | p.nair@texnetdas-demo.com | 24/7 rotation |
| Operations Manager (P1 escalation) | Tom Beckett | (214) 555-0490 | t.beckett@texnetdas-demo.com | Business hours + P1 on-call |
| VP of Operations (major P1 / SLA breach risk) | Angela Torres | (214) 555-0501 | a.torres@texnetdas-demo.com | P1 escalation only |

### Escalation path for internal alarms
1. NOC opens ServiceNow ticket (queue: NOC-Internal-DAS)
2. NOC calls On-Call Operations Engineer — Derek Sandoval (primary) or Priya Nair (backup)
3. If no response in 20 minutes: call Operations Manager — Tom Beckett
4. If P1 with no Operations response in 30 minutes: call VP of Operations — Angela Torres
5. Operations Engineer reviews remotely, develops vendor scope of work, dispatches per OPS-003

### Escalation path for external alarms
1. NOC notifies carrier per OPS-001
2. NOC opens ServiceNow ticket (queue: NOC-External-Carrier) — log carrier ticket number
3. NOC notifies On-Call Operations Engineer as FYI for P1 (no action unless DAS is also at fault)
4. If carrier does not restore within SLA window — escalate to Operations Manager to engage carrier account team

<!-- END DEMO DATA — Operations contacts -->

---

## Step 7: Common misclassification traps — check these before escalating

| What NOC sees | Wrong action | Correct action |
|---|---|---|
| Downlink Power Low on multiple remotes simultaneously | Dispatch DAS vendor | Check EXT-002 (Source Underpower) first — if external, notify carrier only |
| Downlink Power Low on single remote | Assume hardware fault | Check EXT-002 and recent maintenance log first |
| Communication Error on hub | Declare P1 outage immediately | Check INT-001 (Optical) and INT-002 (Power) first — comm loss is often a symptom |
| Clock / Sync Loss | Treat as minor — FDD still working | Always P1/P2 — notify Operations immediately, disable TDD carriers |
| All carriers down simultaneously | Notify all carriers individually | Check INT-001 (Optical) and INT-002 (Power) first — single internal fault looks like all-carrier outage |
| Fan Fault, no other alarms | Ignore until overtemp appears | Log P2 ticket now — proactive repair prevents thermal shutdown |
| Source Overdrive at POI | Reduce DAS gain to compensate | Never adjust DAS gain — notify carrier immediately, hardware damage risk |
| High Temperature + Fan Fault together | Treat each as separate P2 | Co-occurrence = P1 — escalate immediately |

---

## Step 8: ServiceNow ticket minimum fields

Every alarm must have a ServiceNow ticket, internal or external. Minimum required fields:
- Site name and address
- Alarm ID and name from this KB
- Severity (P1 / P2 / P3)
- Category (internal / external)
- Time alarm first appeared
- NMS screenshot or alarm detail (attach)
- What NOC already checked (POI input level, ping test, carrier contact, etc.)
- For external: carrier ticket number
- For internal: Operations engineer notified (name and time)

<!-- ============================================================
     DEMO DATA — ServiceNow instance below is fictitious.
     ============================================================ -->
ServiceNow: https://texnetdas-demo.service-now.com
Internal queue: NOC-Internal-DAS
External queue: NOC-External-Carrier
P1 auto-page: Enabled for NOC-Internal-DAS severity = P1
<!-- END DEMO DATA -->

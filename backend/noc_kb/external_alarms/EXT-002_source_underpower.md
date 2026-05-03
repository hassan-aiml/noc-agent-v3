---
alarm_id: EXT-002
category: external
subcategory: rf_performance
severity: minor
alarm_name: Source Underpower
tags: [POI, underpower, BTS, carrier, coverage, external, misdiagnosis_risk]
---

# Source Underpower

## What this means
RF input from the carrier at the POI is below the commissioned baseline. DAS coverage is reduced because there is less signal to distribute. Users will see weaker signal and reduced throughput in the affected zones. This is an external carrier issue — the DAS hardware is functioning correctly.

## CRITICAL — This alarm drives the most common misdiagnosis in DAS
When Source Underpower is active, all remotes fed by this POI will show Downlink Power Low (INT-003). It will look like a DAS hardware problem across multiple remotes simultaneously.

Always check for this alarm when INT-003 fires on multiple remotes at the same time. If EXT-002 is active — notify the carrier and do NOT dispatch a DAS vendor.

## Most likely causes (ranked)
1. Carrier BTS sector down or in sleep mode
2. Loose jumper at the head-end POI input port
3. BTS output power drift — gradual degradation
4. Carrier performing maintenance on the BTS sector

## NOC triage checklist
- [ ] Which POI is affected — carrier and band?
- [ ] Is Downlink Power Low (INT-003) also active on multiple remotes fed by this POI?
- [ ] What is the measured input power vs. the commissioned baseline?
- [ ] Has the carrier notified us of planned BTS maintenance?
- [ ] Check the jumper at the POI input port — loose connection is a quick fix.
- [ ] Is only one carrier/band affected or multiple? Multiple carriers = DAS internal issue, not carrier.

## Severity
| Condition | Severity |
|---|---|
| Minor power reduction, coverage slightly degraded | P3 |
| Significant power reduction, coverage impact confirmed | P3 |
| Complete signal loss at POI — full carrier band outage | P2 |

## Escalation path
Carrier cause confirmed → notify carrier per OPS-001. Do not dispatch DAS vendor.
If jumper at POI input is suspected → NOC can request facilities check before opening carrier ticket.
Do not open internal Operations ticket for external signal issues.

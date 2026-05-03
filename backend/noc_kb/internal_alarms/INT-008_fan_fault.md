---
alarm_id: INT-008
category: internal
subcategory: system
severity: major
alarm_name: Fan Fault
tags: [fan, cooling, thermal, auto_shutdown_risk]
---

# Fan Fault

## What this means
A cooling fan has slowed below operational speed or stopped entirely. Active cooling is degraded or lost. Without fan cooling, the equipment will heat up and eventually trigger a High Temperature alarm followed by automatic shutdown. Time to impact depends on ambient temperature and load.

## Most likely causes (ranked)
1. Fan obstruction — cable, debris, or foreign object blocking blade rotation
2. Dust buildup on fan blades causing imbalance and motor strain
3. Fan motor failure — end of life or bearing seizure
4. Power rail issue to the fan — electrical fault

## NOC triage checklist
- [ ] Is High Temperature alarm (INT-007) also active? If yes — escalate immediately, time is critical.
- [ ] What is the current temperature reading? Estimate time to shutdown threshold.
- [ ] Is this a remote, expansion hub, or main hub? Scope of impact depends on node type.
- [ ] Contact facilities to check ambient temperature in the equipment room — high ambient accelerates risk.
- [ ] If accessible, visual inspection — is the fan visibly stopped or obstructed?

## Severity
| Condition | Severity |
|---|---|
| Fan fault only, temperature within normal range | P2 |
| Fan fault + temperature rising | P2 |
| Fan fault + High Temperature alarm co-occurring | P1 |
| Fan fault on main hub or critical zone equipment | P1 |

## Escalation path
Fan fault alone → notify Operations, schedule dispatch within SLA window. Bring replacement fan module.
Fan fault + High Temperature → escalate to P1, immediate response. Contact facilities for HVAC backup. Dispatch with replacement fan and portable cooling unit.
Do not wait for auto-shutdown — proactive intervention prevents service outage.

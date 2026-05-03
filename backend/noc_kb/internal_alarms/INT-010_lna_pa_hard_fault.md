---
alarm_id: INT-010
category: internal
subcategory: rf_performance
severity: critical
alarm_name: LNA / PA Hard Fault
tags: [LNA, PA, amplifier, hardware_failure, lightning, surge]
---

# LNA / PA Hard Fault

## What this means
The Power Amplifier (PA) or Low Noise Amplifier (LNA) in the remote unit has suffered a catastrophic hardware failure. The remote can no longer amplify downlink or uplink signals. RF service in the affected zone is completely lost and will not recover without hardware replacement.

## Most likely causes (ranked)
1. Lightning strike or electrical surge on the antenna or coax path
2. Prolonged overheating fatigue from cooling failure
3. Manufacturing defect — early life failure
4. Sustained overdrive from excessive input power over time
5. Physical impact damage to the remote unit

## NOC triage checklist
- [ ] Is this a single remote or multiple? Multiple simultaneous PA faults = surge/lightning event.
- [ ] Check for surge or lightning activity in the area around the time of the alarm.
- [ ] Was there a recent High Temperature or Fan Fault alarm on this node before the fault?
- [ ] Was there a Downlink Power High alarm (INT-004) preceding this event?
- [ ] Check building lightning protection and grounding records for the IDF.
- [ ] Confirm RF service is completely absent — no signal at all vs. degraded signal.

## Severity
| Condition | Severity |
|---|---|
| Single remote hard fault, non-critical zone | P2 |
| Single remote hard fault, critical zone | P1 |
| Multiple remotes simultaneously — surge event | P1 |

## Escalation path
Always requires hardware replacement — no software or configuration fix is possible.
Notify Operations immediately with remote ID, zone, and suspected cause.
Dispatch requires replacement remote unit. Confirm RMA process with warehouse before dispatch.
If lightning/surge suspected across multiple units — assess full site before ordering single spare. May need multiple RMAs.

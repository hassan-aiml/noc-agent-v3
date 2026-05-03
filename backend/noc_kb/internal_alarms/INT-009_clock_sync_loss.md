---
alarm_id: INT-009
category: internal
subcategory: system
severity: critical
alarm_name: Clock / Sync Loss
tags: [sync, GPS, TDD, clock, 5G, n41, timing, carrier_impact]
---

# Clock / Sync Loss

## What this means
The system has lost its 10MHz or PPS timing reference from the GPS or master clock source. TDD carriers (5G NR bands such as n41, n77, n78) require precise timing synchronization to operate. Loss of sync disables all TDD carrier bands immediately. FDD carriers (B2, B4, B13) are not affected by sync loss and continue operating normally.

## Most likely causes (ranked)
1. GPS antenna failure, obstruction, or physical damage on rooftop
2. GPS sync cable disconnected or damaged between rooftop antenna and hub
3. Master clock module instability or failure
4. GPS signal obstruction — new construction, equipment placed near antenna
5. Sync cable connector corrosion or loose termination

## NOC triage checklist
- [ ] Identify which carriers and bands are affected — TDD bands only, or FDD too?
- [ ] If FDD bands are also down, sync loss is not the sole cause — check for additional faults.
- [ ] Check GPS lock status in NMS — is it unlocked, searching, or showing no antenna?
- [ ] Contact facilities to check rooftop GPS antenna — visible damage, obstruction, or disconnection?
- [ ] Check the sync cable path from rooftop to equipment room for damage or disconnection.
- [ ] Notify affected TDD carrier(s) per OPS-001 — they will see n41/TDD impact immediately.
- [ ] Consider disabling TDD carrier ports in NMS to prevent BTS-side alarms while troubleshooting.

## Severity
| Condition | Severity |
|---|---|
| TDD carrier(s) affected, FDD normal | P1 |
| GPS unlocked — TDD bands down | P1 |
| Full timing loss — all carriers affected | P1 |

## Escalation path
Always P1. Notify Operations and affected TDD carrier(s) immediately per OPS-001.
Dispatch requires technician with GPS antenna spare, sync cable, and compass/line-of-sight check tools.
TDD service will not restore until GPS lock is re-established — no software workaround.

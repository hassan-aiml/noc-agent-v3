---
alarm_id: INT-007
category: internal
subcategory: environment
severity: major
alarm_name: High Temperature
tags: [temperature, thermal, HVAC, overtemp, auto_shutdown_risk]
---

# High Temperature

## What this means
Internal component temperature has exceeded the safe operating threshold (typically above 55°C). Equipment will automatically shut down to prevent permanent damage if temperature continues to rise. Auto-shutdown causes a full service outage on the affected node.

## Most likely causes (ranked)
1. HVAC failure or reduced airflow in IDF/MDF room or ceiling enclosure
2. Dust-blocked air intake or heat sinks — gradual degradation
3. Equipment stacked too tightly with insufficient clearance for airflow
4. Fan Fault on the same unit (check INT-008) — loss of active cooling
5. Ambient temperature rise from building HVAC seasonal issues

## NOC triage checklist
- [ ] Check for Fan Fault alarm (INT-008) on the same node — co-occurring fan fault accelerates thermal risk.
- [ ] What is the current temperature reading vs. the auto-shutdown threshold?
- [ ] Contact facilities to check HVAC status in the affected IDF/MDF room.
- [ ] Is this a single node or multiple nodes in the same room heating up together?
- [ ] Is the equipment in a ceiling space or enclosed cabinet with no active ventilation?
- [ ] Has the temperature been rising gradually (HVAC issue) or spiked suddenly (fan failure)?
- [ ] Estimate time to auto-shutdown based on current rate of rise — set a watch timer.

## Severity
| Condition | Severity |
|---|---|
| Temperature elevated, well below shutdown threshold | P3 |
| Temperature approaching shutdown threshold (within 5°C) | P2 |
| Fan Fault co-occurring — accelerated risk | P2 |
| Critical zone equipment at risk | P1 |
| Auto-shutdown imminent or already triggered | P1 |

## Escalation path
Contact facilities immediately — HVAC fix is faster than any equipment intervention.
Notify Operations with node ID, current temperature, shutdown threshold, and rate of rise.
If auto-shutdown has already triggered → treat as service outage, escalate to P1.
Dispatch with portable fan unit for temporary cooling if HVAC repair will take more than 2 hours.

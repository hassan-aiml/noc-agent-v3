---
alarm_id: INT-002
category: internal
subcategory: power
severity: critical
alarm_name: Power Supply Failure
tags: [power, PSU, DC, circuit, downstream_impact]
---

# Power Supply Failure

## What this means
Loss of internal DC voltage required to power internal modules. When a hub or remote loses power, all downstream nodes go dark simultaneously — optical links drop, RF service stops, and management connectivity is lost. A main hub PSU failure is a full site outage.

## Most likely causes (ranked)
1. External circuit breaker trip at the IDF/MDF panel
2. PSU hardware failure (internal capacitor or rectifier failure)
3. Unstable building utility power — brownout or surge
4. Overloaded circuit shared with other building systems
5. Cooling failure leading to thermal protection shutdown

## NOC triage checklist
- [ ] Check NMS for scope — single remote, expansion hub, or main hub?
- [ ] Are all alarms on this node firing simultaneously? Sudden multi-alarm burst = power loss.
- [ ] Contact facilities to check the circuit breaker at the IDF/MDF serving this equipment.
- [ ] Check building UPS or generator status if applicable.
- [ ] Is there a High Temperature or Fan Fault alarm on the same node? Could be thermal shutdown.
- [ ] Verify AC input voltage at the equipment if accessible remotely.
- [ ] Do NOT assume hardware failure until AC input is confirmed present.

## Severity
| Condition | Severity |
|---|---|
| Single remote power loss, non-critical zone | P2 |
| Single remote power loss, critical zone | P1 |
| Expansion hub power loss | P1 |
| Main hub power loss — full site outage | P1 |

## Escalation path
Check building power first — contact facilities before dispatching a DAS vendor.
If AC input is confirmed present and equipment is still dark → internal PSU hardware failure, notify Operations for vendor dispatch with spare PSU.
If AC input is absent → facilities issue, escalate to building engineering. Do not dispatch DAS vendor until power is restored.

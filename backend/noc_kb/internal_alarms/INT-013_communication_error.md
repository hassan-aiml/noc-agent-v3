---
alarm_id: INT-013
category: internal
subcategory: system
severity: critical
alarm_name: Communication Error
tags: [management, unreachable, hub, remote, downstream_impact]
---

# Communication Error

## What this means
Equipment has lost management plane communication. The NOC can no longer monitor or control the affected node. When an expansion hub or remote loses communication, all downstream nodes also become unreachable. This is a management plane loss — RF service may or may not be affected depending on the root cause.

## Most likely causes (ranked)
1. Power loss to the node — no power means no management
2. Optical link loss — management runs over the same fiber as RF
3. Management network or IP connectivity issue at the head-end
4. Faulty equipment requiring hardware replacement
5. Software crash on the management module — may recover with reboot

## NOC triage checklist
- [ ] Check for Power Supply Failure (INT-002) or Optical Link Outage (INT-001) on the same node — these cause communication loss as a secondary effect.
- [ ] Is this a single node or is the management loss cascading to all downstream nodes?
- [ ] Can you ping the management IP of the affected node?
- [ ] Is the management network itself reachable — can you reach other nodes on the same segment?
- [ ] If power and optical are confirmed OK, attempt a remote reboot via NMS if available.
- [ ] Check if the alarm timestamp coincides with a power event or maintenance activity.

## Severity
| Condition | Severity |
|---|---|
| Single remote unreachable, RF service unknown | P2 |
| Single remote unreachable, RF confirmed down | P1 |
| Expansion hub unreachable — all downstream blind | P1 |
| Main hub unreachable — full site management loss | P1 |

## Escalation path
Investigate power and optical first — these are the most common root causes and resolve the communication loss as a byproduct.
If power and optical are healthy → notify Operations, attempt remote reboot. If no recovery, dispatch for hardware inspection.
Do not count communication loss nodes as confirmed service outages until RF service is verified independently.

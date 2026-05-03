---
alarm_id: INT-006
category: internal
subcategory: rf_performance
severity: major
alarm_name: Uplink Noise / RSSI Rise
tags: [uplink, noise, RSSI, interference, PIM, LNA]
---

# Uplink Noise / RSSI Rise

## What this means
The noise floor in the uplink path is elevated, desensitizing the BTS receiver. Users may experience dropped calls and poor data throughput even if DL coverage appears normal. Carriers are particularly sensitive to this — uplink noise directly impacts their network performance metrics.

## Most likely causes (ranked)
1. External interference source near an antenna (other transmitters, equipment)
2. Passive Intermodulation (PIM) from loose connectors or damaged passives — see INT-010
3. Faulty Low Noise Amplifier (LNA) in the remote unit
4. Ingress interference through damaged or poorly shielded coax
5. Near-field interference from building systems (elevators, lighting, HVAC variable drives)

## NOC triage checklist
- [ ] Is this a single remote or multiple? Multiple remotes = interference source is upstream or building-wide.
- [ ] Check for PIM Detection alarm (INT-010) on the same node — frequently co-occurs.
- [ ] Is there any new equipment installed near the antenna in the last 30 days?
- [ ] Check uplink noise floor reading in NMS — how far above baseline?
- [ ] Has any passive work (connectors, cables) been done recently on this antenna run?
- [ ] Notify the affected carrier(s) — they will want to know and may have their own diagnostic data.

## Severity
| Condition | Severity |
|---|---|
| Single remote, moderate noise rise | P3 |
| Single remote, significant noise — carrier impact confirmed | P2 |
| Multiple remotes affected | P2 |
| Full sector noise rise — carrier escalating | P1 |

## Escalation path
Notify affected carrier(s) per OPS-001 — uplink noise directly impacts their KPIs and SLA.
Internal cause suspected → notify Operations. Dispatch requires RF technician with PIM analyzer and LNA spare.
If PIM is confirmed source → passive repair first (connectors, jumpers) before replacing active equipment.

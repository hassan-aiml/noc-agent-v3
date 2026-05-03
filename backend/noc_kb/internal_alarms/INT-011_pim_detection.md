---
alarm_id: INT-011
category: internal
subcategory: rf_performance
severity: major
alarm_name: PIM Detection
tags: [PIM, passive, intermodulation, uplink, connector, antenna]
---

# PIM Detection

## What this means
Passive Intermodulation (PIM) is detected in the antenna path. PIM is generated when two or more high-power signals mix in a non-linear passive component (loose connector, damaged cable, corroded metal contact) and produce interference products that fall in the uplink receive band. This degrades uplink sensitivity and impacts carrier KPIs.

## Most likely causes (ranked)
1. Loose or improperly torqued connector — most common cause
2. Metal-on-metal contact in the antenna path (rusty bolt effect — oxidized hardware near antenna)
3. Damaged coax cable with compromised shielding
4. Faulty or aging passive component (splitter, coupler, diplexer)
5. Damaged antenna with internal conductor issue

## NOC triage checklist
- [ ] Check for Uplink Noise / RSSI Rise alarm (INT-006) on the same node — PIM and uplink noise frequently co-occur.
- [ ] Notify affected carrier(s) — they will see uplink degradation on their network.
- [ ] Is this a single remote or multiple? Multiple = PIM source is in the shared passive path upstream.
- [ ] Any recent maintenance on the antenna, coax, or connectors in this zone?
- [ ] Any construction or renovation near the antenna that could have disturbed hardware?
- [ ] Check connector torque on the antenna and remote ports — loose connections are the most common fix.

## Severity
| Condition | Severity |
|---|---|
| PIM detected, mild uplink impact | P3 |
| PIM confirmed, carrier uplink degradation | P2 |
| PIM with Uplink Noise alarm co-occurring | P2 |
| Multiple remotes affected — carrier escalating | P1 |

## Escalation path
Notify affected carrier(s) per OPS-001 — PIM directly impacts their uplink KPIs.
Dispatch requires RF technician with PIM analyzer, torque wrench, and passive component spares (connectors, jumpers).
Attempt passive repair first — re-torquing connectors resolves a significant portion of PIM cases without hardware replacement.

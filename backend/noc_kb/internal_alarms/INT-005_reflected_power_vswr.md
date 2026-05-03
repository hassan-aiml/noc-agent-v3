---
alarm_id: INT-005
category: internal
subcategory: rf_performance
severity: major
alarm_name: Reflected Power (VSWR)
tags: [VSWR, antenna, coax, connector, passive, reflected_power]
---

# Reflected Power (VSWR)

## What this means
High energy is reflecting back from the antenna system into the remote unit instead of radiating. This means coverage is degraded in the affected zone, and the reflected power can damage the remote's amplifier over time if not resolved.

## Most likely causes (ranked)
1. Pinched or crushed coax jumper at the antenna edge or ceiling entry point
2. Water ingress in 4.3-10 or N-type connectors — common in high-humidity zones
3. Faulty or physically damaged antenna (dropped, impacted, cracked radome)
4. Loose connector not fully torqued — intermittent contact
5. Wrong impedance adapter or barrel connector in the RF path

## NOC triage checklist
- [ ] Is this a single remote or multiple? Multiple remotes with VSWR = passive path issue upstream of split.
- [ ] Any recent construction, renovation, or ceiling work in the affected zone?
- [ ] Check the coax jumper at the remote antenna port — visible kink, pinch, or damage?
- [ ] Inspect connectors for corrosion, water staining, or loose coupling.
- [ ] Check antenna for physical damage — especially in high-traffic areas.
- [ ] Was the antenna recently moved or remounted during maintenance?

## Severity
| Condition | Severity |
|---|---|
| Single remote, moderate VSWR, non-critical zone | P3 |
| Single remote, high VSWR — amplifier damage risk | P2 |
| Single remote, critical zone | P2 |
| Multiple remotes, passive path fault | P2 |

## Escalation path
Internal cause confirmed → notify Operations with remote ID, VSWR reading, and zone description.
Dispatch requires RF technician with passive kit: coax jumpers, connectors, torque wrench, antenna spare.
Active electronics (remote unit) are NOT required for first dispatch — always attempt passive path repair first.

---
alarm_id: INT-004
category: internal
subcategory: rf_performance
severity: major
alarm_name: Downlink Power High
tags: [downlink, RF, overdrive, gain, hardware_damage_risk]
---

# Downlink Power High

## What this means
RF output from the remote is too high, above the safe operating limit. The amplifier is being overdriven, which risks permanent hardware damage to the remote unit and may cause interference to the macro network outside the building.

## Most likely causes (ranked)
1. System gain set too high in NMS — operator configuration error
2. Faulty remote amplifier module with uncontrolled gain
3. Optical over-saturation driving excessive signal into the remote
4. Input attenuator removed or bypassed during maintenance and not restored

## NOC triage checklist
- [ ] Check NMS gain settings on this remote — was there a recent configuration change?
- [ ] Check optical input power at the remote — is it within spec?
- [ ] Is EXT-002 (Source Overdrive) also active? If yes, the excess power is coming from the POI.
- [ ] Is this a single remote or multiple? Multiple with same readings = upstream gain issue.
- [ ] What is the actual DL output power reading vs. the maximum threshold?
- [ ] Has any maintenance been performed on the RF path (attenuators, splitters) recently?

## Severity
| Condition | Severity |
|---|---|
| Single remote, slightly above threshold | P2 |
| Single remote, significantly above threshold — hardware damage risk | P1 |
| Multiple remotes overdriving simultaneously | P1 |

## Escalation path
Configuration error confirmed → NOC corrects gain in NMS immediately. Log the change.
Hardware fault suspected → notify Operations. Do not leave the unit running at high power — risk of permanent damage. Dispatch requires RF technician with spare amplifier module.
If EXT-002 is active simultaneously → escalate to carrier per OPS-001 first before adjusting internal gain.

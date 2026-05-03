---
alarm_id: INT-012
category: internal
subcategory: optical_performance
severity: minor
alarm_name: Optical Over-Saturation
tags: [optical, saturation, fiber, attenuator, SFP]
---

# Optical Over-Saturation

## What this means
The optical power level at the receiver is too high. Excessive optical power causes bit errors in the optical link and can damage the SFP receiver module over time. Service may be intermittent or degraded even though the optical link appears connected.

## Most likely causes (ranked)
1. Missing optical attenuator on a very short fiber run
2. Fiber span is shorter than the minimum required for the installed SFP type
3. Incorrect high-power laser SFP installed for a short-range application
4. Attenuator removed during maintenance and not replaced

## NOC triage checklist
- [ ] Check the optical receive power reading in NMS — how far above the maximum receive threshold?
- [ ] What is the fiber span length between hub and remote? Very short spans are the most common cause.
- [ ] Was any maintenance performed on the optical path recently — SFP swapped, fiber rerouted?
- [ ] Is the correct SFP type installed for the fiber span length?
- [ ] Is an inline optical attenuator present on this run? Check the fiber documentation.

## Severity
| Condition | Severity |
|---|---|
| Slightly above threshold, no service impact | P3 |
| Significantly above threshold — bit errors or intermittent service | P3 |
| Hardware damage risk — receiver near saturation limit | P2 |

## Escalation path
Low urgency but should be resolved before causing SFP damage.
Notify Operations with fiber run ID, optical power reading, and span length.
Dispatch requires technician with inline optical attenuators. No RMA required in most cases.

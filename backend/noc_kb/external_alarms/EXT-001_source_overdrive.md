---
alarm_id: EXT-001
category: external
subcategory: rf_performance
severity: critical
alarm_name: Source Overdrive
tags: [POI, overdrive, BTS, carrier, hardware_damage_risk, external]
---

# Source Overdrive

## What this means
RF input from the carrier BTS at the POI exceeds the safe operating threshold of the DAS hardware. The POI module and downstream equipment are being overdriven. This risks permanent damage to the POI module and can cause DL Power High alarms on all downstream remotes. This is an external carrier issue — the DAS is the victim, not the cause.

## CRITICAL — Do not adjust DAS gain to compensate
The correct response is to notify the carrier and have them reduce BTS output power or adjust the POI attenuation setting. Do not reduce DAS gain to mask the problem — this treats the symptom and leaves the hardware at risk.

## Most likely causes (ranked)
1. Carrier BTS power increase — intentional or unintentional
2. Incorrect POI attenuation setting — too little attenuation for the BTS power level
3. Wrong POI module type installed — insufficient input power handling for this carrier

## NOC triage checklist
- [ ] Which POI is affected — identify the carrier and band precisely.
- [ ] What is the measured input power vs. the POI threshold?
- [ ] Is DL Power High (INT-004) firing on downstream remotes? If yes, confirms overdrive is propagating.
- [ ] Has the carrier recently performed BTS work or power optimization on this sector?
- [ ] Check POI attenuation setting in NMS — was it changed recently?
- [ ] Do NOT reduce DAS internal gain as a workaround.

## Severity
| Condition | Severity |
|---|---|
| Input power above threshold, hardware not yet at risk | P2 |
| Input power significantly above threshold — hardware damage risk | P1 |
| Downstream DL Power High alarms co-occurring | P1 |

## Escalation path
Always notify the carrier per OPS-001 immediately — this is their BTS output issue.
Open an external carrier ticket. Provide measured input power, POI ID, and carrier/band.
Do not dispatch DAS vendor for this alarm — no DAS hardware repair is required.
If hardware damage is suspected after sustained overdrive → notify Operations for POI module inspection.

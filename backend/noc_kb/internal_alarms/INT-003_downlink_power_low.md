---
alarm_id: INT-003
category: internal
subcategory: rf_performance
severity: major
alarm_name: Downlink Power Low
tags: [downlink, RF, coverage, POI, misdiagnosis_risk]
---

# Downlink Power Low

## What this means
RF output from the remote is below the expected threshold. Coverage is degraded — users see reduced signal, dropped calls, and slow data. The affected zone may fall below the coverage level specified in the RF design.

## CRITICAL — Most common misdiagnosis in DAS NOC operations
This alarm is frequently caused by an external issue — low or absent DL input at the POI from the carrier BTS — not a DAS hardware fault.

Always check EXT-001 (Source Underpower) before assuming the DAS is at fault.

If EXT-001 is also active: notify the carrier. Do NOT dispatch a DAS vendor. This is the single biggest source of unnecessary truck rolls.

If all remotes under a hub show this alarm simultaneously, the cause is upstream — POI or hub — not individual remote hardware.

## Most likely causes (ranked)
1. Low or no DL input at POI — external carrier issue (check EXT-001 first)
2. Recent gain configuration change in NMS
3. Attenuator incorrectly inserted into RF path during maintenance
4. Faulty amplifier module or gain card in remote
5. Partial fiber degradation reducing signal level without triggering full optical LOS

## NOC triage checklist
- [ ] Is EXT-001 (Source Underpower) also active? If yes — notify carrier, do NOT dispatch vendor.
- [ ] Is this one remote or multiple remotes simultaneously? Multiple = upstream suspect.
- [ ] Any maintenance on this site in the last 48–72 hours?
- [ ] Any NMS gain configuration changes recently? Check the change log.
- [ ] What is the actual DL output power reading vs. threshold in NMS?
- [ ] Check DL input level at the hub POI port — is it within spec?

## Severity
| Condition | Severity |
|---|---|
| Single remote, minor degradation, non-critical zone | P3 |
| Single remote, critical zone | P2 |
| Multiple remotes, building-wide degradation | P2 |
| No DL output at all / full coverage loss | P1 |

## Escalation path
External cause confirmed → notify carrier per OPS-001. Do not open internal Operations ticket.
Internal cause confirmed → notify Operations with remote ID, DL power reading, POI input level, and recent maintenance log. Dispatch requires RF technician with power meter and spare amplifier module.

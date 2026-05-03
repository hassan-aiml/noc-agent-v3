---
alarm_id: INT-001
category: internal
subcategory: optical_performance
severity: critical
alarm_name: Optical Link Outage
tags: [fiber, optical, LOS, hub, remote, downstream_impact]
---

# Optical Link Outage

## What this means
The head-end and remote have lost the physical light handshake or framing on the optical link. No optical signal = no RF service downstream. Every remote fed by this fiber run is completely out of service for all carriers and all bands.

## Most likely causes (ranked)
1. Fiber break or tight kink in the cable path
2. Dirty or damaged SFP/LC connectors at hub or remote
3. Remote unit power loss (no power = no optical response)
4. Faulty SFP transceiver module
5. Excessive fiber bend radius causing signal loss

## NOC triage checklist
- [ ] Is this a single remote or multiple remotes on the same fiber run?
- [ ] Check NMS for PSU or power alarms on the same node — power loss can look like optical LOS.
- [ ] Was there any maintenance, construction, or renovation activity in the affected zone?
- [ ] Check optical power reading at hub port — is Tx present but Rx absent, or both absent?
- [ ] Inspect patch panel and fiber tray at IDF for visible damage or disconnected jumpers.
- [ ] If Tx power is present at hub but Rx is absent at remote — fiber path is the suspect.
- [ ] If both Tx and Rx are absent — check power to the remote first.

## Severity
| Condition | Severity |
|---|---|
| Single remote offline, non-critical zone | P2 |
| Single remote offline, critical zone | P1 |
| Multiple remotes / entire hub branch offline | P1 |
| Main hub optical link lost — full site outage | P1 |

## Escalation path
Confirm scope (how many remotes affected) before escalating.
Internal cause confirmed → notify Operations with fiber run ID, affected remote list, optical power readings, and any maintenance log entries. Dispatch requires fiber technician with OTDR and spare jumpers.
Do NOT dispatch without confirming power is present at the remote first — eliminates unnecessary truck rolls.

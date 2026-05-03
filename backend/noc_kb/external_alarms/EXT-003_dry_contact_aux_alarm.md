---
alarm_id: EXT-003
category: external
subcategory: system
severity: variable
alarm_name: Dry Contact / Aux Alarm
tags: [dry_contact, aux, UPS, door, sensor, external, environmental]
---

# Dry Contact / Aux Alarm

## What this means
An external sensor connected to the DAS dry contact input port has triggered. The DAS hardware is functioning — this alarm is a notification from an external building or environmental system. Severity depends entirely on what triggered it.

## Common trigger sources
- Door open / tamper sensor — maintenance access or unauthorized entry
- UPS running on battery — building power issue
- External leak or water sensor — flooding risk
- Smoke or fire sensor — evacuation risk
- Generator running — utility power failure

## NOC triage checklist
- [ ] Identify which dry contact input triggered and what sensor is mapped to it — check site documentation.
- [ ] Is the trigger expected? Check for scheduled maintenance or access requests.
- [ ] If UPS on battery — check for Power Supply alarms on DAS equipment. Building power event may cause cascading alarms.
- [ ] If door/tamper — verify with facilities or security whether access was authorized.
- [ ] If smoke/fire/water — treat as life safety event, notify building management immediately.
- [ ] How long has the contact been triggered? Short duration = likely maintenance. Sustained = investigate.

## Severity
| Condition | Severity |
|---|---|
| Door open — expected maintenance access | P3 |
| UPS on battery — building power event | P2 |
| UPS on battery + DAS power alarms co-occurring | P1 |
| Smoke / fire / water sensor triggered | P1 |
| Unknown trigger — no documentation | P2 |

## Escalation path
Life safety triggers (smoke, fire, water) → notify building management immediately, treat as P1 regardless of DAS status.
UPS on battery → monitor DAS equipment for power alarms, notify facilities.
Door/tamper → verify with facilities or security.
Unknown trigger → notify Operations, review site documentation, schedule inspection.

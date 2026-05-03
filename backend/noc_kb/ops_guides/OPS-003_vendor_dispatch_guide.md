---
doc_id: OPS-003
category: ops_guide
title: Vendor dispatch guide and standard first-trip kit
tags: [vendor, dispatch, truck_roll, materials, first_trip, scope_of_work, servicenow]
---

# Vendor dispatch guide and standard first-trip kit

## When vendor dispatch is required
Vendor dispatch is authorized by Operations only. NOC does not dispatch directly.

Typical conditions requiring vendor dispatch:
- INT-001 Optical Link Outage — fiber break or connector fault requiring physical repair
- INT-002 Power Supply Failure — PSU hardware replacement after AC input confirmed present
- INT-003 Downlink Power Low — hardware fault confirmed after external cause ruled out
- INT-005 Reflected Power (VSWR) — passive path inspection and repair
- INT-007 High Temperature / INT-008 Fan Fault — fan replacement or cooling intervention
- INT-009 Clock / Sync Loss — GPS antenna or sync cable inspection and replacement
- INT-010 LNA / PA Hard Fault — remote unit replacement (always requires RMA confirmation first)
- INT-011 PIM Detection — passive path inspection with PIM analyzer
- INT-012 Optical Over-Saturation — optical attenuator installation
- Any P1 alarm that Operations cannot resolve remotely within 1 hour

## Do NOT dispatch vendor for external alarms
EXT-001 and EXT-002 are carrier BTS issues. No DAS hardware repair is required.
Notify carrier per OPS-001. Dispatch only if POI module damage is confirmed after sustained overdrive.

---

## Vendor contacts

<!-- ============================================================
     DEMO DATA — All vendor company names, contacts, phone numbers,
     and SLA terms below are fictitious placeholders for demo
     purposes. Replace with your actual preferred vendor list
     and their contracted response times before production use.
     ============================================================ -->

### Primary vendor — Apex Field Services
- Dispatch line (24/7): (214) 555-0611
- Email: dispatch@apexfield-demo.com
- Primary contact: Kevin Marsh | (214) 555-0624
- Coverage area: DFW metro, north Texas
- Contracted response: 4 hours for P1, next business day for P2/P3
- Portal: https://dispatch.apexfield-demo.com

### Secondary vendor — NovaTech Wireless Solutions
- Dispatch line (business hours): (972) 555-0732
- After-hours: (972) 555-0745
- Email: service@novatech-demo.com
- Primary contact: Lisa Huang | (972) 555-0758
- Coverage area: DFW metro, south Texas
- Contracted response: 6 hours for P1, 48 hours for P2/P3
- Use when: Apex is unavailable or site is outside their coverage area

### Vendor escalation — Operations Engineer authorizes
If neither vendor can meet P1 response time, Operations Engineer escalates to Operations Manager for alternate vendor authorization.

<!-- END DEMO DATA — Vendor contacts -->

---

## Standard first-trip kit — every vendor visit

These are low-cost passive items. Every vendor truck must carry them on every dispatch regardless of alarm type. There is no excuse for a failed first-trip due to a missing passive item.

### Fiber and optical
- Fiber inspection scope with one-click cleaner — cleans fix 50%+ of optical LOS faults
- Spare SC/APC jumpers: 1m, 3m, 5m (minimum 2 of each)
- Spare LC/UPC jumpers: 1m, 3m, 5m (minimum 2 of each)
- Spare SFP transceivers: single-mode 1310nm (confirm wavelength before dispatch)
- Inline optical attenuators: 5 dB, 10 dB, 15 dB (for INT-012 Optical Over-Saturation)
- Optical power meter

### RF and antenna
- 50-ohm terminator caps — N-type (minimum 10 units)
- 50-ohm terminator caps — DIN 7/16 (minimum 5 units)
- Fixed attenuators — N-type: 3 dB, 6 dB, 10 dB (one of each)
- Torque wrench calibrated for N-connectors (20–25 in-lbs) — required for INT-005 and INT-011
- Spare N-type male connectors and short RG-316 jumpers
- Basic VSWR bridge or cable/antenna analyzer

### Power and general
- Assorted fuses — DC and AC (match common hub models in portfolio)
- Multimeter
- PoE tester cable

### GPS and sync
- Spare GPS antenna (patch type, standard — always carry one, inexpensive)
- Spare GPS antenna coax (RG-6 or LMR-195 with appropriate connectors)

### Access and tools
- Laptop with VPN and NMS read access (view-only for field techs)
- Flashlight and head lamp
- Phone with GPS signal strength app to verify sky view at GPS antenna location
- Site access credentials or building management contact (provided in dispatch work order)

### Alarm-specific active equipment — bring only when authorized by Operations
These require RMA confirmation before dispatch. Do not bring speculatively.

| Alarm | Active equipment to bring |
|---|---|
| INT-001 Optical Link Outage | Spare SFP (confirm type) |
| INT-002 Power Supply Failure | Spare PSU module (confirm model) |
| INT-008 Fan Fault | Spare fan module (confirm model) |
| INT-010 LNA / PA Hard Fault | Spare remote unit (RMA confirmed) |
| INT-013 Communication Error | Spare management module if power and optical confirmed healthy |

---

## Scope of work template — Operations fills this out for every dispatch

Operations creates the vendor work order in ServiceNow and includes all of the following. An incomplete work order is returned to Operations before dispatch proceeds.

Required fields in every work order:
1. Site name, full address, and building access instructions
2. Alarm ID and alarm name from this KB
3. Severity (P1 / P2 / P3) and contracted response time
4. Specific remote or hub ID affected (from NMS)
5. What Operations already confirmed remotely — power status, management ping, NMS reading, optical power
6. Specific task for the vendor — do not say "investigate"; say "inspect fiber span from HUB-01 port 4 to RU-08, clean connectors, replace jumper if LOS persists"
7. Materials to bring — reference standard kit above plus alarm-specific items
8. On-site contact (building manager or facilities — name and number)
9. Operations Engineer callback number for vendor questions on site
10. ServiceNow ticket number to log work against

<!-- ============================================================
     DEMO DATA — ServiceNow work order queue and instance below
     are fictitious. Replace with actual configuration.
     ============================================================ -->
ServiceNow work order queue: OPS-VendorDispatch
ServiceNow instance: https://texnetdas-demo.service-now.com
Vendor SLA tracking: Auto-triggered on work order creation
<!-- END DEMO DATA -->

---

## Dispatch authorization matrix

| Severity | Who can authorize dispatch | ServiceNow approval required |
|---|---|---|
| P1 | On-Call Operations Engineer | No — verbal authorization, log in ticket afterward |
| P2 | On-Call Operations Engineer | Yes — ServiceNow approval workflow |
| P3 | Operations Manager (business hours) | Yes — ServiceNow approval workflow |

---

## Post-dispatch process

After the vendor completes work on site:
1. Vendor submits completed work order: work performed, materials used, time on site, outcome
2. Operations Engineer confirms alarm cleared in NMS
3. ServiceNow ticket updated with resolution details
4. If first-trip did not resolve — Operations Engineer reviews, updates scope, schedules return visit
5. If passive items were missing from standard kit — log a vendor performance note in ServiceNow

---

## First-trip failure analysis

If a vendor returns without resolving the issue, Operations Engineer must document in ServiceNow:
- What was found on site
- What was attempted
- Why it was not resolved
- Updated scope of work for return visit

<!-- ============================================================
     DEMO DATA — Vendor performance tracking thresholds below
     are fictitious estimates. Replace with actual vendor KPI
     requirements from your vendor contracts.
     ============================================================ -->
Target first-trip resolution rate: 80% or higher
Vendors below 70% over 90-day rolling period: escalate to Operations Manager for vendor review
<!-- END DEMO DATA -->

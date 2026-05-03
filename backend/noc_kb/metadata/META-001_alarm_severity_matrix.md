---
doc_id: META-001
category: metadata
doc_name: Alarm Severity Matrix
version: 2.0
---

# Alarm Severity Matrix

## Severity definitions

| Level | Definition | Response Target |
|---|---|---|
| P1 — Critical | Service outage or hardware damage imminent. Carrier impact or full zone loss. | Immediate — escalate within 15 minutes |
| P2 — Major | Service degraded or at risk. Single zone impact or hardware fault requiring dispatch. | Escalate within 1 hour |
| P3 — Minor | Degradation noted, no immediate service impact. Schedule for resolution. | Resolve within SLA window |

---

## Alarm severity reference

| Alarm ID | Alarm Name | Base Severity | Escalates to P1 When |
|---|---|---|---|
| INT-001 | Optical Link Outage | P2 | Multiple remotes / hub branch / main hub affected |
| INT-002 | Power Supply Failure | P2 | Hub affected, critical zone, or main hub |
| INT-003 | Downlink Power Low | P3 | Multiple remotes, critical zone, or complete signal loss |
| INT-004 | Downlink Power High | P2 | Significantly above threshold — hardware damage risk |
| INT-005 | Reflected Power (VSWR) | P3 | High VSWR with amplifier damage risk or critical zone |
| INT-006 | Uplink Noise / RSSI Rise | P3 | Multiple remotes or carrier escalating |
| INT-007 | High Temperature | P3 | Approaching auto-shutdown threshold or fan fault co-occurring |
| INT-008 | Fan Fault | P2 | Fan fault + High Temperature alarm co-occurring |
| INT-009 | Clock / Sync Loss | P1 | Always P1 — TDD carrier service lost |
| INT-010 | LNA / PA Hard Fault | P2 | Critical zone or multiple units — surge event |
| INT-011 | PIM Detection | P3 | Multiple remotes or carrier escalating |
| INT-012 | Optical Over-Saturation | P3 | Hardware damage risk |
| INT-013 | Communication Error | P2 | Hub unreachable, main hub, or RF service confirmed down |
| EXT-001 | Source Overdrive | P2 | Hardware damage risk or downstream DL Power High co-occurring |
| EXT-002 | Source Underpower | P3 | Complete signal loss at POI |
| EXT-003 | Dry Contact / Aux Alarm | Variable | Life safety trigger (smoke/fire/water) or UPS + DAS power alarms |

---

## Severity escalation rules

1. **Scope escalation** — any alarm that affects a hub or multiple remotes simultaneously escalates one level above its base single-remote severity
2. **Zone escalation** — any alarm in a critical zone (Security Center, Emergency Operations, Life Safety) escalates one level
3. **Co-occurrence escalation** — Fan Fault + High Temperature = P1 regardless of individual severity
4. **Alarm type override** — INT-009 (Clock/Sync Loss), EXT-001 (Source Overdrive with damage risk) are always P1 regardless of scope
5. **External alarms** — EXT alarms do not dispatch DAS vendor. Carrier notification always precedes any internal action.

---

## Classification guide

| Classification | Meaning | Action |
|---|---|---|
| Internal | DAS hardware or configuration issue — 3PO responsibility | Open Operations ticket, consider vendor dispatch |
| External | Carrier BTS or signal issue — carrier responsibility | Notify carrier per OPS-001, do NOT dispatch DAS vendor |

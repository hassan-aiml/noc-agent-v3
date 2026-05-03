---
doc_id: OPS-001
category: ops_guide
title: Carrier notification procedure for external alarms
tags: [carrier, notification, escalation, external, POI, procedure]
---

# Carrier notification procedure

## When to notify a carrier
Notify the carrier for these external alarms:
- EXT-001: Source Overdrive — RF input from carrier BTS exceeds safe threshold at POI
- EXT-002: Source Underpower — RF input from carrier is below commissioned baseline at POI
- EXT-003: Dry Contact / Aux Alarm — only when UPS on battery or building power event affects carrier service

Also notify the carrier for these internal alarms when carrier service is confirmed impacted:
- INT-006: Uplink Noise / RSSI Rise — uplink degradation directly impacts carrier KPIs
- INT-011: PIM Detection — PIM impacts carrier uplink sensitivity

## Do NOT notify carrier for internal alarms
INT-001 through INT-013 are our responsibility unless carrier service impact is confirmed.
Do not involve the carrier unless directed by Operations or carrier impact is confirmed.

## What to tell the carrier NOC
1. Site name and address
2. DAS system identifier if the carrier has one
3. Alarm ID and name from this KB
4. Time alarm first appeared
5. Current power level reading if available from NMS
6. Impact description — "No downlink coverage in building" or "DL coverage degraded on [bands]"
7. Your name and callback number

---

## Carrier contact information

<!-- ============================================================
     DEMO DATA — All carrier names, contact persons, phone numbers,
     and portal URLs below are fictitious placeholders for demo
     purposes. Replace with actual carrier contact information
     per your carrier agreements before using in production.
     ============================================================ -->

### Carrier A — Vertex Wireless
- NOC (24/7): 1-800-555-0141 | noc-escalations@vertexwireless-demo.com
- Ticket portal: https://portal.vertexwireless-demo.com/noc
- Account manager: Sandra Okafor | s.okafor@vertexwireless-demo.com | (214) 555-0182
- Escalation — if no NOC response in 30 min: Marcus Webb, Director Network Operations | (214) 555-0199
- Preferred contact method: Phone first, then portal ticket. Always get a ticket number.

### Carrier B — PeakCell Networks
- NOC (24/7): 1-800-555-0263 | noc@peakcell-demo.com
- Ticket portal: https://noc.peakcell-demo.com/tickets
- Account manager: James Tran | j.tran@peakcell-demo.com | (469) 555-0217
- Escalation — if no NOC response in 30 min: Diane Holloway, VP Network Reliability | (469) 555-0244
- Preferred contact method: Portal ticket first for P2. Phone for P1.

### Carrier C — Meridian Mobile
- NOC (24/7): 1-888-555-0374 | noc-support@meridianmobile-demo.com
- Ticket portal: https://support.meridianmobile-demo.com
- Account manager: Carlos Ruiz | c.ruiz@meridianmobile-demo.com | (972) 555-0331
- Escalation — if no NOC response in 30 min: Patricia Ng, Senior Network Engineer | (972) 555-0358
- Preferred contact method: Phone only for P1. Portal for P2 and below.

<!-- END DEMO DATA — Carrier contacts -->

---

## Notification SLA by severity

<!-- ============================================================
     DEMO DATA — SLA timelines below are reasonable estimates for
     a 3PO neutral host operator based on industry norms.
     Replace with actual SLA terms from your carrier contracts.
     ============================================================ -->

| Alarm Severity | Notify Carrier Within | Follow Up If No Response |
|---|---|---|
| P1 — Full building outage (all bands, all carriers) | 15 minutes of alarm confirmation | 30 min — escalate to carrier account manager |
| P1 — Full outage, single carrier, all bands | 15 minutes | 30 min — escalate to carrier account manager |
| P2 — Partial outage or degraded service | 30 minutes | 60 min — escalate to carrier account manager |
| P3 — Minor / single band / informational | Within 4 hours during business hours | Next business day |

<!-- END DEMO DATA — SLA timelines -->

---

## Phone notification script — P1

"This is [your name] calling from TexNet DAS NOC. I am calling to report a P1 alarm at [site name and address]. We are seeing [no downlink input / overdrive] from your network at our Point of Interface. Alarm ID [EXT-001 or EXT-002], first appeared at [time]. [All bands / n41 band] affected. Our DAS has confirmed the issue is at the POI — this appears to be a BTS or RAN issue on your end. Please open a ticket and advise. Our callback number is [your number]."

## Portal ticket format

Subject: [SITE NAME] — DAS POI [Signal Loss / Overdrive] — [ALARM ID] — [DATE TIME]
Priority: Match to P1 / P2 / P3
Description: alarm ID, site address, bands affected, POI power reading, alarm start time

---

## What to document in ServiceNow

Create or update the ServiceNow incident after every carrier notification. Record:
- Carrier notified (name and NOC agent)
- Time of notification
- Carrier ticket number
- Agreed resolution timeline if provided
- Time alarm cleared and service restored
- Whether escalation path was triggered

<!-- ============================================================
     DEMO DATA — ServiceNow instance and queue names below are
     fictitious. Replace with your actual ServiceNow instance URL
     and queue configuration before using in production.
     ============================================================ -->
ServiceNow instance: https://texnetdas-demo.service-now.com
Queue for external alarms: NOC-External-Carrier
Queue for internal alarms: NOC-Internal-DAS
<!-- END DEMO DATA — ServiceNow -->

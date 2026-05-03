"""
correlation_engine.py
5-level severity: P1 (Critical) → P2 (Major) → P3 (Minor) → P4 (Warning) → P5 (Informational)
Alarm-type first, then scope and zone.
Confirmed by Hassan 2026-04-28.
"""
from dataclasses import dataclass, field
from typing import Optional
from topology_manager import TopologyManager


# ── Always-P1 alarm types ─────────────────────────────────────────────
ALWAYS_P1 = {"SYNC_LOSS", "HUB_OFFLINE"}

# ── Always-P4 alarm types ─────────────────────────────────────────────
ALWAYS_P4 = {"OPT_SATURATION"}

# ── Critical zone escalation map ─────────────────────────────────────
ZONE_ESCALATE = {"P3": "P2", "P2": "P1", "P4": "P3", "P5": "P3"}


def _zone_escalate(sev: str) -> str:
    return ZONE_ESCALATE.get(sev, sev)


def _calc_severity(alarm_code: str, scope: str, is_critical: bool,
                   root_type: str, co_alarms: list[str] = None,
                   context: dict = None) -> str:
    """
    Severity rules — evaluated in order, first match wins.

    Rule 1:  Always-P1 alarm types
    Rule 2:  Always-P4 alarm types
    Rule 3:  POI root cause → P1
    Rule 4:  Co-occurrence escalation
    Rule 5:  Alarm-specific logic
    Rule 6:  Critical zone escalation
    """
    co = co_alarms or []
    ctx = context or {}

    # Rule 1: always-P1
    if alarm_code in ALWAYS_P1:
        sev = "P1"
        return _zone_escalate(sev) if is_critical else sev

    # Rule 2: always-P4
    if alarm_code in ALWAYS_P4:
        sev = "P4"
        return _zone_escalate(sev) if is_critical else sev

    # Rule 3: POI root cause
    if root_type == "poi":
        # DL_POWER_LOW at POI: P1 if full site all carriers, else P1 (POI = at least one full carrier band)
        return "P1"

    # Rule 4: co-occurrence escalation
    if alarm_code == "FAN_FAULT" and "OVERTEMP" in co:
        return "P1"
    if alarm_code == "OVERTEMP" and "FAN_FAULT" in co:
        return "P1"
    if alarm_code == "DL_POWER_LOW" and "DL_OVERDRIVE" in co:
        return "P1"

    # Rule 5: alarm-specific logic
    sev = _alarm_severity(alarm_code, scope, root_type, ctx)

    # Rule 6: critical zone escalation
    if is_critical:
        sev = _zone_escalate(sev)

    return sev


def _alarm_severity(alarm_code: str, scope: str, root_type: str, ctx: dict) -> str:
    """Per-alarm severity logic matching confirmed classification table."""

    hub_scope = root_type in ("expansion_hub", "main_hub") or scope in (
        "Hub", "Full Site (POI)", "Sector (POI)", "Multiple RUs"
    )

    if alarm_code == "FIBER_LOS":
        return "P2" if hub_scope else "P3"

    if alarm_code == "PSU_FAULT":
        return "P2" if hub_scope else "P3"

    if alarm_code == "LNA_PA_FAULT":
        # P2 if multiple units (surge), P3 if single RU
        return "P2" if hub_scope or scope == "Multiple RUs" else "P3"

    if alarm_code == "COMM_ERROR":
        # P1 if hub unreachable, P5 if single RU with RF up
        if root_type in ("expansion_hub", "main_hub"):
            return "P1"
        return "P5"

    if alarm_code == "DL_OVERDRIVE":
        # P1 if hardware damage risk (ctx flag), P2 otherwise
        return "P1" if ctx.get("hardware_damage_risk") else "P2"

    if alarm_code == "DL_POWER_LOW":
        # P1 if full site/POI scope; P2 if multiple RUs or hub branch; P3 if single RU
        if root_type == "poi" or scope in ("Full Site (POI)", "Sector (POI)"):
            return "P1"
        if hub_scope:
            return "P2"
        return "P3"

    if alarm_code == "DL_INPUT_LOW":
        # P1 if complete POI loss all bands for carrier; P2 if partial/single band
        # Correlation engine sets root_type="poi" for full carrier loss → handled in Rule 3
        # Reaching here means partial/single band degraded
        return "P2"

    if alarm_code in ("DL_POWER_HIGH", "VSWR_HIGH", "UL_NOISE_RISE"):
        # P2 if multiple RUs, hub, or damage risk; P3 if single RU
        return "P2" if hub_scope else "P3"

    if alarm_code == "OVERTEMP":
        # P1 co-occurrence handled in Rule 4
        # P2 if near shutdown threshold (ctx flag), P4 otherwise
        return "P2" if ctx.get("near_shutdown") else "P4"

    if alarm_code == "FAN_FAULT":
        # P1 co-occurrence handled in Rule 4; P4 alone
        return "P4"

    if alarm_code == "PIM_DETECTED":
        # P3 if carrier impact confirmed, P4 otherwise
        return "P3" if ctx.get("carrier_impact") else "P4"

    if alarm_code == "DRY_CONTACT":
        trigger = ctx.get("trigger_type", "door")
        if trigger == "life_safety":
            return "P1"
        if trigger == "ups_battery":
            return "P2"
        return "P5"

    # Default: P3 for unknown alarm codes
    return "P3"


@dataclass
class Incident:
    incident_id: str
    title: str
    root_cause_node: str
    root_cause_type: str
    affected_nodes: list[str]
    alarm_code: str
    severity: str                 # P1–P5
    is_critical_zone: bool
    scope_label: str
    sparing_advice: str
    raw_alarms: list[dict] = field(default_factory=list)
    poi_suspect: Optional[str] = None


class CorrelationEngine:
    def __init__(self, topology: TopologyManager):
        self.topo = topology

    def correlate(self, alarms: list[dict]) -> list[Incident]:
        incidents: list[Incident] = []
        all_codes = [a["alarm_code"] for a in alarms]

        # ── Rule 1: Hub grouping ──────────────────────────────────────
        hub_groups: dict[tuple, list[dict]] = {}
        for alarm in alarms:
            node = self.topo.get_node(alarm["node_id"])
            if not node or node["type"] != "remote":
                continue
            parent = self.topo.get_parent(alarm["node_id"])
            if not parent or parent["type"] != "expansion_hub":
                continue
            key = (parent["id"], alarm["alarm_code"])
            hub_groups.setdefault(key, []).append(alarm)

        for (hub_id, alarm_code), group_alarms in hub_groups.items():
            health = self.topo.get_hub_health(hub_id, [a["node_id"] for a in group_alarms])
            hub_node = self.topo.get_node(hub_id)
            is_critical = health.get("is_critical", False)

            if health["hub_is_suspect"]:
                scope_label = "Hub"
                root_node = hub_id
                root_type = "expansion_hub"
            else:
                scope_label = "Multiple RUs" if len(group_alarms) > 1 else "Single RU"
                root_node = group_alarms[0]["node_id"]
                root_type = "remote"

            severity = _calc_severity(alarm_code, scope_label, is_critical,
                                      root_type, all_codes)
            incidents.append(Incident(
                incident_id=f"INC-{hub_id}-{alarm_code}",
                title=f"{alarm_code} — {hub_node.get('location', hub_id)} {'Hub Fault' if health['hub_is_suspect'] else 'RU Fault'}",
                root_cause_node=root_node,
                root_cause_type=root_type,
                affected_nodes=[a["node_id"] for a in group_alarms],
                alarm_code=alarm_code,
                severity=severity,
                is_critical_zone=is_critical,
                scope_label=scope_label,
                sparing_advice=_sparing_advice(root_type, hub_node.get("location", "")),
                raw_alarms=group_alarms,
            ))

        # ── Rule 2: POI / carrier-band grouping ──────────────────────
        band_groups: dict[tuple, list[dict]] = {}
        for alarm in alarms:
            carrier = alarm.get("carrier")
            band = alarm.get("band")
            if carrier and band:
                key = (carrier, band, alarm["alarm_code"])
                band_groups.setdefault(key, []).append(alarm)

        total_rus = len([n for n in self.topo.nodes.values() if n["type"] == "remote"])

        for (carrier, band, alarm_code), group_alarms in band_groups.items():
            if len(group_alarms) < 2:
                continue
            poi = next((p for p in self.topo.pois.values()
                        if p["carrier"] == carrier and p["band"] == band), None)
            ratio = len(group_alarms) / total_rus if total_rus else 0
            scope_label = "Full Site (POI)" if ratio >= 0.7 else "Sector (POI)"
            severity = _calc_severity(alarm_code, scope_label, False, "poi", all_codes)
            carrier_name = poi.get("carrier_name", carrier) if poi else carrier

            incidents.append(Incident(
                incident_id=f"INC-POI-{carrier}-{band}",
                title=f"{carrier_name} {band} Signal Loss — {'Sector-wide' if ratio >= 0.7 else 'Partial'}",
                root_cause_node=poi["id"] if poi else f"POI-{carrier}-{band}",
                root_cause_type="poi",
                affected_nodes=[a["node_id"] for a in group_alarms],
                alarm_code=alarm_code,
                severity=severity,
                is_critical_zone=False,
                scope_label=scope_label,
                sparing_advice="Check POI donor/BDA and fiber path. Passive spares only until active equipment RMA confirmed.",
                raw_alarms=group_alarms,
                poi_suspect=poi["id"] if poi else None,
            ))

        # ── Remaining singletons ─────────────────────────────────────
        grouped_ids = {id(a) for inc in incidents for a in inc.raw_alarms}
        for alarm in alarms:
            if id(alarm) in grouped_ids:
                continue
            node = self.topo.get_node(alarm["node_id"])
            if not node:
                continue
            is_critical = self._node_in_critical_zone(alarm["node_id"])
            severity = _calc_severity(alarm["alarm_code"], "Single RU", is_critical,
                                      node["type"], all_codes)
            incidents.append(Incident(
                incident_id=f"INC-{alarm['node_id']}-{alarm['alarm_code']}",
                title=f"{alarm['alarm_code']} — {alarm['node_id']}",
                root_cause_node=alarm["node_id"],
                root_cause_type=node["type"],
                affected_nodes=[alarm["node_id"]],
                alarm_code=alarm["alarm_code"],
                severity=severity,
                is_critical_zone=is_critical,
                scope_label="Single RU",
                sparing_advice=_sparing_advice(node["type"]),
                raw_alarms=[alarm],
            ))

        return incidents

    def _node_in_critical_zone(self, node_id: str) -> bool:
        node = self.topo.get_node(node_id)
        if not node:
            return False
        if node.get("is_critical"):
            return True
        parent = self.topo.get_parent(node_id)
        return bool(parent and parent.get("is_critical"))


def _sparing_advice(node_type: str, location: str = "") -> str:
    if node_type == "remote":
        return ("Passive spares only (Fiber/Coax/Connectors). "
                "Active RU replacement requires RMA/Sparing check per OPS-003.")
    if node_type == "expansion_hub":
        return (f"Active electronics (Expansion Hub) require RMA/Sparing check per OPS-003. "
                f"Scope impact on {location or 'zone'} before dispatch.")
    if node_type == "main_hub":
        return "Main Hub replacement is a site-level outage. Escalate immediately. Sparing approval required per OPS-003."
    return "Verify passive path first. Active equipment requires RMA/Sparing approval per OPS-003."

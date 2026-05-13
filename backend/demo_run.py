"""
demo_run.py
NOC Triage Agent v3 — End-to-end demo.

Pipeline:
  YAML raw alarms → ingestion_agent → correlation_engine_v3 → terminal summary

Usage:
    python backend/demo_run.py             # all scenarios (SCN-001, SCN-002, SCN-003)
    python backend/demo_run.py SCN-002     # single scenario
    python backend/demo_run.py SCN-003
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ingestion_agent import run_ingestion
from correlation_engine_v3 import run_correlation

# ── ANSI colours ───────────────────────────────────────────────────────

BOLD   = "\033[1m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
RESET  = "\033[0m"

_SEVERITY_COLOUR = {
    "critical": RED,
    "major":    YELLOW,
    "minor":    YELLOW,
    "warning":  CYAN,
    "info":     RESET,
}

_PRIORITY_COLOUR = {
    "P1": RED,
    "P2": YELLOW,
    "P3": CYAN,
    "P4": CYAN,
    "P5": RESET,
}

_SEV_RANK = {"critical": 0, "major": 1, "minor": 2, "warning": 3, "info": 4}


def _c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}"


def _header(title: str) -> None:
    print()
    print(_c(BOLD, "─" * 62))
    print(_c(BOLD + CYAN, f"  {title}"))
    print(_c(BOLD, "─" * 62))


def _field(label: str, value: str, indent: int = 2) -> None:
    print(f"{' ' * indent}{_c(BOLD, label + ':')} {value}")


# ── Topology extraction ────────────────────────────────────────────────

def _extract_topology_map(scenario: dict) -> dict:
    """Build {site_id -> {topology, carriers}} from the scenario dict."""
    topo_map: dict = {}
    sub_sites = {
        k: v for k, v in scenario.items()
        if isinstance(v, dict) and "site_id" in v and "topology" in v
    }
    if sub_sites:
        for _, sub in sub_sites.items():
            topo_map[sub["site_id"]] = {
                "topology": sub["topology"],
                "carriers": sub.get("carriers", []),
                "site_name": sub.get("site_name", sub["site_id"]),
                "oem": sub.get("oem", "?"),
            }
    elif "topology" in scenario:
        site_id = scenario.get("site_id", "?")
        topo_map[site_id] = {
            "topology": scenario["topology"],
            "carriers": scenario.get("carriers", []),
            "site_name": scenario.get("site_name", site_id),
            "oem": scenario.get("oem", "?"),
        }
    return topo_map


# ── Topology tree ──────────────────────────────────────────────────────

class _Node:
    """Single node in the topology display tree."""
    __slots__ = ("label", "alarm_sev", "children")

    def __init__(self, label: str, alarm_sev: str | None = None) -> None:
        self.label = label
        self.alarm_sev = alarm_sev
        self.children: list[_Node] = []


def _build_site_nodes(topo_entry: dict, site_raw_alarms: list[dict]) -> list[_Node]:
    """
    Build a list of top-level _Node objects for one site.

    Layout rules:
    - Single POI  → the POI is the root; Main Hub is its child.
    - Multiple POIs → POIs and Main Hub are siblings under the site label.

    Expansion hubs are rendered as children of the OM that references them
    (via the `expansion_hub` field in the optical_modules list).
    """
    topology = topo_entry["topology"]
    carriers = topo_entry.get("carriers", [])

    # ── Alarm lookup: equip_id -> worst severity ──────────────────
    alarmed: dict[str, str] = {}
    for a in site_raw_alarms:
        eid = a.get("source_equipment_id", "")
        sev = a.get("severity", "info")
        if eid and _SEV_RANK.get(sev, 9) < _SEV_RANK.get(alarmed.get(eid, "info"), 9):
            alarmed[eid] = sev

    # ── POI → carrier label ───────────────────────────────────────
    poi_carrier_labels: dict[str, list[str]] = {}
    for c in carriers:
        bands = c.get("bands", [])
        tech = c.get("tech", "LTE")
        if isinstance(tech, list):
            tech = "/".join(dict.fromkeys(tech))  # unique, order-preserving
        label = f"{c.get('carrier', '?')} {', '.join(bands)} {tech}"
        for poi_id in c.get("pois", []):
            poi_carrier_labels.setdefault(poi_id, []).append(label)

    # ── EH lookup ─────────────────────────────────────────────────
    eh_lookup = {eh["id"]: eh for eh in topology.get("expansion_hubs", [])}

    # ── Main hub node ─────────────────────────────────────────────
    mh_raw = topology.get("main_hub", "")
    mh_id = mh_raw if isinstance(mh_raw, str) else mh_raw.get("id", "")
    mh_node = _Node(f"{mh_id} (Main Hub)", alarm_sev=alarmed.get(mh_id))

    for om in topology.get("optical_modules", []):
        om_id = om["id"]
        om_node = _Node(f"{om_id} (Optical Module)", alarm_sev=alarmed.get(om_id))

        # Direct remotes
        for ru_id in om.get("remotes", []):
            om_node.children.append(_Node(f"{ru_id} (Remote)", alarm_sev=alarmed.get(ru_id)))

        # Expansion hub hanging off this OM
        eh_ref = om.get("expansion_hub")
        if eh_ref and eh_ref in eh_lookup:
            eh = eh_lookup[eh_ref]
            eh_node = _Node(f"{eh_ref} (Expansion Hub)", alarm_sev=alarmed.get(eh_ref))
            for sub_om in eh.get("optical_modules", []):
                sub_id = sub_om["id"]
                sub_node = _Node(f"{sub_id} (Optical Module)", alarm_sev=alarmed.get(sub_id))
                for ru_id in sub_om.get("remotes", []):
                    sub_node.children.append(
                        _Node(f"{ru_id} (Remote)", alarm_sev=alarmed.get(ru_id))
                    )
                eh_node.children.append(sub_node)
            om_node.children.append(eh_node)

        mh_node.children.append(om_node)

    # ── POI nodes ─────────────────────────────────────────────────
    pois_raw = topology.get("pois") or topology.get("poi") or []
    if isinstance(pois_raw, str):
        pois_raw = [pois_raw]

    poi_nodes: list[_Node] = []
    for poi_id in pois_raw:
        labels = poi_carrier_labels.get(poi_id, [])
        suffix = f" — {' / '.join(labels)}" if labels else ""
        poi_nodes.append(_Node(f"{poi_id} (POI){suffix}", alarm_sev=alarmed.get(poi_id)))

    if len(poi_nodes) == 1:
        # Single POI: MH is a child of the POI
        poi_nodes[0].children.append(mh_node)
        return poi_nodes
    else:
        # Multiple POIs: all are siblings of the MH
        return poi_nodes + [mh_node]


def _render_tree_lines(
    lines: list[str],
    node: _Node,
    prefix: str = "",
    is_last: bool = True,
) -> None:
    """Recursively append ASCII tree lines to `lines`."""
    connector = "└── " if is_last else "├── "

    alarm_tag = ""
    if node.alarm_sev:
        col = _SEVERITY_COLOUR.get(node.alarm_sev, RESET)
        alarm_tag = f"  {_c(col + BOLD, '[ALARM: ' + node.alarm_sev + ']')}"

    lines.append(f"{prefix}{connector}{node.label}{alarm_tag}")

    child_prefix = prefix + ("    " if is_last else "│   ")
    for i, child in enumerate(node.children):
        _render_tree_lines(lines, child, child_prefix, i == len(node.children) - 1)


def print_topology_tree(topology_map: dict, raw_alarms: list[dict]) -> None:
    _header("STEP 1 — SITE TOPOLOGY")

    # Group raw alarms by site_id (using pre-normalization OEM field names)
    alarms_by_site: dict[str, list[dict]] = {}
    for a in raw_alarms:
        alarms_by_site.setdefault(a.get("site_id", "?"), []).append(a)

    for site_id, topo_entry in topology_map.items():
        site_name = topo_entry.get("site_name", site_id)
        oem = topo_entry.get("oem", "?").title()
        site_label = f"{site_id} — {site_name} ({oem})"

        site_alarms = alarms_by_site.get(site_id, [])
        top_nodes = _build_site_nodes(topo_entry, site_alarms)

        print(f"  {_c(BOLD, site_label)}")
        lines: list[str] = []
        for i, node in enumerate(top_nodes):
            _render_tree_lines(lines, node, prefix="  ", is_last=(i == len(top_nodes) - 1))
        for line in lines:
            print(line)
        print()


# ── Remaining section printers (steps 2-5) ────────────────────────────

def print_raw_alarms(raw_alarms: list[dict]) -> None:
    _header("STEP 2 — RAW ALARMS RECEIVED")
    oems  = sorted({a.get("das_oem", "?") for a in raw_alarms})
    sites = sorted({a.get("site_id", "?") for a in raw_alarms})
    _field("Count",   str(len(raw_alarms)))
    _field("OEM(s)",  ", ".join(oems))
    _field("Site(s)", ", ".join(sites))
    print()
    for i, a in enumerate(raw_alarms, 1):
        alarm_name = a.get("alarm_name") or a.get("fault_description", "—")
        sev     = a.get("severity", "?")
        sev_str = _c(_SEVERITY_COLOUR.get(sev, RESET), f"{sev.upper():<8s}")
        eq_id   = a.get("source_equipment_id", "?")
        eq_ty   = a.get("source_equipment_type", "?")
        ts      = a.get("timestamp", "?")[11:19]
        ref     = a.get("alarm_id", "?")
        print(
            f"  [{i:2d}] {sev_str}  "
            f"{eq_ty:<6s} {eq_id:<8s}  "
            f"{alarm_name:<35s}  @{ts}  ({ref})"
        )


def print_normalized_alarms(site_events: list[dict]) -> None:
    _header("STEP 3 — NORMALIZED CANONICAL ALARMS")
    for event in site_events:
        alarms = event.get("alarm_list", [])
        site   = event["site_id"]
        zone   = event["zone_id"]
        oems   = ", ".join(event.get("das_oems", []))
        print(f"  Site: {_c(BOLD, site)}  Zone: {zone}  OEM(s): {oems}")
        print()
        print(
            f"  {'#':>2}  {'SEV':8s}  {'EQ TYPE':15s}  {'EQ ID':10s}  "
            f"{'PARENT':10s}  {'CATEGORY':20s}  ALARM"
        )
        print("  " + "·" * 90)
        for i, a in enumerate(alarms, 1):
            sev     = a.get("severity", "?")
            sev_str = _c(_SEVERITY_COLOUR.get(sev, RESET), f"{sev.upper():<8s}")
            eq_ty   = a.get("source_equipment_type", "?")
            eq_id   = a.get("source_equipment_id", "?")
            parent  = a.get("parent_equipment_id") or "—"
            cat     = a.get("alarm_category", "?")
            name    = a.get("alarm_name", "?")
            print(
                f"  {i:2d}  {sev_str}  "
                f"{eq_ty:<15s}  {eq_id:<10s}  {parent:<10s}  {cat:<20s}  {name}"
            )
        print()

        mappings = event.get("field_mappings_resolved", [])
        if mappings:
            print(f"  {_c(BOLD, 'Field mappings applied')} ({len(mappings)}):")
            seen: set[str] = set()
            for m in mappings:
                if "canonical_field" in m:
                    key = f"  oem:{m['oem_field']} → canonical:{m['canonical_field']}"
                else:
                    key = f"  {m['oem_field']} {m.get('oem_value','?')} → {m.get('canonical_value','?')}"
                if key not in seen:
                    seen.add(key)
                    print(f"    {key}")

        gaps = event.get("severity_gaps_resolved", [])
        if gaps:
            print(f"\n  {_c(BOLD, 'Severity gaps noted')} ({len(gaps)}):")
            for g in gaps:
                print(
                    f"    alarm {g['alarm_id']}: arrived as {g['arrived_as']!r}"
                    f" — {g['note']}"
                )


def print_aggregated_event(site_events: list[dict]) -> None:
    _header("STEP 4 — AGGREGATED SITE EVENT(S)")
    for event in site_events:
        site  = event["site_id"]
        zone  = event["zone_id"]
        count = event["alarm_count"]
        sev   = event["dominant_severity"]
        cat   = event["alarm_category"]
        col   = _SEVERITY_COLOUR.get(sev, RESET)
        win_s = event.get("aggregation_window_start", "?")[11:19]
        win_e = event.get("aggregation_window_end",   "?")[11:19]
        agg   = "YES" if event.get("aggregated") else "NO (stray)"

        _field("Site / Zone",      f"{site}  /  {zone}")
        _field("Alarm count",      str(count))
        _field("Dominant severity", _c(col, sev.upper()))
        _field("Alarm category",   cat)
        _field("Aggregated",       _c(GREEN if event.get("aggregated") else YELLOW, agg))
        if event.get("stray_alarm"):
            _field("Stray alarm",  _c(YELLOW, "YES"))
        _field("Window",           f"{win_s} → {win_e} (UTC)")
        print()


def print_correlation_result(results: list[dict]) -> None:
    _header("STEP 5 — CORRELATION RESULT")
    for r in results:
        site     = r["site_id"]
        zone     = r["zone_id"]
        cascade  = r.get("cascade_type", "?")
        root_id  = r.get("root_cause_node", "?")
        root_ty  = r.get("root_cause_type", "?")
        prio     = r.get("triage_priority", "?")
        prio_col = _PRIORITY_COLOUR.get(prio, RESET)
        stray    = r.get("stray_alarm", False)

        _field("Site / Zone",     f"{site}  /  {zone}")
        _field("Cascade type",    cascade)
        _field("Root cause",      f"{root_id}  ({root_ty})")
        _field("Triage priority", _c(prio_col + BOLD, prio))
        print()

        print(f"  {_c(BOLD, 'Probable root cause:')}")
        print(f"    {r.get('probable_root_cause', '—')}")
        print()

        br = r.get("blast_radius", {})
        print(f"  {_c(BOLD, 'Blast radius:')}")
        _field("  Affected equipment", ", ".join(br.get("affected_equipment", [])) or "—", indent=4)
        _field("  Affected carriers",  ", ".join(br.get("affected_carriers", [])) or "—", indent=4)
        _field("  Affected bands",     ", ".join(br.get("affected_bands", [])) or "—", indent=4)
        _field("  Service impact",     br.get("service_impact", "—"), indent=4)
        print()

        print(f"  {_c(BOLD, 'Recommended action:')}")
        action = r.get("recommended_action", "—")
        line = ""
        for word in action.split():
            if len(line) + len(word) + 1 > 70:
                print(f"    {line}")
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            print(f"    {line}")

        if stray:
            print()
            print(f"  {_c(YELLOW, '⚠  Stray alarm — no correlated activity in 15-min window.')}")

        refs = r.get("correlated_alarm_refs", [])
        if refs:
            print()
            _field("Correlated alarm refs", ", ".join(refs))
        print()


# ── Main ──────────────────────────────────────────────────────────────

def _run_scenario(scenario: dict) -> None:
    scn_id = scenario["id"]
    print()
    print(_c(BOLD + CYAN, "=" * 62))
    print(_c(BOLD + CYAN, "  NOC Triage Agent v3 — Demo Run"))
    print(_c(BOLD + CYAN, f"  Scenario: {scn_id} — {scenario['name']}"))
    print(_c(BOLD + CYAN, "=" * 62))

    raw_alarms   = scenario["raw_alarms"]
    topology_map = _extract_topology_map(scenario)
    window       = scenario.get("aggregation_window_minutes", 15)

    # Step 1 — topology tree
    print_topology_tree(topology_map, raw_alarms)

    # Step 2 — raw alarms
    print_raw_alarms(raw_alarms)

    # Step 3 — ingestion → normalized alarms
    ingestion_out = run_ingestion(raw_alarms, aggregation_window_minutes=window)
    site_events   = ingestion_out["site_events"]
    if ingestion_out["errors"]:
        print(f"\n  {_c(YELLOW, 'Ingestion warnings:')} {ingestion_out['errors']}")
    print_normalized_alarms(site_events)

    # Step 4 — aggregated events
    print_aggregated_event(site_events)

    # Step 5 — correlation
    corr_out = run_correlation(site_events, topology_map)
    results  = corr_out["results"]
    if corr_out["errors"]:
        print(f"\n  {_c(YELLOW, 'Correlation warnings:')} {corr_out['errors']}")
    print_correlation_result(results)


def main() -> None:
    scenarios_path = _BACKEND / "tests" / "ground_truth" / "scenarios.yaml"
    with open(scenarios_path) as f:
        all_scenarios = yaml.safe_load(f)["scenarios"]

    if len(sys.argv) > 1:
        scenario_id = sys.argv[1]
        scenario = next((s for s in all_scenarios if s["id"] == scenario_id), None)
        if scenario is None:
            print(f"Scenario {scenario_id!r} not found.")
            sys.exit(1)
        scenarios_to_run = [scenario]
    else:
        scenarios_to_run = all_scenarios

    for i, scenario in enumerate(scenarios_to_run):
        _run_scenario(scenario)
        if i < len(scenarios_to_run) - 1:
            print()
            print(_c(BOLD, "─" * 62))
            print()

    print()
    print(_c(BOLD, "─" * 62))
    print(_c(BOLD + GREEN, "  Demo complete."))
    print(_c(BOLD, "─" * 62))
    print()


if __name__ == "__main__":
    main()

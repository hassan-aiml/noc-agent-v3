"""
demo_run.py
NOC Triage Agent v3 — End-to-end demo for SCN-001.

Pipeline:
  YAML raw alarms → ingestion_agent → correlation_engine_v3 → terminal summary

Usage:
    python backend/demo_run.py
    python backend/demo_run.py SCN-002   # optional scenario override
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

# ── ANSI colours (degrade gracefully if terminal doesn't support them) ─

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


def _c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}"


def _header(title: str) -> None:
    width = 62
    print()
    print(_c(BOLD, "─" * width))
    print(_c(BOLD + CYAN, f"  {title}"))
    print(_c(BOLD, "─" * width))


def _field(label: str, value: str, indent: int = 2) -> None:
    pad = " " * indent
    print(f"{pad}{_c(BOLD, label + ':')} {value}")


# ── Topology extraction (mirrors test runner logic) ────────────────────

def _extract_topology_map(scenario: dict) -> dict:
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
            }
    elif "topology" in scenario:
        topo_map[scenario["site_id"]] = {
            "topology": scenario["topology"],
            "carriers": scenario.get("carriers", []),
        }
    return topo_map


# ── Section printers ───────────────────────────────────────────────────

def print_raw_alarms(raw_alarms: list[dict]) -> None:
    _header("STEP 1 — RAW ALARMS RECEIVED")
    oems   = sorted({a.get("das_oem", "?") for a in raw_alarms})
    sites  = sorted({a.get("site_id", "?") for a in raw_alarms})
    _field("Count", str(len(raw_alarms)))
    _field("OEM(s)", ", ".join(oems))
    _field("Site(s)", ", ".join(sites))
    print()
    for i, a in enumerate(raw_alarms, 1):
        alarm_name = a.get("alarm_name") or a.get("fault_description", "—")
        sev      = a.get("severity", "?")
        col      = _SEVERITY_COLOUR.get(sev, RESET)
        sev_str  = _c(col, f"{sev.upper():<8s}")
        eq_id    = a.get("source_equipment_id", "?")
        eq_ty    = a.get("source_equipment_type", "?")
        ts       = a.get("timestamp", "?")[11:19]   # HH:MM:SS only
        ref      = a.get("alarm_id", "?")
        print(
            f"  [{i:2d}] {sev_str}  "
            f"{eq_ty:<6s} {eq_id:<8s}  "
            f"{alarm_name:<35s}  @{ts}  ({ref})"
        )


def print_normalized_alarms(site_events: list[dict]) -> None:
    _header("STEP 2 — NORMALIZED CANONICAL ALARMS")
    for event in site_events:
        alarms = event.get("alarm_list", [])
        site   = event["site_id"]
        zone   = event["zone_id"]
        oems   = ", ".join(event.get("das_oems", []))
        print(f"  Site: {_c(BOLD, site)}  Zone: {zone}  OEM(s): {oems}")
        print()
        # Header row
        print(
            f"  {'#':>2}  {'SEV':8s}  {'EQ TYPE':15s}  {'EQ ID':10s}  "
            f"{'PARENT':10s}  {'CATEGORY':20s}  ALARM"
        )
        print("  " + "·" * 90)
        for i, a in enumerate(alarms, 1):
            sev     = a.get("severity", "?")
            col     = _SEVERITY_COLOUR.get(sev, RESET)
            sev_str = _c(col, f"{sev.upper():<8s}")
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

        # Mapping log
        mappings = event.get("field_mappings_resolved", [])
        if mappings:
            print(f"  {_c(BOLD, 'Field mappings applied')} ({len(mappings)}):")
            seen = set()
            for m in mappings:
                if "canonical_field" in m:
                    key = f"  oem:{m['oem_field']} → canonical:{m['canonical_field']}"
                else:
                    key = f"  {m['oem_field']} {m.get('oem_value','?')} → {m.get('canonical_value','?')}"
                if key not in seen:
                    seen.add(key)
                    print(f"    {key}")

        # Severity gaps
        gaps = event.get("severity_gaps_resolved", [])
        if gaps:
            print(f"\n  {_c(BOLD, 'Severity gaps noted')} ({len(gaps)}):")
            for g in gaps:
                print(
                    f"    alarm {g['alarm_id']}: arrived as {g['arrived_as']!r}"
                    f" — {g['note']}"
                )


def print_aggregated_event(site_events: list[dict]) -> None:
    _header("STEP 3 — AGGREGATED SITE EVENT(S)")
    for event in site_events:
        site  = event["site_id"]
        zone  = event["zone_id"]
        count = event["alarm_count"]
        sev     = event["dominant_severity"]
        cat     = event["alarm_category"]
        col     = _SEVERITY_COLOUR.get(sev, RESET)
        win_s = event.get("aggregation_window_start", "?")[11:19]
        win_e = event.get("aggregation_window_end",   "?")[11:19]
        agg   = "YES" if event.get("aggregated") else "NO (stray)"

        _field("Site / Zone", f"{site}  /  {zone}")
        _field("Alarm count", str(count))
        _field("Dominant severity", _c(col, sev.upper()))
        _field("Alarm category",   cat)
        _field("Aggregated",       _c(GREEN if event.get("aggregated") else YELLOW, agg))
        if event.get("stray_alarm"):
            _field("Stray alarm",  _c(YELLOW, "YES"))
        _field("Window",           f"{win_s} → {win_e} (UTC)")
        print()


def print_correlation_result(results: list[dict]) -> None:
    _header("STEP 4 — CORRELATION RESULT")
    for r in results:
        site     = r["site_id"]
        zone     = r["zone_id"]
        cascade  = r.get("cascade_type", "?")
        root_id  = r.get("root_cause_node", "?")
        root_ty  = r.get("root_cause_type", "?")
        prio     = r.get("triage_priority", "?")
        prio_col = _PRIORITY_COLOUR.get(prio, RESET)
        stray    = r.get("stray_alarm", False)

        _field("Site / Zone",    f"{site}  /  {zone}")
        _field("Cascade type",   cascade)
        _field("Root cause",     f"{root_id}  ({root_ty})")
        _field("Triage priority",_c(prio_col + BOLD, prio))
        print()

        print(f"  {_c(BOLD, 'Probable root cause:')}")
        print(f"    {r.get('probable_root_cause', '—')}")
        print()

        br = r.get("blast_radius", {})
        print(f"  {_c(BOLD, 'Blast radius:')}")
        equip    = br.get("affected_equipment", [])
        carriers = br.get("affected_carriers", [])
        bands    = br.get("affected_bands", [])
        impact   = br.get("service_impact", "—")
        _field("  Affected equipment", ", ".join(equip) if equip else "—", indent=4)
        _field("  Affected carriers",  ", ".join(carriers) if carriers else "—", indent=4)
        _field("  Affected bands",     ", ".join(bands) if bands else "—", indent=4)
        _field("  Service impact",     impact, indent=4)
        print()

        print(f"  {_c(BOLD, 'Recommended action:')}")
        action = r.get("recommended_action", "—")
        # Wrap at ~70 chars
        words, line = [], ""
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

        # Correlated alarm refs
        refs = r.get("correlated_alarm_refs", [])
        if refs:
            print()
            _field("Correlated alarm refs", ", ".join(refs))
        print()


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "SCN-001"

    scenarios_path = _BACKEND / "tests" / "ground_truth" / "scenarios.yaml"
    with open(scenarios_path) as f:
        all_scenarios = yaml.safe_load(f)["scenarios"]

    scenario = next((s for s in all_scenarios if s["id"] == scenario_id), None)
    if scenario is None:
        print(f"Scenario {scenario_id!r} not found.")
        sys.exit(1)

    print()
    print(_c(BOLD + CYAN, "=" * 62))
    print(_c(BOLD + CYAN, f"  NOC Triage Agent v3 — Demo Run"))
    print(_c(BOLD + CYAN, f"  Scenario: {scenario_id} — {scenario['name']}"))
    print(_c(BOLD + CYAN, "=" * 62))

    raw_alarms   = scenario["raw_alarms"]
    topology_map = _extract_topology_map(scenario)
    window       = scenario.get("aggregation_window_minutes", 15)

    # ── Step 1: print raw alarms ──────────────────────────────────
    print_raw_alarms(raw_alarms)

    # ── Step 2: ingestion ─────────────────────────────────────────
    ingestion_out = run_ingestion(raw_alarms, aggregation_window_minutes=window)
    site_events   = ingestion_out["site_events"]

    if ingestion_out["errors"]:
        print(f"\n  {_c(YELLOW, 'Ingestion warnings:')} {ingestion_out['errors']}")

    print_normalized_alarms(site_events)

    # ── Step 3: aggregated events ─────────────────────────────────
    print_aggregated_event(site_events)

    # ── Step 4: correlation ───────────────────────────────────────
    corr_out = run_correlation(site_events, topology_map)
    results  = corr_out["results"]

    if corr_out["errors"]:
        print(f"\n  {_c(YELLOW, 'Correlation warnings:')} {corr_out['errors']}")

    print_correlation_result(results)

    print(_c(BOLD, "─" * 62))
    print(_c(BOLD + GREEN, "  Demo complete."))
    print(_c(BOLD, "─" * 62))
    print()


if __name__ == "__main__":
    main()

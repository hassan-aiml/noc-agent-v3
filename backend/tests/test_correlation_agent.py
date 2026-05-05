"""
test_correlation_agent.py
Ground-truth test runner for the correlation agent (correlation_engine_v3.py).

Pipeline under test:
  1. Run ingestion_agent.run_ingestion() on the scenario's raw_alarms.
  2. Extract topology_map from the scenario's topology / carriers fields.
  3. Run correlation_engine_v3.run_correlation(site_events, topology_map).
  4. Validate each correlation result against expected_output.

Validated fields per site event:
  - alarm_category (exact)
  - probable_root_cause (key equipment IDs present as substrings)
  - blast_radius.affected_equipment (set equality)
  - blast_radius.affected_carriers (set equality)
  - blast_radius.affected_bands (set equality)
  - blast_radius.service_impact (key terms present)
  - stray_alarm (exact bool)
  - aggregated (exact bool)

Usage:
    python tests/test_correlation_agent.py          # all scenarios
    python tests/test_correlation_agent.py SCN-002  # single scenario
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any

import yaml

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ingestion_agent import run_ingestion            # noqa: E402
from correlation_engine_v3 import run_correlation    # noqa: E402

_SCENARIOS_FILE = Path(__file__).resolve().parent / "ground_truth" / "scenarios.yaml"


# ── YAML loading ───────────────────────────────────────────────────────


def _load_scenarios() -> list[dict]:
    with open(_SCENARIOS_FILE) as f:
        return yaml.safe_load(f)["scenarios"]


# ── Topology extraction from scenario YAML ────────────────────────────


def _extract_topology_map(scenario: dict) -> dict:
    """
    Build topology_map = {site_id -> {"topology": dict, "carriers": list}}
    from the varying shapes present in scenarios.yaml:
      - Single-site scenario: scenario.{topology, carriers, site_id}
      - Multi-site scenario: scenario.{site_atx_003, site_atx_004} sub-dicts
    """
    topo_map: dict = {}

    # Multi-site: look for sub-dicts named site_atx_* or similar
    sub_sites = {k: v for k, v in scenario.items()
                 if isinstance(v, dict) and "site_id" in v and "topology" in v}

    if sub_sites:
        for _key, sub in sub_sites.items():
            site_id = sub["site_id"]
            topo_map[site_id] = {
                "topology": sub["topology"],
                "carriers": sub.get("carriers", []),
            }
    elif "topology" in scenario:
        site_id = scenario.get("site_id", "")
        topo_map[site_id] = {
            "topology": scenario["topology"],
            "carriers": scenario.get("carriers", []),
        }

    return topo_map


# ── Assertion helpers ──────────────────────────────────────────────────


class AssertionResult:
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        suffix = f" — {self.message}" if self.message else ""
        return f"  [{status}] {self.name}{suffix}"


def _check(name: str, actual: Any, expected: Any) -> AssertionResult:
    if actual == expected:
        return AssertionResult(name, True)
    return AssertionResult(name, False, f"expected={expected!r}, got={actual!r}")


def _check_set(name: str, actual: list, expected: list) -> AssertionResult:
    """Order-independent list equality."""
    if set(actual) == set(expected):
        return AssertionResult(name, True)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    parts = []
    if missing:
        parts.append(f"missing={missing}")
    if extra:
        parts.append(f"extra={extra}")
    return AssertionResult(name, False, ", ".join(parts))


def _check_ids_in_text(name: str, text: str, expected_ids: list[str]) -> AssertionResult:
    """Check that all listed equipment IDs appear as substrings in the text."""
    missing = [eid for eid in expected_ids if eid not in text]
    if not missing:
        return AssertionResult(name, True)
    return AssertionResult(name, False, f"missing IDs in text: {missing!r}\nText: {text!r}")


def _check_terms(name: str, text: str, required_terms: list[str]) -> AssertionResult:
    """At least one of each group of OR-alternatives must appear in text."""
    # Each element can be a string (must appear) or list (any must appear)
    missing: list[str] = []
    for term in required_terms:
        if isinstance(term, list):
            if not any(t.lower() in text.lower() for t in term):
                missing.append(f"one of {term}")
        else:
            if term.lower() not in text.lower():
                missing.append(repr(term))
    if not missing:
        return AssertionResult(name, True)
    return AssertionResult(name, False, f"missing terms: {missing}\nText: {text!r}")


# ── Per-scenario validation ────────────────────────────────────────────

# Service impact key-term requirements per scenario/site
_SERVICE_IMPACT_TERMS: dict[str, list] = {
    "SITE-ATX-001/ZONE-B2": ["Vertex", "B4", ["coverage", "loss"]],
    "SITE-ATX-002/ZONE-L4": [["sync", "Sync"], "EH-01"],
    "SITE-ATX-003/ZONE-G1": [["outage", "all"], ["3 carriers", "all"]],
    "SITE-ATX-004/ZONE-R3": ["RAU-03", ["partial", "degraded"]],
}

# Key equipment IDs that MUST appear in probable_root_cause per scenario/site
_ROOT_CAUSE_IDS: dict[str, list[str]] = {
    "SITE-ATX-001/ZONE-B2": ["OM-1", "MU-01", "RU-01", "RU-02", "RU-03"],
    "SITE-ATX-002/ZONE-L4": ["MH-01", "EH-01"],
    "SITE-ATX-003/ZONE-G1": ["MU-01", "RU-01", "RU-02", "RU-04"],
    "SITE-ATX-004/ZONE-R3": ["RAU-03"],
}


def _validate_correlation_result(
    result: dict,
    expected: dict,
    label: str,
) -> list[AssertionResult]:
    assertions: list[AssertionResult] = []
    site_zone = f"{result.get('site_id')}/{result.get('zone_id')}"

    # alarm_category
    if "alarm_category" in expected:
        assertions.append(
            _check(f"{label}: alarm_category",
                   result.get("alarm_category"), expected["alarm_category"])
        )

    # stray_alarm / aggregated
    if "stray_alarm" in expected:
        assertions.append(
            _check(f"{label}: stray_alarm",
                   result.get("stray_alarm"), expected["stray_alarm"])
        )
    if "aggregated" in expected:
        assertions.append(
            _check(f"{label}: aggregated",
                   result.get("aggregated"), expected["aggregated"])
        )

    br = result.get("blast_radius", {})
    expected_br = expected.get("blast_radius", {})

    # blast_radius.affected_equipment (set equality)
    if "affected_equipment" in expected_br:
        assertions.append(
            _check_set(f"{label}: blast_radius.affected_equipment",
                       br.get("affected_equipment", []),
                       expected_br["affected_equipment"])
        )

    # blast_radius.affected_carriers (set equality)
    if "affected_carriers" in expected_br:
        assertions.append(
            _check_set(f"{label}: blast_radius.affected_carriers",
                       br.get("affected_carriers", []),
                       expected_br["affected_carriers"])
        )

    # blast_radius.affected_bands (set equality)
    if "affected_bands" in expected_br:
        assertions.append(
            _check_set(f"{label}: blast_radius.affected_bands",
                       br.get("affected_bands", []),
                       expected_br["affected_bands"])
        )

    # blast_radius.service_impact (key term presence)
    if "service_impact" in expected_br:
        impact_text = br.get("service_impact", "")
        terms = _SERVICE_IMPACT_TERMS.get(site_zone, [])
        if terms:
            assertions.append(
                _check_terms(f"{label}: blast_radius.service_impact", impact_text, terms)
            )
        else:
            # Fallback: just ensure it's non-empty
            assertions.append(
                AssertionResult(
                    f"{label}: blast_radius.service_impact",
                    bool(impact_text),
                    "" if impact_text else "empty",
                )
            )

    # probable_root_cause — key equipment IDs must appear as substrings
    if "probable_root_cause" in expected:
        root_cause_text = result.get("probable_root_cause", "")
        ids = _ROOT_CAUSE_IDS.get(site_zone, [])
        if ids:
            assertions.append(
                _check_ids_in_text(
                    f"{label}: probable_root_cause contains key IDs",
                    root_cause_text,
                    ids,
                )
            )
        # Also check the result is non-empty
        assertions.append(
            AssertionResult(
                f"{label}: probable_root_cause non-empty",
                bool(root_cause_text),
                "" if root_cause_text else "empty string",
            )
        )

    return assertions


def _run_scenario(scenario: dict) -> tuple[bool, list[AssertionResult]]:
    raw_alarms = scenario["raw_alarms"]
    window = scenario.get("aggregation_window_minutes", 15)

    # Step 1: ingestion
    ingestion_out = run_ingestion(raw_alarms, aggregation_window_minutes=window)
    site_events = ingestion_out["site_events"]

    # Step 2: build topology_map
    topology_map = _extract_topology_map(scenario)

    # Step 3: correlation
    correlation_out = run_correlation(site_events, topology_map)
    corr_results = correlation_out["results"]
    corr_errors = correlation_out["errors"]

    all_assertions: list[AssertionResult] = []
    errors = [e for e in corr_errors if "topology parse failed" not in e]
    if errors:
        all_assertions.append(
            AssertionResult("pipeline errors", False, "; ".join(errors))
        )

    expected_output = scenario["expected_output"]
    # Normalise to list
    expected_list = expected_output if isinstance(expected_output, list) else [expected_output]

    for expected in expected_list:
        site_id = expected.get("site_id", "")
        zone_id = expected.get("zone_id", "")
        label = f"{site_id}/{zone_id}"

        result = next(
            (r for r in corr_results
             if r.get("site_id") == site_id and r.get("zone_id") == zone_id),
            corr_results[0] if len(corr_results) == 1 else None,
        )

        if result is None:
            all_assertions.append(
                AssertionResult(f"{label}: result found", False,
                                "no matching correlation result")
            )
            continue

        all_assertions.append(AssertionResult(f"{label}: result found", True))
        all_assertions.extend(
            _validate_correlation_result(result, expected, label)
        )

    all_passed = all(a.passed for a in all_assertions)
    return all_passed, all_assertions


# ── Main runner ────────────────────────────────────────────────────────


def main() -> None:
    filter_id = sys.argv[1] if len(sys.argv) > 1 else None
    scenarios = _load_scenarios()

    if filter_id:
        scenarios = [s for s in scenarios if s["id"] == filter_id]
        if not scenarios:
            print(f"No scenario with id={filter_id!r}")
            sys.exit(1)

    total = passed = 0
    print("=" * 60)
    print("NOC Correlation Agent — Ground Truth Test Runner")
    print("=" * 60)

    for scenario in scenarios:
        total += 1
        scn_id = scenario["id"]
        scn_name = scenario["name"]
        print(f"\n{scn_id}: {scn_name}")
        print("-" * 60)

        try:
            ok, results = _run_scenario(scenario)
        except Exception:
            print("  [ERROR] Scenario raised an exception:")
            traceback.print_exc()
            continue

        for r in results:
            print(repr(r))

        if ok:
            passed += 1
            print("\n  >> SCENARIO PASSED")
        else:
            fail_count = sum(1 for r in results if not r.passed)
            print(f"\n  >> SCENARIO FAILED ({fail_count} assertion(s) failed)")

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} scenarios passed")
    if passed == total:
        print("All scenarios PASSED.")
    else:
        print(f"{total - passed} scenario(s) FAILED.")
    print("=" * 60)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()

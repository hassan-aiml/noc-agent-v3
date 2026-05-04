"""
test_ingestion_agent.py
Ground-truth test runner for the ingestion agent.

Loads scenarios from tests/ground_truth/scenarios.yaml, runs each scenario
through the ingestion pipeline, and validates the output against expected_output.

Usage:
    python tests/test_ingestion_agent.py          # run all scenarios
    python tests/test_ingestion_agent.py SCN-001  # run a specific scenario
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from typing import Any

import yaml

# Ensure backend/ is importable when running from repo root or tests/
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ingestion_agent import run_ingestion  # noqa: E402

# ── YAML loader ────────────────────────────────────────────────────────

_SCENARIOS_FILE = Path(__file__).resolve().parent / "ground_truth" / "scenarios.yaml"


def _load_scenarios() -> list[dict]:
    with open(_SCENARIOS_FILE) as f:
        data = yaml.safe_load(f)
    return data["scenarios"]


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


def _check_contains(name: str, container: Any, key: str) -> AssertionResult:
    if isinstance(container, dict) and key in container:
        return AssertionResult(name, True)
    return AssertionResult(name, False, f"key {key!r} not present in result")


def _check_nonempty(name: str, value: Any) -> AssertionResult:
    if value:
        return AssertionResult(name, True)
    return AssertionResult(name, False, "expected non-empty, got empty/None")


def _check_mapping_present(
    name: str,
    resolved: list[dict],
    expected_mappings: list[dict],
) -> AssertionResult:
    """
    Verify that each expected field mapping appears in resolved.
    Matches on subset of keys — e.g., oem_field + oem_value (if present).
    """
    for em in expected_mappings:
        match = any(
            all(em.get(k) == r.get(k) for k in em if k in r)
            for r in resolved
        )
        if not match:
            return AssertionResult(name, False, f"mapping not found: {em}")
    return AssertionResult(name, True)


def _check_gap_present(
    name: str,
    gaps: list[dict],
    expected_gaps: list[dict],
) -> AssertionResult:
    for eg in expected_gaps:
        alarm_id = eg.get("alarm_id")
        match = any(g.get("alarm_id") == alarm_id for g in gaps)
        if not match:
            return AssertionResult(name, False, f"severity gap not found for alarm_id={alarm_id!r}")
    return AssertionResult(name, True)


# ── Per-scenario validators ────────────────────────────────────────────


def _validate_single_event(
    event: dict,
    expected: dict,
    label: str,
) -> list[AssertionResult]:
    results: list[AssertionResult] = []

    results.append(_check(f"{label}: site_id", event.get("site_id"), expected.get("site_id")))
    results.append(_check(f"{label}: zone_id", event.get("zone_id"), expected.get("zone_id")))
    results.append(_check(f"{label}: alarm_count", event.get("alarm_count"), expected.get("alarm_count")))
    results.append(_check(f"{label}: dominant_severity", event.get("dominant_severity"), expected.get("dominant_severity")))
    results.append(_check(f"{label}: aggregated", event.get("aggregated"), expected.get("aggregated")))

    if "alarm_category" in expected:
        results.append(_check(f"{label}: alarm_category", event.get("alarm_category"), expected["alarm_category"]))

    if "stray_alarm" in expected:
        results.append(_check(f"{label}: stray_alarm", event.get("stray_alarm"), expected["stray_alarm"]))

    if "aggregation_window_start" in expected:
        results.append(
            _check(
                f"{label}: aggregation_window_start",
                event.get("aggregation_window_start"),
                expected["aggregation_window_start"],
            )
        )
    if "aggregation_window_end" in expected:
        results.append(
            _check(
                f"{label}: aggregation_window_end",
                event.get("aggregation_window_end"),
                expected["aggregation_window_end"],
            )
        )

    if expected.get("normalization_applied"):
        results.append(
            _check(f"{label}: normalization_applied", event.get("normalization_applied"), True)
        )

    if "field_mappings_resolved" in expected:
        results.append(
            _check_mapping_present(
                f"{label}: field_mappings_resolved",
                event.get("field_mappings_resolved", []),
                expected["field_mappings_resolved"],
            )
        )

    if "severity_gaps_resolved" in expected:
        results.append(
            _check_gap_present(
                f"{label}: severity_gaps_resolved",
                event.get("severity_gaps_resolved", []),
                expected["severity_gaps_resolved"],
            )
        )

    return results


def _run_scenario(scenario: dict) -> tuple[bool, list[AssertionResult]]:
    """
    Run one scenario and return (all_passed, assertion_results).
    Handles both single-site and multi-site expected outputs.
    """
    raw_alarms: list[dict] = scenario["raw_alarms"]
    window: int = scenario.get("aggregation_window_minutes", 15)
    result = run_ingestion(raw_alarms, aggregation_window_minutes=window)

    events: list[dict] = result["site_events"]
    expected_output = scenario["expected_output"]
    all_results: list[AssertionResult] = []

    # SCN-003 style: expected_output is a list of per-site dicts
    if isinstance(expected_output, list):
        for expected in expected_output:
            site_id = expected.get("site_id")
            zone_id = expected.get("zone_id")
            # Find matching event
            event = next(
                (
                    e
                    for e in events
                    if e.get("site_id") == site_id and e.get("zone_id") == zone_id
                ),
                None,
            )
            label = f"{site_id}/{zone_id}"
            if event is None:
                all_results.append(
                    AssertionResult(f"{label}: event found", False, "no matching site event in output")
                )
            else:
                all_results.append(AssertionResult(f"{label}: event found", True))
                all_results.extend(_validate_single_event(event, expected, label))
    else:
        # Single site expected output
        site_id = expected_output.get("site_id")
        zone_id = expected_output.get("zone_id")
        event = next(
            (
                e
                for e in events
                if e.get("site_id") == site_id and e.get("zone_id") == zone_id
            ),
            events[0] if events else None,
        )
        label = f"{site_id}/{zone_id}"
        if event is None:
            all_results.append(
                AssertionResult(f"{label}: event found", False, "no site event in output")
            )
        else:
            all_results.append(AssertionResult(f"{label}: event found", True))
            all_results.extend(_validate_single_event(event, expected_output, label))

    # General: no errors logged
    if result["errors"]:
        # Warnings about unknown OEM are acceptable; hard errors are not
        hard_errors = [e for e in result["errors"] if "missing required field" in e or "Normalization failed" in e]
        if hard_errors:
            all_results.append(
                AssertionResult("pipeline errors", False, "; ".join(hard_errors))
            )

    all_passed = all(r.passed for r in all_results)
    return all_passed, all_results


# ── Main runner ────────────────────────────────────────────────────────


def main() -> None:
    filter_id = sys.argv[1] if len(sys.argv) > 1 else None
    scenarios = _load_scenarios()

    if filter_id:
        scenarios = [s for s in scenarios if s["id"] == filter_id]
        if not scenarios:
            print(f"No scenario found with id={filter_id!r}")
            sys.exit(1)

    total = 0
    passed = 0

    print("=" * 60)
    print("NOC Ingestion Agent — Ground Truth Test Runner")
    print("=" * 60)

    for scenario in scenarios:
        total += 1
        scn_id = scenario["id"]
        scn_name = scenario["name"]
        print(f"\n{scn_id}: {scn_name}")
        print("-" * 60)

        try:
            ok, results = _run_scenario(scenario)
        except Exception as exc:
            print(f"  [ERROR] Scenario raised an exception: {exc}")
            import traceback
            traceback.print_exc()
            continue

        for r in results:
            print(repr(r))

        if ok:
            passed += 1
            print(f"\n  >> SCENARIO PASSED")
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

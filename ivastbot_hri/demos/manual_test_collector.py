"""Manual HRI expression/action test collection utilities."""

import json
from pathlib import Path
from pprint import pprint

from ivastbot_hri.core import keys
from ivastbot_hri.demos.local_expression_action_demo import (
    DEFAULT_EXPRESSION_ACTION_SCENARIOS,
    run_expression_action_scenario,
)


_EXPECTED_EXPRESSIONS_BY_SCENARIO = {
    "neutral_center": keys.EXPR_NEUTRAL,
    "happy_center": keys.EXPR_HAPPY,
    "happy_left": keys.EXPR_HAPPY,
    "confused_right": keys.EXPR_CONFUSED,
    "angry_center": keys.EXPR_ANGRY,
    "bored_center": keys.EXPR_BORED,
    "surprise_center": keys.EXPR_SURPRISE,
    "low_confidence_unknown": keys.EXPR_UNKNOWN,
    "no_person": keys.EXPR_UNKNOWN,
}

DEFAULT_MANUAL_TEST_CASES = tuple(
    {
        **scenario,
        "expected_expression": _EXPECTED_EXPRESSIONS_BY_SCENARIO.get(
            scenario["name"]
        ),
        "notes": None,
    }
    for scenario in DEFAULT_EXPRESSION_ACTION_SCENARIOS
)


def build_manual_test_case(
    name: str,
    person_detected: bool,
    person_position: str | None,
    scores: dict | None,
    expected_expression: str | None = None,
    notes: str | None = None,
) -> dict:
    """Build a structured manual expression/action test case."""
    return {
        "name": name,
        "person_detected": bool(person_detected),
        "person_position": person_position,
        "scores": dict(scores or {}),
        "expected_expression": expected_expression,
        "notes": notes,
    }


def run_manual_test_case(test_case: dict) -> dict:
    """Run one manual test case and add expected-expression comparison data."""
    scenario_result = run_expression_action_scenario(test_case)
    expected_expression = test_case.get("expected_expression")
    raw_expression = scenario_result["raw_expression"]

    return {
        "test_name": test_case.get("name", "unnamed"),
        "person_detected": scenario_result["person_detected"],
        "person_position": scenario_result["person_position"],
        "input_scores": dict(test_case.get("scores") or {}),
        "expected_expression": expected_expression,
        "raw_expression": raw_expression,
        "smoothed_expression": scenario_result["smoothed_expression"],
        "matched_expected": _matches_expected(raw_expression, expected_expression),
        "action_results": scenario_result["action_results"],
        "face_commands": scenario_result["face_commands"],
        "gesture_commands": scenario_result["gesture_commands"],
        "navigation_commands": scenario_result["navigation_commands"],
        "notes": test_case.get("notes"),
    }


def run_manual_test_cases(test_cases: list[dict]) -> list[dict]:
    """Run multiple manual test cases with isolated deterministic pipelines."""
    return [run_manual_test_case(test_case) for test_case in test_cases]


def save_results_json(results: list[dict], output_path: str) -> None:
    """Save collected manual test results as UTF-8 JSON at the given path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def summarize_results(results: list[dict]) -> dict:
    """Summarize expected-expression match results for manual review."""
    total_cases = len(results)
    matched_cases = sum(1 for result in results if result.get("matched_expected") is True)
    mismatched_cases = sum(
        1 for result in results if result.get("matched_expected") is False
    )
    not_evaluated_cases = total_cases - matched_cases - mismatched_cases

    return {
        "total_cases": total_cases,
        "matched_cases": matched_cases,
        "mismatched_cases": mismatched_cases,
        "not_evaluated_cases": not_evaluated_cases,
    }


def run_default_manual_tests() -> list[dict]:
    """Run built-in sample manual test cases."""
    return run_manual_test_cases(list(DEFAULT_MANUAL_TEST_CASES))


def main() -> int:
    """Print built-in manual test results and summary for local inspection."""
    results = run_default_manual_tests()
    pprint(results)
    pprint(summarize_results(results))
    return 0


def _matches_expected(raw_expression: str, expected_expression: str | None) -> bool | None:
    if expected_expression is None:
        return None
    return raw_expression == expected_expression


def _expected_expression_for_scenario(name: str) -> str | None:
    return _EXPECTED_EXPRESSIONS_BY_SCENARIO.get(name)


if __name__ == "__main__":
    raise SystemExit(main())

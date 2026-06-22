import importlib
import json
import sys

from ivastbot_hri.core import keys
from ivastbot_hri.demos.manual_test_collector import (
    DEFAULT_MANUAL_TEST_CASES,
    build_manual_test_case,
    run_default_manual_tests,
    run_manual_test_case,
    run_manual_test_cases,
    save_results_json,
    summarize_results,
)


EXPECTED_RESULT_KEYS = {
    "test_name",
    "person_detected",
    "person_position",
    "input_scores",
    "expected_expression",
    "raw_expression",
    "smoothed_expression",
    "matched_expected",
    "action_results",
    "face_commands",
    "gesture_commands",
    "navigation_commands",
    "notes",
}


def test_importing_manual_test_collector_requires_no_optional_runtime(tmp_path):
    forbidden_roots = {
        "cv2",
        "mediapipe",
        "numpy",
        "openni",
        "requests",
        "rclpy",
        "serial",
        "websocket",
        "websockets",
    }
    before = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }

    output_path = tmp_path / "manual_results.json"
    sys.modules.pop("ivastbot_hri.demos.manual_test_collector", None)
    module = importlib.import_module("ivastbot_hri.demos.manual_test_collector")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.run_manual_test_case is not None
    assert after == before
    assert not output_path.exists()


def test_build_manual_test_case_creates_valid_dictionary():
    test_case = build_manual_test_case(
        name="happy_left_manual",
        person_detected=True,
        person_position="left",
        scores={"smile_score": 0.9, "face_confidence": 0.95},
        expected_expression=keys.EXPR_HAPPY,
        notes="clear smile",
    )

    assert test_case == {
        "name": "happy_left_manual",
        "person_detected": True,
        "person_position": "left",
        "scores": {"smile_score": 0.9, "face_confidence": 0.95},
        "expected_expression": keys.EXPR_HAPPY,
        "notes": "clear smile",
    }


def test_run_manual_test_case_returns_expected_debug_keys():
    result = run_manual_test_case(_sample_case())

    assert set(result) == EXPECTED_RESULT_KEYS
    assert result["test_name"] == "happy_center_manual"
    assert result["input_scores"]["smile_score"] == 0.9
    assert result["action_results"]
    assert result["navigation_commands"] == []


def test_high_smile_case_produces_happy_expression():
    result = run_manual_test_case(_sample_case())

    assert result["raw_expression"] == keys.EXPR_HAPPY
    assert result["matched_expected"] is True
    assert result["face_commands"][0] == {"emotion": "happy"}


def test_low_confidence_case_produces_unknown_expression():
    test_case = build_manual_test_case(
        name="low_confidence",
        person_detected=True,
        person_position="center",
        scores={"smile_score": 0.9, "face_confidence": 0.1},
        expected_expression=keys.EXPR_UNKNOWN,
    )

    result = run_manual_test_case(test_case)

    assert result["raw_expression"] == keys.EXPR_UNKNOWN
    assert result["matched_expected"] is True


def test_mismatched_expected_expression_is_counted():
    result = run_manual_test_case(
        build_manual_test_case(
            name="happy_expected_neutral",
            person_detected=True,
            person_position="center",
            scores={"smile_score": 0.9, "face_confidence": 0.95},
            expected_expression=keys.EXPR_NEUTRAL,
        )
    )

    assert result["raw_expression"] == keys.EXPR_HAPPY
    assert result["matched_expected"] is False


def test_no_expected_expression_produces_none_match_value():
    result = run_manual_test_case(
        build_manual_test_case(
            name="not_labeled",
            person_detected=True,
            person_position="center",
            scores={"smile_score": 0.9, "face_confidence": 0.95},
        )
    )

    assert result["matched_expected"] is None


def test_run_manual_test_cases_returns_list():
    results = run_manual_test_cases([_sample_case()])

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["test_name"] == "happy_center_manual"


def test_summarize_results_counts_total_matched_and_mismatched_cases():
    results = [
        {"matched_expected": True},
        {"matched_expected": False},
        {"matched_expected": None},
    ]

    summary = summarize_results(results)

    assert summary == {
        "total_cases": 3,
        "matched_cases": 1,
        "mismatched_cases": 1,
        "not_evaluated_cases": 1,
    }


def test_save_results_json_writes_valid_json_to_tmp_path(tmp_path):
    results = [run_manual_test_case(_sample_case())]
    output_path = tmp_path / "nested" / "manual_results.json"

    save_results_json(results, str(output_path))

    assert json.loads(output_path.read_text(encoding="utf-8")) == results


def test_default_manual_test_cases_cover_required_samples():
    names = {test_case["name"] for test_case in DEFAULT_MANUAL_TEST_CASES}

    assert names >= {
        "neutral_center",
        "happy_center",
        "happy_left",
        "confused_right",
        "surprise_center",
        "low_confidence_unknown",
        "no_person",
    }


def test_run_default_manual_tests_returns_structured_results():
    results = run_default_manual_tests()

    assert results
    assert all(set(result) == EXPECTED_RESULT_KEYS for result in results)
    assert summarize_results(results)["total_cases"] == len(DEFAULT_MANUAL_TEST_CASES)


def _sample_case() -> dict:
    return build_manual_test_case(
        name="happy_center_manual",
        person_detected=True,
        person_position="center",
        scores={"smile_score": 0.9, "face_confidence": 0.95},
        expected_expression=keys.EXPR_HAPPY,
        notes="manual high smile example",
    )

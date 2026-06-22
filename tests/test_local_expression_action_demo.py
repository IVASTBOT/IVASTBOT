import importlib
import sys

from ivastbot_hri.core import keys
from ivastbot_hri.demos.local_expression_action_demo import (
    DEFAULT_EXPRESSION_ACTION_SCENARIOS,
    build_expression_action_pipeline,
    run_expression_action_demo,
    run_expression_action_scenario,
)


EXPECTED_RESULT_KEYS = {
    "scenario_name",
    "person_detected",
    "person_position",
    "extracted_features",
    "raw_expression",
    "smoothed_expression",
    "action_results",
    "face_commands",
    "gesture_commands",
    "navigation_commands",
}


def test_importing_local_expression_action_demo_requires_no_optional_runtime():
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

    sys.modules.pop("ivastbot_hri.demos.local_expression_action_demo", None)
    module = importlib.import_module("ivastbot_hri.demos.local_expression_action_demo")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.run_expression_action_demo is not None
    assert after == before


def test_build_expression_action_pipeline_returns_usable_components():
    pipeline = build_expression_action_pipeline()

    assert pipeline["feature_extractor"].extract_from_scores({"smile_score": 0.9})
    assert pipeline["recognizer"].recognize(
        {"smile_score": 0.9, "face_confidence": 1.0}
    ) == keys.EXPR_HAPPY
    assert pipeline["smoother"].current() == keys.EXPR_UNKNOWN
    assert pipeline["interaction_manager"] is not None
    assert pipeline["action_library"] is not None
    assert pipeline["face_adapter"].sent_commands == []
    assert pipeline["gesture_adapter"].commands == []
    assert pipeline["navigation_adapter"].commands == []


def test_run_expression_action_scenario_returns_expected_debug_keys():
    result = run_expression_action_scenario(_scenario_by_name("happy_left"))

    assert set(result) == EXPECTED_RESULT_KEYS
    assert result["scenario_name"] == "happy_left"


def test_happy_scenario_produces_happy_raw_expression_and_face_commands():
    result = run_expression_action_scenario(_scenario_by_name("happy_left"))

    assert result["raw_expression"] == keys.EXPR_HAPPY
    assert result["smoothed_expression"] == keys.EXPR_HAPPY
    assert result["face_commands"] == [
        {"emotion": "happy"},
        {"gaze": "left"},
    ]
    assert [item["action_key"] for item in result["action_results"]] == [
        keys.SHOW_HAPPY_FACE,
        keys.LOOK_LEFT,
    ]


def test_low_confidence_scenario_produces_unknown_raw_expression():
    result = run_expression_action_scenario(
        _scenario_by_name("low_confidence_unknown")
    )

    assert result["raw_expression"] == keys.EXPR_UNKNOWN
    assert result["face_commands"] == [
        {"emotion": "neutral"},
        {"gaze": "center"},
    ]


def test_no_person_scenario_produces_idle_action_behavior():
    result = run_expression_action_scenario(_scenario_by_name("no_person"))

    assert result["raw_expression"] == keys.EXPR_UNKNOWN
    assert result["action_results"][0]["action_key"] == keys.IDLE
    assert result["action_results"][0]["executed"] is True
    assert result["face_commands"] == [{"emotion": "neutral"}]


def test_confused_right_scenario_produces_thinking_face_and_look_right():
    result = run_expression_action_scenario(_scenario_by_name("confused_right"))

    assert result["raw_expression"] == keys.EXPR_CONFUSED
    assert result["person_position"] == "right"
    assert result["face_commands"] == [
        {"emotion": "thinking"},
        {"gaze": "right"},
    ]


def test_run_expression_action_demo_returns_non_empty_list():
    results = run_expression_action_demo()

    assert results
    assert all(set(result) == EXPECTED_RESULT_KEYS for result in results)
    assert {result["scenario_name"] for result in results} >= {
        "no_person",
        "neutral_center",
        "happy_center",
        "happy_left",
        "confused_right",
        "surprise_center",
        "low_confidence_unknown",
    }


def test_gesture_commands_are_captured_when_gestures_are_triggered():
    result = run_expression_action_scenario(_scenario_by_name("happy_center"))

    assert result["gesture_commands"] == [
        {"command": keys.WAVE_HAND, "payload": {}}
    ]
    assert result["action_results"][-1]["action_key"] == keys.WAVE_HAND


def test_navigation_commands_list_exists_even_if_empty():
    result = run_expression_action_scenario(_scenario_by_name("neutral_center"))

    assert result["navigation_commands"] == []


def _scenario_by_name(name: str) -> dict:
    for scenario in DEFAULT_EXPRESSION_ACTION_SCENARIOS:
        if scenario["name"] == name:
            return scenario
    raise AssertionError(f"Missing demo scenario: {name}")

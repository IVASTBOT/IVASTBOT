import importlib
import sys

from ivastbot_hri.core import keys
from ivastbot_hri.demos.local_hri_demo import (
    build_local_hri_pipeline,
    run_demo,
    run_demo_scenario,
)


EXPECTED_RESULT_KEYS = {
    "scenario_name",
    "extracted_features",
    "raw_expression",
    "smoothed_expression",
    "person_detected",
    "person_position",
    "action_results",
    "face_bridge_commands",
    "gesture_commands",
    "navigation_commands",
}


def test_build_local_hri_pipeline_returns_usable_components():
    pipeline = build_local_hri_pipeline()

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


def test_run_demo_scenario_returns_expected_debug_keys():
    result = run_demo_scenario(
        {
            "name": "happy_left",
            "person_detected": True,
            "person_position": keys.PERSON_LEFT,
            "scores": {"smile_score": 0.9, "face_confidence": 0.95},
        }
    )

    assert set(result) == EXPECTED_RESULT_KEYS
    assert result["scenario_name"] == "happy_left"


def test_happy_scenario_produces_happy_expression_and_face_commands():
    result = run_demo_scenario(
        {
            "name": "happy_left",
            "person_detected": True,
            "person_position": keys.PERSON_LEFT,
            "scores": {"smile_score": 0.9, "face_confidence": 0.95},
        }
    )

    assert result["extracted_features"]["smile_score"] == 0.9
    assert result["extracted_features"]["face_confidence"] == 0.95
    assert result["raw_expression"] == keys.EXPR_HAPPY
    assert result["smoothed_expression"] == keys.EXPR_HAPPY
    assert result["face_bridge_commands"] == [
        {"emotion": "happy"},
        {"gaze": "left"},
    ]


def test_no_person_scenario_produces_idle_action_behavior():
    result = run_demo_scenario(
        {
            "name": "no_person",
            "person_detected": False,
            "scores": None,
        }
    )

    assert result["raw_expression"] == keys.EXPR_UNKNOWN
    assert result["action_results"][0]["action_key"] == keys.IDLE
    assert result["action_results"][0]["executed"] is True
    assert result["face_bridge_commands"] == [{"emotion": "neutral"}]


def test_low_confidence_scenario_produces_unknown_expression():
    result = run_demo_scenario(
        {
            "name": "low_confidence",
            "person_detected": True,
            "person_position": keys.PERSON_CENTER,
            "scores": {"smile_score": 0.9, "face_confidence": 0.1},
        }
    )

    assert result["raw_expression"] == keys.EXPR_UNKNOWN
    assert result["smoothed_expression"] == keys.EXPR_UNKNOWN
    assert result["face_bridge_commands"] == [
        {"emotion": "neutral"},
        {"gaze": "center"},
    ]


def test_gesture_commands_are_generated_for_extra_actions():
    result = run_demo_scenario(
        {
            "name": "happy_wave",
            "person_detected": True,
            "person_position": keys.PERSON_CENTER,
            "scores": {"smile_score": 0.9, "face_confidence": 0.95},
            "extra_actions": (keys.WAVE_HAND,),
        }
    )

    assert result["gesture_commands"] == [
        {"command": keys.WAVE_HAND, "payload": {}}
    ]
    assert result["action_results"][-1]["action_key"] == keys.WAVE_HAND


def test_run_demo_returns_non_empty_list_of_scenario_results():
    results = run_demo()

    assert results
    assert all(set(result) == EXPECTED_RESULT_KEYS for result in results)
    assert {result["scenario_name"] for result in results} >= {
        "no_person",
        "happy_center",
        "happy_left",
        "confused_right",
        "surprised_center",
        "low_confidence_unknown",
    }


def test_navigation_commands_are_available_and_empty_without_navigation_actions():
    result = run_demo_scenario(
        {
            "name": "surprised_center",
            "person_detected": True,
            "person_position": keys.PERSON_CENTER,
            "scores": {
                "mouth_open_score": 0.85,
                "eyebrow_raise_score": 0.85,
                "face_confidence": 0.95,
            },
        }
    )

    assert result["raw_expression"] == keys.EXPR_SURPRISE
    assert result["navigation_commands"] == []


def test_local_hri_demo_import_has_no_ros_camera_network_or_hardware_dependency():
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

    sys.modules.pop("ivastbot_hri.demos.local_hri_demo", None)
    module = importlib.import_module("ivastbot_hri.demos.local_hri_demo")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.run_demo is not None
    assert after == before

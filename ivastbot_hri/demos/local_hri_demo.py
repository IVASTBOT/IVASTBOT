"""End-to-end local HRI pipeline demo without external services."""

from pprint import pprint

from ivastbot_hri.adapters.face_bridge_adapter import FaceBridgeAdapter
from ivastbot_hri.adapters.face_feature_extractor import FaceFeatureExtractor
from ivastbot_hri.adapters.fake_gesture_adapter import FakeGestureAdapter
from ivastbot_hri.adapters.fake_navigation_adapter import FakeNavigationAdapter
from ivastbot_hri.core import keys
from ivastbot_hri.core.action_library import ActionLibrary
from ivastbot_hri.core.cooldown import CooldownManager
from ivastbot_hri.core.emotion_recognizer import ExpressionRecognizer
from ivastbot_hri.core.expression_smoother import ExpressionSmoother
from ivastbot_hri.core.interaction_manager import InteractionManager


DEFAULT_DEMO_SCENARIOS = (
    {
        "name": "no_person",
        "person_detected": False,
        "person_position": None,
        "scores": None,
    },
    {
        "name": "happy_center",
        "person_detected": True,
        "person_position": keys.PERSON_CENTER,
        "scores": {"smile_score": 0.9, "face_confidence": 0.95},
        "extra_actions": (keys.WAVE_HAND,),
    },
    {
        "name": "happy_left",
        "person_detected": True,
        "person_position": keys.PERSON_LEFT,
        "scores": {"smile_score": 0.9, "face_confidence": 0.95},
    },
    {
        "name": "confused_right",
        "person_detected": True,
        "person_position": keys.PERSON_RIGHT,
        "scores": {
            "smile_score": 0.1,
            "eyebrow_raise_score": 0.8,
            "mouth_open_score": 0.2,
            "face_confidence": 0.95,
        },
    },
    {
        "name": "surprised_center",
        "person_detected": True,
        "person_position": keys.PERSON_CENTER,
        "scores": {
            "mouth_open_score": 0.85,
            "eyebrow_raise_score": 0.85,
            "face_confidence": 0.95,
        },
    },
    {
        "name": "low_confidence_unknown",
        "person_detected": True,
        "person_position": keys.PERSON_CENTER,
        "scores": {"smile_score": 0.9, "face_confidence": 0.1},
    },
)


class DemoClock:
    """Deterministic clock for local demo cooldown wiring."""

    def __init__(self, current_time: float = 0.0):
        self.current_time = current_time

    def now(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


def build_local_hri_pipeline() -> dict:
    """Build a deterministic local HRI pipeline using fake/local adapters."""
    clock = DemoClock()
    face_adapter = FaceBridgeAdapter()
    gesture_adapter = FakeGestureAdapter()
    navigation_adapter = FakeNavigationAdapter()
    cooldown_manager = CooldownManager(
        default_cooldown_seconds=0.0,
        time_provider=clock.now,
    )
    action_library = ActionLibrary(
        face_adapter=face_adapter,
        gesture_adapter=gesture_adapter,
        navigation_adapter=navigation_adapter,
        cooldown_manager=cooldown_manager,
    )

    return {
        "clock": clock,
        "feature_extractor": FaceFeatureExtractor(),
        "recognizer": ExpressionRecognizer(),
        "smoother": ExpressionSmoother(window_size=3, min_confidence_count=1),
        "face_adapter": face_adapter,
        "gesture_adapter": gesture_adapter,
        "navigation_adapter": navigation_adapter,
        "cooldown_manager": cooldown_manager,
        "action_library": action_library,
        "interaction_manager": InteractionManager(action_library),
    }


def run_demo_scenario(scenario: dict, pipeline: dict | None = None) -> dict:
    """Run one static HRI demo scenario and return inspectable debug output."""
    active_pipeline = pipeline or build_local_hri_pipeline()
    face_adapter = active_pipeline["face_adapter"]
    gesture_adapter = active_pipeline["gesture_adapter"]
    navigation_adapter = active_pipeline["navigation_adapter"]

    face_start = len(face_adapter.sent_commands)
    gesture_start = len(gesture_adapter.commands)
    navigation_start = len(navigation_adapter.commands)

    features = _extract_features(active_pipeline["feature_extractor"], scenario)
    raw_expression = active_pipeline["recognizer"].recognize(features)
    smoothed_expression = active_pipeline["smoother"].update(raw_expression)

    person_detected = bool(scenario.get("person_detected", False))
    person_position = scenario.get("person_position")
    action_results = active_pipeline["interaction_manager"].handle_state(
        person_detected=person_detected,
        expression_key=smoothed_expression,
        person_position=person_position,
    )

    for extra_action in scenario.get("extra_actions", ()):
        action_results.append(
            _action_result_to_dict(
                active_pipeline["action_library"].execute(
                    _extra_action_key(extra_action),
                    _extra_action_payload(extra_action),
                )
            )
        )

    return {
        "scenario_name": scenario.get("name", "unnamed"),
        "extracted_features": features,
        "raw_expression": raw_expression,
        "smoothed_expression": smoothed_expression,
        "person_detected": person_detected,
        "person_position": person_position,
        "action_results": action_results,
        "face_bridge_commands": face_adapter.sent_commands[face_start:],
        "gesture_commands": _serialize_adapter_commands(
            gesture_adapter.commands[gesture_start:]
        ),
        "navigation_commands": _serialize_adapter_commands(
            navigation_adapter.commands[navigation_start:]
        ),
    }


def run_demo() -> list[dict]:
    """Run all built-in static demo scenarios."""
    pipeline = build_local_hri_pipeline()
    return [
        run_demo_scenario(scenario, pipeline=pipeline)
        for scenario in DEFAULT_DEMO_SCENARIOS
    ]


def main() -> int:
    """Print demo scenario results for local manual inspection."""
    pprint(run_demo())
    return 0


def _extract_features(feature_extractor, scenario: dict) -> dict:
    if "scores" in scenario:
        return feature_extractor.extract_from_scores(scenario.get("scores"))
    return feature_extractor.extract_from_landmarks(
        scenario.get("landmarks"),
        confidence=scenario.get("confidence", 1.0),
    )


def _action_result_to_dict(result) -> dict:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return dict(result)


def _extra_action_key(extra_action) -> str:
    if isinstance(extra_action, dict):
        return extra_action["action_key"]
    return extra_action


def _extra_action_payload(extra_action) -> dict | None:
    if isinstance(extra_action, dict):
        return extra_action.get("payload")
    return None


def _serialize_adapter_commands(commands) -> list[dict]:
    return [
        {
            "command": command,
            "payload": dict(payload),
        }
        for command, payload in commands
    ]


if __name__ == "__main__":
    raise SystemExit(main())

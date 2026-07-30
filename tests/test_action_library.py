import importlib
import sys

from ivastbot_hri.adapters.fake_face_adapter import FakeFaceAdapter
from ivastbot_hri.adapters.fake_gesture_adapter import FakeGestureAdapter
from ivastbot_hri.adapters.fake_navigation_adapter import FakeNavigationAdapter
from ivastbot_hri.core import keys
from ivastbot_hri.core.action_library import ActionLibrary
from ivastbot_hri.core.cooldown import CooldownManager


def make_library():
    face = FakeFaceAdapter()
    gesture = FakeGestureAdapter()
    navigation = FakeNavigationAdapter()
    return ActionLibrary(face, gesture, navigation), face, gesture, navigation


def expected_result(action_key, executed=True, reason="executed", payload=None, error=None):
    return {
        "action_key": action_key,
        "executed": executed,
        "reason": reason,
        "payload": dict(payload or {}),
        "error": error,
    }


def test_wave_hand_routes_to_gesture_adapter():
    library, face, gesture, navigation = make_library()

    result = library.execute(keys.WAVE_HAND)

    assert result.to_dict() == expected_result(keys.WAVE_HAND)
    assert gesture.commands == [(keys.WAVE_HAND, {})]
    assert face.commands == []
    assert navigation.commands == []


def test_point_actions_route_to_gesture_adapter():
    library, face, gesture, navigation = make_library()

    library.execute(keys.POINT_LEFT, {"duration": 1.0})
    library.execute(keys.POINT_RIGHT)
    library.execute(keys.POINT_FORWARD, {"duration_ms": 500})

    assert gesture.commands == [
        (keys.POINT_LEFT, {"duration": 1.0}),
        (keys.POINT_RIGHT, {}),
        (keys.POINT_FORWARD, {"duration_ms": 500}),
    ]
    assert face.commands == []
    assert navigation.commands == []


def test_show_face_actions_route_to_face_adapter():
    library, face, gesture, navigation = make_library()

    happy_result = library.execute(keys.SHOW_HAPPY_FACE, {"duration": 1.0})
    neutral_result = library.execute(keys.SHOW_NEUTRAL_FACE)
    angry_result = library.execute(keys.SHOW_ANGRY_FACE)
    bored_result = library.execute(keys.SHOW_BORED_FACE)

    assert happy_result.to_dict() == expected_result(
        keys.SHOW_HAPPY_FACE,
        payload={"duration": 1.0},
    )
    assert neutral_result.to_dict() == expected_result(keys.SHOW_NEUTRAL_FACE)
    assert angry_result.to_dict() == expected_result(keys.SHOW_ANGRY_FACE)
    assert bored_result.to_dict() == expected_result(keys.SHOW_BORED_FACE)
    assert face.commands == [
        (keys.SHOW_HAPPY_FACE, {"duration": 1.0}),
        (keys.SHOW_NEUTRAL_FACE, {}),
        (keys.SHOW_ANGRY_FACE, {}),
        (keys.SHOW_BORED_FACE, {}),
    ]
    assert gesture.commands == []
    assert navigation.commands == []


def test_guide_to_target_routes_to_navigation_adapter_and_preserves_payload():
    library, face, gesture, navigation = make_library()
    payload = {"target": "front_desk", "speed": "slow"}

    result = library.execute(keys.GUIDE_TO_TARGET, payload)

    assert result.to_dict() == expected_result(keys.GUIDE_TO_TARGET, payload=payload)
    assert navigation.commands == [(keys.GUIDE_TO_TARGET, payload)]
    assert face.commands == []
    assert gesture.commands == []


def test_idle_maps_to_show_neutral_face():
    library, face, gesture, navigation = make_library()

    result = library.execute(keys.IDLE)

    assert result.to_dict() == expected_result(keys.IDLE)
    assert face.commands == [(keys.SHOW_NEUTRAL_FACE, {})]
    assert gesture.commands == []
    assert navigation.commands == []


def test_look_actions_route_to_face_adapter_for_now():
    library, face, gesture, navigation = make_library()

    library.execute(keys.LOOK_LEFT)
    library.execute(keys.LOOK_RIGHT)
    library.execute(keys.LOOK_CENTER)

    assert face.commands == [
        (keys.LOOK_LEFT, {}),
        (keys.LOOK_RIGHT, {}),
        (keys.LOOK_CENTER, {}),
    ]
    assert gesture.commands == []
    assert navigation.commands == []


def test_stop_action_routes_to_available_gesture_and_navigation_adapters():
    library, face, gesture, navigation = make_library()

    result = library.execute(keys.STOP_ACTION)

    assert result.to_dict() == expected_result(keys.STOP_ACTION)
    assert gesture.commands == [(keys.STOP_ACTION, {})]
    assert navigation.commands == [(keys.STOP_ACTION, {})]
    assert face.commands == []


def test_unknown_action_key_returns_invalid_action_result():
    library, face, gesture, navigation = make_library()

    result = library.execute("UNKNOWN_ACTION")

    assert result.action_key == "UNKNOWN_ACTION"
    assert result.executed is False
    assert result.reason == "invalid_action"
    assert "Unknown action key" in result.error
    assert face.commands == []
    assert gesture.commands == []
    assert navigation.commands == []


def test_invalid_payload_returns_result_and_does_not_call_adapters():
    library, face, gesture, navigation = make_library()

    result = library.execute(keys.LOOK_LEFT, {"duration": 1.0})

    assert result.executed is False
    assert result.reason == "invalid_payload"
    assert "unsupported keys" in result.error
    assert face.commands == []
    assert gesture.commands == []
    assert navigation.commands == []


def test_guide_to_target_without_target_is_invalid_and_not_routed():
    library, face, gesture, navigation = make_library()

    result = library.execute(keys.GUIDE_TO_TARGET)

    assert result.executed is False
    assert result.reason == "invalid_payload"
    assert "requires 'target' or 'target_id'" in result.error
    assert face.commands == []
    assert gesture.commands == []
    assert navigation.commands == []


def test_action_library_with_cooldown_blocks_repeated_adapter_calls():
    current_time = 0.0

    def now():
        return current_time

    face = FakeFaceAdapter()
    gesture = FakeGestureAdapter()
    navigation = FakeNavigationAdapter()
    cooldown = CooldownManager(
        default_cooldown_seconds=2.0,
        time_provider=now,
    )
    library = ActionLibrary(face, gesture, navigation, cooldown_manager=cooldown)

    first_result = library.execute(keys.WAVE_HAND)
    second_result = library.execute(keys.WAVE_HAND)

    assert first_result.to_dict() == expected_result(keys.WAVE_HAND)
    assert second_result.to_dict() == expected_result(
        keys.WAVE_HAND,
        executed=False,
        reason="cooldown",
    )
    assert gesture.commands == [(keys.WAVE_HAND, {})]
    assert face.commands == []
    assert navigation.commands == []


def test_action_library_without_cooldown_keeps_repeated_execution_behavior():
    library, _, gesture, _ = make_library()

    first_result = library.execute(keys.WAVE_HAND)
    second_result = library.execute(keys.WAVE_HAND)

    assert first_result.to_dict() == expected_result(keys.WAVE_HAND)
    assert second_result.to_dict() == expected_result(keys.WAVE_HAND)
    assert gesture.commands == [
        (keys.WAVE_HAND, {}),
        (keys.WAVE_HAND, {}),
    ]


def test_unsupported_adapter_action_returns_result_without_recording_cooldown():
    class UnsupportedGestureAdapter:
        def send(self, command, payload=None):
            raise NotImplementedError(f"No verified pose for {command}")

    cooldown = CooldownManager(default_cooldown_seconds=2.0)
    library = ActionLibrary(
        gesture_adapter=UnsupportedGestureAdapter(),
        cooldown_manager=cooldown,
    )

    result = library.execute(keys.POINT_LEFT)

    assert result.to_dict() == expected_result(
        keys.POINT_LEFT,
        executed=False,
        reason="unsupported_action",
        error="No verified pose for POINT_LEFT",
    )
    assert cooldown.can_execute(keys.POINT_LEFT)


def test_action_library_import_has_no_ros_dependency():
    before = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}

    sys.modules.pop("ivastbot_hri.core.action_library", None)
    module = importlib.import_module("ivastbot_hri.core.action_library")

    after = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}
    assert module.ActionLibrary is not None
    assert after == before

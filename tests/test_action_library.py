import importlib
import sys

import pytest

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


def test_wave_hand_routes_to_gesture_adapter():
    library, face, gesture, navigation = make_library()

    result = library.execute(keys.WAVE_HAND)

    assert result is None
    assert gesture.commands == [(keys.WAVE_HAND, {})]
    assert face.commands == []
    assert navigation.commands == []


def test_point_actions_route_to_gesture_adapter():
    library, face, gesture, navigation = make_library()

    library.execute(keys.POINT_LEFT, {"direction": "left"})
    library.execute(keys.POINT_RIGHT, {"direction": "right"})
    library.execute(keys.POINT_FORWARD, {"direction": "forward"})

    assert gesture.commands == [
        (keys.POINT_LEFT, {"direction": "left"}),
        (keys.POINT_RIGHT, {"direction": "right"}),
        (keys.POINT_FORWARD, {"direction": "forward"}),
    ]
    assert face.commands == []
    assert navigation.commands == []


def test_show_face_actions_route_to_face_adapter():
    library, face, gesture, navigation = make_library()

    library.execute(keys.SHOW_HAPPY_FACE)
    library.execute(keys.SHOW_NEUTRAL_FACE)

    assert face.commands == [
        (keys.SHOW_HAPPY_FACE, {}),
        (keys.SHOW_NEUTRAL_FACE, {}),
    ]
    assert gesture.commands == []
    assert navigation.commands == []


def test_guide_to_target_routes_to_navigation_adapter_and_preserves_payload():
    library, face, gesture, navigation = make_library()
    payload = {"target": "front_desk", "speed": "slow"}

    library.execute(keys.GUIDE_TO_TARGET, payload)

    assert navigation.commands == [(keys.GUIDE_TO_TARGET, payload)]
    assert face.commands == []
    assert gesture.commands == []


def test_idle_maps_to_show_neutral_face():
    library, face, gesture, navigation = make_library()

    library.execute(keys.IDLE)

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

    library.execute(keys.STOP_ACTION, {"reason": "test"})

    assert gesture.commands == [(keys.STOP_ACTION, {"reason": "test"})]
    assert navigation.commands == [(keys.STOP_ACTION, {"reason": "test"})]
    assert face.commands == []


def test_unknown_action_key_raises_value_error():
    library, _, _, _ = make_library()

    with pytest.raises(ValueError, match="Unknown action key"):
        library.execute("UNKNOWN_ACTION")


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

    assert first_result == {
        "action_key": keys.WAVE_HAND,
        "executed": True,
        "reason": "executed",
    }
    assert second_result == {
        "action_key": keys.WAVE_HAND,
        "executed": False,
        "reason": "cooldown",
    }
    assert gesture.commands == [(keys.WAVE_HAND, {})]
    assert face.commands == []
    assert navigation.commands == []


def test_action_library_without_cooldown_keeps_phase_2_behavior():
    library, _, gesture, _ = make_library()

    first_result = library.execute(keys.WAVE_HAND)
    second_result = library.execute(keys.WAVE_HAND)

    assert first_result is None
    assert second_result is None
    assert gesture.commands == [
        (keys.WAVE_HAND, {}),
        (keys.WAVE_HAND, {}),
    ]


def test_action_library_import_has_no_ros_dependency():
    before = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}

    sys.modules.pop("ivastbot_hri.core.action_library", None)
    module = importlib.import_module("ivastbot_hri.core.action_library")

    after = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}
    assert module.ActionLibrary is not None
    assert after == before

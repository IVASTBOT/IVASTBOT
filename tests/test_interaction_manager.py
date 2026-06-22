import importlib
import sys

from ivastbot_hri.adapters.fake_face_adapter import FakeFaceAdapter
from ivastbot_hri.adapters.fake_gesture_adapter import FakeGestureAdapter
from ivastbot_hri.adapters.fake_navigation_adapter import FakeNavigationAdapter
from ivastbot_hri.core import keys
from ivastbot_hri.core.action_library import ActionLibrary
from ivastbot_hri.core.cooldown import CooldownManager
from ivastbot_hri.core.interaction_manager import InteractionManager


class FakeClock:
    def __init__(self, current_time=0.0):
        self.current_time = current_time

    def now(self):
        return self.current_time


def make_manager(cooldown_manager=None):
    face = FakeFaceAdapter()
    gesture = FakeGestureAdapter()
    navigation = FakeNavigationAdapter()
    action_library = ActionLibrary(
        face_adapter=face,
        gesture_adapter=gesture,
        navigation_adapter=navigation,
        cooldown_manager=cooldown_manager,
    )
    return InteractionManager(action_library), face, gesture, navigation


def expected_result(action_key, executed=True, reason="executed", payload=None, error=None):
    return {
        "action_key": action_key,
        "executed": executed,
        "reason": reason,
        "payload": dict(payload or {}),
        "error": error,
    }


def test_no_person_detected_triggers_idle():
    manager, face, gesture, navigation = make_manager()

    results = manager.handle_state(person_detected=False)

    assert results == [expected_result(keys.IDLE)]
    assert face.commands == [(keys.SHOW_NEUTRAL_FACE, {})]
    assert gesture.commands == []
    assert navigation.commands == []


def test_happy_expression_triggers_show_happy_face():
    manager, face, gesture, navigation = make_manager()

    results = manager.handle_state(
        person_detected=True,
        expression_key=keys.EXPR_HAPPY,
    )

    assert results == [expected_result(keys.SHOW_HAPPY_FACE)]
    assert face.commands == [(keys.SHOW_HAPPY_FACE, {})]
    assert gesture.commands == []
    assert navigation.commands == []


def test_neutral_expression_triggers_show_neutral_face():
    manager, face, _, _ = make_manager()

    manager.handle_state(person_detected=True, expression_key=keys.EXPR_NEUTRAL)

    assert face.commands == [(keys.SHOW_NEUTRAL_FACE, {})]


def test_confused_expression_triggers_show_thinking_face():
    manager, face, _, _ = make_manager()

    manager.handle_state(person_detected=True, expression_key=keys.EXPR_CONFUSED)

    assert face.commands == [(keys.SHOW_THINKING_FACE, {})]


def test_angry_expression_triggers_show_angry_face():
    manager, face, _, _ = make_manager()

    manager.handle_state(person_detected=True, expression_key=keys.EXPR_ANGRY)

    assert face.commands == [(keys.SHOW_ANGRY_FACE, {})]


def test_bored_expression_triggers_show_bored_face():
    manager, face, _, _ = make_manager()

    manager.handle_state(person_detected=True, expression_key=keys.EXPR_BORED)

    assert face.commands == [(keys.SHOW_BORED_FACE, {})]


def test_unknown_expression_triggers_show_neutral_face():
    manager, face, _, _ = make_manager()

    manager.handle_state(person_detected=True, expression_key=keys.EXPR_UNKNOWN)

    assert face.commands == [(keys.SHOW_NEUTRAL_FACE, {})]


def test_left_position_triggers_look_left():
    manager, face, _, _ = make_manager()

    manager.handle_state(
        person_detected=True,
        expression_key=None,
        person_position=keys.PERSON_LEFT,
    )

    assert face.commands == [
        (keys.SHOW_NEUTRAL_FACE, {}),
        (keys.LOOK_LEFT, {}),
    ]


def test_right_position_triggers_look_right():
    manager, face, _, _ = make_manager()

    manager.handle_state(
        person_detected=True,
        expression_key=None,
        person_position=keys.PERSON_RIGHT,
    )

    assert face.commands == [
        (keys.SHOW_NEUTRAL_FACE, {}),
        (keys.LOOK_RIGHT, {}),
    ]


def test_center_position_triggers_look_center():
    manager, face, _, _ = make_manager()

    manager.handle_state(
        person_detected=True,
        expression_key=None,
        person_position=keys.PERSON_CENTER,
    )

    assert face.commands == [
        (keys.SHOW_NEUTRAL_FACE, {}),
        (keys.LOOK_CENTER, {}),
    ]


def test_manager_returns_multiple_action_results_for_expression_and_position():
    manager, face, _, _ = make_manager()

    results = manager.handle_state(
        person_detected=True,
        expression_key=keys.EXPR_CONFUSED,
        person_position=keys.PERSON_LEFT,
    )

    assert results == [
        expected_result(keys.SHOW_THINKING_FACE),
        expected_result(keys.LOOK_LEFT),
    ]
    assert face.commands == [
        (keys.SHOW_THINKING_FACE, {}),
        (keys.LOOK_LEFT, {}),
    ]


def test_cooldown_through_action_library_blocks_repeated_actions():
    clock = FakeClock()
    cooldown = CooldownManager(
        default_cooldown_seconds=2.0,
        time_provider=clock.now,
    )
    manager, face, _, _ = make_manager(cooldown_manager=cooldown)

    first_results = manager.handle_state(
        person_detected=True,
        expression_key=keys.EXPR_HAPPY,
    )
    second_results = manager.handle_state(
        person_detected=True,
        expression_key=keys.EXPR_HAPPY,
    )

    assert first_results == [expected_result(keys.SHOW_HAPPY_FACE)]
    assert second_results == [
        expected_result(
            keys.SHOW_HAPPY_FACE,
            executed=False,
            reason="cooldown",
        )
    ]
    assert face.commands == [(keys.SHOW_HAPPY_FACE, {})]


def test_interaction_manager_import_has_no_ros_dependency():
    before = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}

    sys.modules.pop("ivastbot_hri.core.interaction_manager", None)
    module = importlib.import_module("ivastbot_hri.core.interaction_manager")

    after = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}
    assert module.InteractionManager is not None
    assert after == before

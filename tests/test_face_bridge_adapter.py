import importlib
import sys

import pytest

from ivastbot_hri.adapters.face_bridge_adapter import FaceBridgeAdapter
from ivastbot_hri.core import keys


@pytest.mark.parametrize(
    ("action_key", "expected_command"),
    [
        (keys.SHOW_NEUTRAL_FACE, {"emotion": "neutral"}),
        (keys.SHOW_HAPPY_FACE, {"emotion": "happy"}),
        (keys.SHOW_THINKING_FACE, {"emotion": "thinking"}),
        (keys.SHOW_GUIDING_FACE, {"emotion": "guiding"}),
        (keys.SHOW_ANGRY_FACE, {"emotion": "angry"}),
        (keys.SHOW_BORED_FACE, {"emotion": "bored"}),
    ],
)
def test_face_actions_map_to_emotions(action_key, expected_command):
    adapter = FaceBridgeAdapter()

    assert adapter.send(action_key) == expected_command
    assert adapter.sent_commands == [expected_command]


@pytest.mark.parametrize(
    ("action_key", "expected_command"),
    [
        (keys.LOOK_LEFT, {"gaze": "left"}),
        (keys.LOOK_RIGHT, {"gaze": "right"}),
        (keys.LOOK_CENTER, {"gaze": "center"}),
    ],
)
def test_look_actions_map_to_gaze_commands(action_key, expected_command):
    adapter = FaceBridgeAdapter()

    assert adapter.send(action_key) == expected_command
    assert adapter.sent_commands == [expected_command]


def test_payload_is_merged_and_preserved():
    adapter = FaceBridgeAdapter()

    ui_command = adapter.send(
        keys.SHOW_HAPPY_FACE,
        {"duration_ms": 1200, "source": "test"},
    )

    assert ui_command == {
        "duration_ms": 1200,
        "source": "test",
        "emotion": "happy",
    }
    assert adapter.sent_commands == [ui_command]


def test_action_key_mapping_wins_over_conflicting_payload():
    adapter = FaceBridgeAdapter()

    ui_command = adapter.send(keys.SHOW_NEUTRAL_FACE, {"emotion": "happy"})

    assert ui_command == {"emotion": "neutral"}


def test_sender_callback_is_called_if_provided():
    sent = []
    adapter = FaceBridgeAdapter(sender=sent.append)

    ui_command = adapter.send(keys.LOOK_LEFT, {"confidence": 0.8})

    assert ui_command == {"confidence": 0.8, "gaze": "left"}
    assert sent == [ui_command]
    assert adapter.sent_commands == [ui_command]


def test_unknown_face_command_raises_value_error():
    adapter = FaceBridgeAdapter()

    with pytest.raises(ValueError, match="Unknown face bridge command"):
        adapter.send(keys.WAVE_HAND)


def test_face_bridge_adapter_import_has_no_ros_dependency():
    before = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}

    sys.modules.pop("ivastbot_hri.adapters.face_bridge_adapter", None)
    module = importlib.import_module("ivastbot_hri.adapters.face_bridge_adapter")

    after = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}
    assert module.FaceBridgeAdapter is not None
    assert after == before

import importlib
import sys

from ivastbot_hri.demos.face_bridge_demo import generate_demo_commands


def test_demo_command_sequence_can_be_generated():
    assert generate_demo_commands() == [
        {"emotion": "neutral"},
        {"emotion": "happy"},
        {"emotion": "thinking"},
        {"emotion": "guiding"},
        {"gaze": "left"},
        {"gaze": "right"},
        {"gaze": "center"},
    ]


def test_demo_output_commands_include_expected_emotion_values():
    emotion_values = [
        command["emotion"]
        for command in generate_demo_commands()
        if "emotion" in command
    ]

    assert emotion_values == ["neutral", "happy", "thinking", "guiding"]


def test_demo_output_commands_include_expected_gaze_values():
    gaze_values = [
        command["gaze"]
        for command in generate_demo_commands()
        if "gaze" in command
    ]

    assert gaze_values == ["left", "right", "center"]


def test_demo_import_has_no_ros_camera_network_or_hardware_dependency():
    forbidden_roots = {
        "cv2",
        "mediapipe",
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

    sys.modules.pop("ivastbot_hri.demos.face_bridge_demo", None)
    module = importlib.import_module("ivastbot_hri.demos.face_bridge_demo")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.generate_demo_commands is not None
    assert after == before

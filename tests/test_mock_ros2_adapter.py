import importlib
import sys

from ivastbot_hri.adapters.interfaces import (
    FaceAdapter,
    GestureAdapter,
    NavigationAdapter,
)
from ivastbot_hri.adapters.mock_ros2_adapter import (
    MockROS2Adapter,
    MockROS2FaceAdapter,
    MockROS2GestureAdapter,
    MockROS2NavigationAdapter,
)
from ivastbot_hri.adapters.ros2_contracts import (
    FACE_COMMAND_CHANNEL,
    GESTURE_COMMAND_CHANNEL,
    NAVIGATION_COMMAND_CHANNEL,
    STOP_COMMAND_CHANNEL,
)
from ivastbot_hri.core import keys
from ivastbot_hri.core.action_library import ActionLibrary


def test_send_face_stores_face_contract():
    adapter = MockROS2Adapter()

    message = adapter.send_face(keys.SHOW_HAPPY_FACE, {"duration": 1.0})

    assert message["channel"] == FACE_COMMAND_CHANNEL
    assert message["command"] == keys.SHOW_HAPPY_FACE
    assert message["payload"] == {"duration": 1.0}
    assert adapter.sent_messages == [message]


def test_send_gesture_stores_gesture_contract():
    adapter = MockROS2Adapter()

    message = adapter.send_gesture(keys.WAVE_HAND)

    assert message["channel"] == GESTURE_COMMAND_CHANNEL
    assert message["command"] == keys.WAVE_HAND
    assert message["payload"] == {}
    assert adapter.sent_messages == [message]


def test_send_navigation_stores_navigation_contract():
    adapter = MockROS2Adapter()

    message = adapter.send_navigation(keys.GUIDE_TO_TARGET, {"target": "lobby"})

    assert message["channel"] == NAVIGATION_COMMAND_CHANNEL
    assert message["command"] == keys.GUIDE_TO_TARGET
    assert message["payload"] == {"target": "lobby"}
    assert adapter.sent_messages == [message]


def test_send_stop_stores_stop_contract():
    adapter = MockROS2Adapter()

    message = adapter.send_stop({"reason": "operator"})

    assert message["channel"] == STOP_COMMAND_CHANNEL
    assert message["command"] == keys.STOP_ACTION
    assert message["payload"] == {"reason": "operator"}
    assert adapter.sent_messages == [message]


def test_wrapper_adapters_expose_action_library_send_method():
    shared_adapter = MockROS2Adapter()
    face = MockROS2FaceAdapter(shared_adapter)
    gesture = MockROS2GestureAdapter(shared_adapter)
    navigation = MockROS2NavigationAdapter(shared_adapter)

    face_message = face.send(keys.SHOW_NEUTRAL_FACE)
    gesture_message = gesture.send(keys.POINT_LEFT, {"duration": 1.0})
    navigation_message = navigation.send(keys.GUIDE_TO_TARGET, {"target_id": "desk"})

    assert isinstance(face, FaceAdapter)
    assert isinstance(gesture, GestureAdapter)
    assert isinstance(navigation, NavigationAdapter)
    assert face_message["channel"] == FACE_COMMAND_CHANNEL
    assert gesture_message["channel"] == GESTURE_COMMAND_CHANNEL
    assert navigation_message["channel"] == NAVIGATION_COMMAND_CHANNEL
    assert shared_adapter.sent_messages == [
        face_message,
        gesture_message,
        navigation_message,
    ]


def test_wrapper_adapters_convert_stop_action_to_stop_contract():
    shared_adapter = MockROS2Adapter()
    gesture = MockROS2GestureAdapter(shared_adapter)
    navigation = MockROS2NavigationAdapter(shared_adapter)

    gesture_message = gesture.send(keys.STOP_ACTION)
    navigation_message = navigation.send(keys.STOP_ACTION, {"reason": "blocked"})

    assert gesture_message["channel"] == STOP_COMMAND_CHANNEL
    assert gesture_message["payload"] == {}
    assert navigation_message["channel"] == STOP_COMMAND_CHANNEL
    assert navigation_message["payload"] == {"reason": "blocked"}


def test_action_library_can_use_mock_ros2_wrapper_adapters():
    shared_adapter = MockROS2Adapter()
    library = ActionLibrary(
        face_adapter=MockROS2FaceAdapter(shared_adapter),
        gesture_adapter=MockROS2GestureAdapter(shared_adapter),
        navigation_adapter=MockROS2NavigationAdapter(shared_adapter),
    )

    happy_result = library.execute(keys.SHOW_HAPPY_FACE, {"duration": 1.0})
    wave_result = library.execute(keys.WAVE_HAND)
    guide_result = library.execute(keys.GUIDE_TO_TARGET, {"target_id": "desk"})

    assert happy_result.executed is True
    assert wave_result.executed is True
    assert guide_result.executed is True
    assert shared_adapter.sent_messages == [
        {
            "channel": FACE_COMMAND_CHANNEL,
            "command": keys.SHOW_HAPPY_FACE,
            "payload": {"duration": 1.0},
            "timestamp": None,
            "source": "ivastbot_hri",
            "correlation_id": None,
        },
        {
            "channel": GESTURE_COMMAND_CHANNEL,
            "command": keys.WAVE_HAND,
            "payload": {},
            "timestamp": None,
            "source": "ivastbot_hri",
            "correlation_id": None,
        },
        {
            "channel": NAVIGATION_COMMAND_CHANNEL,
            "command": keys.GUIDE_TO_TARGET,
            "payload": {"target_id": "desk"},
            "timestamp": None,
            "source": "ivastbot_hri",
            "correlation_id": None,
        },
    ]


def test_mock_ros2_adapter_import_has_no_ros_or_hardware_dependency():
    forbidden_roots = {
        "cv2",
        "mediapipe",
        "openni",
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

    sys.modules.pop("ivastbot_hri.adapters.mock_ros2_adapter", None)
    module = importlib.import_module("ivastbot_hri.adapters.mock_ros2_adapter")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.MockROS2Adapter is not None
    assert after == before

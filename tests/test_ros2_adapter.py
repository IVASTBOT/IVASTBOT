import importlib
import sys
from pathlib import Path

import pytest

from ivastbot_hri.adapters.interfaces import (
    FaceAdapter,
    GestureAdapter,
    NavigationAdapter,
)
from ivastbot_hri.adapters.ros2_adapter import (
    ROS2_RUNTIME_UNAVAILABLE_MESSAGE,
    ROS2Adapter,
    ROS2FaceAdapter,
    ROS2GestureAdapter,
    ROS2NavigationAdapter,
)
from ivastbot_hri.adapters.ros2_contracts import (
    FACE_COMMAND_CHANNEL,
    GESTURE_COMMAND_CHANNEL,
    NAVIGATION_COMMAND_CHANNEL,
    STOP_COMMAND_CHANNEL,
)
from ivastbot_hri.core import keys
from ivastbot_hri.core.action_library import ActionLibrary


class FakePublisher:
    def __init__(self, topic):
        self.topic = topic
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class FakeNode:
    def __init__(self):
        self.created_publishers = []

    def create_publisher(self, message_type, topic, queue_size):
        publisher = FakePublisher(topic)
        self.created_publishers.append(
            {
                "message_type": message_type,
                "topic": topic,
                "queue_size": queue_size,
                "publisher": publisher,
            }
        )
        return publisher


def test_importing_ros2_adapter_does_not_require_rclpy():
    before = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}

    sys.modules.pop("ivastbot_hri.adapters.ros2_adapter", None)
    module = importlib.import_module("ivastbot_hri.adapters.ros2_adapter")

    after = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}
    assert module.ROS2Adapter is not None
    assert after == before


def test_constructing_ros2_adapter_with_fake_node_works_without_rclpy():
    node = FakeNode()

    adapter = ROS2Adapter(node=node, topic_prefix="ivastbot/test")

    assert adapter.node is node
    assert adapter.topic_prefix == "/ivastbot/test"
    assert adapter.published_messages == []


def test_publish_face_creates_and_publishes_face_contract():
    node = FakeNode()
    adapter = ROS2Adapter(node=node)

    message = adapter.publish_face(keys.SHOW_HAPPY_FACE, {"duration": 1.0})

    assert message["channel"] == FACE_COMMAND_CHANNEL
    assert message["command"] == keys.SHOW_HAPPY_FACE
    assert message["payload"] == {"duration": 1.0}
    assert adapter.published_messages == [message]
    assert node.created_publishers[0]["topic"] == "/ivastbot/hri/hri/face/command"
    assert node.created_publishers[0]["publisher"].messages == [message]


def test_publish_gesture_creates_and_publishes_gesture_contract():
    node = FakeNode()
    adapter = ROS2Adapter(node=node)

    message = adapter.publish_gesture(keys.WAVE_HAND)

    assert message["channel"] == GESTURE_COMMAND_CHANNEL
    assert message["command"] == keys.WAVE_HAND
    assert message["payload"] == {}
    assert adapter.published_messages == [message]
    assert node.created_publishers[0]["topic"] == "/ivastbot/hri/hri/gesture/command"
    assert node.created_publishers[0]["publisher"].messages == [message]


def test_publish_navigation_creates_and_publishes_navigation_contract():
    node = FakeNode()
    adapter = ROS2Adapter(node=node)

    message = adapter.publish_navigation(keys.GUIDE_TO_TARGET, {"target": "lobby"})

    assert message["channel"] == NAVIGATION_COMMAND_CHANNEL
    assert message["command"] == keys.GUIDE_TO_TARGET
    assert message["payload"] == {"target": "lobby"}
    assert adapter.published_messages == [message]
    assert node.created_publishers[0]["topic"] == "/ivastbot/hri/hri/navigation/command"
    assert node.created_publishers[0]["publisher"].messages == [message]


def test_publish_stop_creates_and_publishes_stop_contract():
    node = FakeNode()
    adapter = ROS2Adapter(node=node)

    message = adapter.publish_stop({"reason": "operator"})

    assert message["channel"] == STOP_COMMAND_CHANNEL
    assert message["command"] == keys.STOP_ACTION
    assert message["payload"] == {"reason": "operator"}
    assert adapter.published_messages == [message]
    assert node.created_publishers[0]["topic"] == "/ivastbot/hri/hri/stop/command"
    assert node.created_publishers[0]["publisher"].messages == [message]


def test_wrapper_adapters_expose_action_library_send_method():
    adapter = ROS2Adapter(node=FakeNode())
    face = ROS2FaceAdapter(adapter)
    gesture = ROS2GestureAdapter(adapter)
    navigation = ROS2NavigationAdapter(adapter)

    face_message = face.send(keys.SHOW_NEUTRAL_FACE)
    gesture_message = gesture.send(keys.POINT_LEFT, {"duration": 1.0})
    navigation_message = navigation.send(keys.GUIDE_TO_TARGET, {"target_id": "desk"})

    assert isinstance(face, FaceAdapter)
    assert isinstance(gesture, GestureAdapter)
    assert isinstance(navigation, NavigationAdapter)
    assert face_message["channel"] == FACE_COMMAND_CHANNEL
    assert gesture_message["channel"] == GESTURE_COMMAND_CHANNEL
    assert navigation_message["channel"] == NAVIGATION_COMMAND_CHANNEL
    assert adapter.published_messages == [
        face_message,
        gesture_message,
        navigation_message,
    ]


def test_wrapper_adapters_route_stop_actions_to_stop_contracts():
    adapter = ROS2Adapter(node=FakeNode())
    gesture = ROS2GestureAdapter(adapter)
    navigation = ROS2NavigationAdapter(adapter)

    gesture_message = gesture.send(keys.STOP_ACTION)
    navigation_message = navigation.send(keys.STOP_ACTION, {"reason": "blocked"})

    assert gesture_message["channel"] == STOP_COMMAND_CHANNEL
    assert gesture_message["payload"] == {}
    assert navigation_message["channel"] == STOP_COMMAND_CHANNEL
    assert navigation_message["payload"] == {"reason": "blocked"}


def test_action_library_can_use_ros2_wrapper_adapters_with_fake_node():
    adapter = ROS2Adapter(node=FakeNode())
    library = ActionLibrary(
        face_adapter=ROS2FaceAdapter(adapter),
        gesture_adapter=ROS2GestureAdapter(adapter),
        navigation_adapter=ROS2NavigationAdapter(adapter),
    )

    happy_result = library.execute(keys.SHOW_HAPPY_FACE, {"duration": 1.0})
    wave_result = library.execute(keys.WAVE_HAND)
    guide_result = library.execute(keys.GUIDE_TO_TARGET, {"target_id": "desk"})

    assert happy_result.executed is True
    assert wave_result.executed is True
    assert guide_result.executed is True
    assert adapter.published_messages == [
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


def test_creating_real_adapter_without_rclpy_raises_clear_runtime_error(
    monkeypatch,
):
    real_import_module = importlib.import_module

    def fake_import_module(name, package=None):
        if name == "rclpy":
            raise ImportError("no ROS runtime")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match=ROS2_RUNTIME_UNAVAILABLE_MESSAGE):
        ROS2Adapter()


def test_core_files_do_not_reference_rclpy():
    core_dir = Path("ivastbot_hri/core")

    for path in core_dir.glob("*.py"):
        assert "rclpy" not in path.read_text(encoding="utf-8")

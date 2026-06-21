"""ROS 2 adapter skeleton for future real robot integration."""

import importlib

from ivastbot_hri.adapters.ros2_contracts import (
    FACE_COMMAND_CHANNEL,
    GESTURE_COMMAND_CHANNEL,
    NAVIGATION_COMMAND_CHANNEL,
    STOP_COMMAND_CHANNEL,
    build_face_contract,
    build_gesture_contract,
    build_navigation_contract,
    build_stop_contract,
)
from ivastbot_hri.core import keys

ROS2_RUNTIME_UNAVAILABLE_MESSAGE = (
    "ROS 2 runtime is not available. Install ROS 2 and run this adapter in a "
    "ROS 2 environment."
)


class ROS2Adapter:
    """Publish HRI contract dictionaries through an injected ROS 2-like node."""

    def __init__(self, node=None, topic_prefix: str = "/ivastbot/hri"):
        self.node = node if node is not None else self._create_default_node()
        self.topic_prefix = _normalize_topic_prefix(topic_prefix)
        self._publishers = {}
        self.published_messages = []

    def publish_face(self, command: str, payload: dict | None = None) -> dict:
        contract = build_face_contract(command, payload)
        return self._publish(contract)

    def publish_gesture(self, command: str, payload: dict | None = None) -> dict:
        contract = build_gesture_contract(command, payload)
        return self._publish(contract)

    def publish_navigation(self, command: str, payload: dict | None = None) -> dict:
        contract = build_navigation_contract(command, payload)
        return self._publish(contract)

    def publish_stop(self, payload: dict | None = None) -> dict:
        contract = build_stop_contract(payload)
        return self._publish(contract)

    def _publish(self, contract: dict) -> dict:
        self.published_messages.append(contract)
        publisher = self._get_publisher(contract["channel"])
        publisher.publish(contract)
        return contract

    def _get_publisher(self, channel: str):
        if channel not in self._publishers:
            topic = self._topic_for_channel(channel)
            self._publishers[channel] = self.node.create_publisher(dict, topic, 10)
        return self._publishers[channel]

    def _topic_for_channel(self, channel: str) -> str:
        topic_suffix = channel.replace(".", "/")
        return f"{self.topic_prefix}/{topic_suffix}"

    @staticmethod
    def _create_default_node():
        try:
            rclpy = importlib.import_module("rclpy")
        except ImportError as error:
            raise RuntimeError(ROS2_RUNTIME_UNAVAILABLE_MESSAGE) from error

        if hasattr(rclpy, "create_node"):
            return rclpy.create_node("ivastbot_hri_adapter")

        raise RuntimeError(
            "ROS 2 runtime was found, but a node could not be created. "
            "Provide a node-like object or run inside a supported ROS 2 runtime."
        )


class ROS2FaceAdapter:
    """ActionLibrary-compatible face adapter backed by ROS2Adapter."""

    def __init__(self, ros2_adapter: ROS2Adapter):
        self.ros2_adapter = ros2_adapter

    def send(self, command: str, payload: dict | None = None) -> dict:
        return self.ros2_adapter.publish_face(command, payload)


class ROS2GestureAdapter:
    """ActionLibrary-compatible gesture adapter backed by ROS2Adapter."""

    def __init__(self, ros2_adapter: ROS2Adapter):
        self.ros2_adapter = ros2_adapter

    def send(self, command: str, payload: dict | None = None) -> dict:
        if command == keys.STOP_ACTION:
            return self.ros2_adapter.publish_stop(payload)
        return self.ros2_adapter.publish_gesture(command, payload)


class ROS2NavigationAdapter:
    """ActionLibrary-compatible navigation adapter backed by ROS2Adapter."""

    def __init__(self, ros2_adapter: ROS2Adapter):
        self.ros2_adapter = ros2_adapter

    def send(self, command: str, payload: dict | None = None) -> dict:
        if command == keys.STOP_ACTION:
            return self.ros2_adapter.publish_stop(payload)
        return self.ros2_adapter.publish_navigation(command, payload)


def _normalize_topic_prefix(topic_prefix: str) -> str:
    normalized = topic_prefix.strip().rstrip("/")
    if not normalized:
        return "/ivastbot/hri"
    if not normalized.startswith("/"):
        return f"/{normalized}"
    return normalized


__all__ = (
    "ROS2_RUNTIME_UNAVAILABLE_MESSAGE",
    "ROS2Adapter",
    "ROS2FaceAdapter",
    "ROS2GestureAdapter",
    "ROS2NavigationAdapter",
)

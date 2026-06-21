"""In-memory ROS 2-style adapters for local HRI integration tests."""

from ivastbot_hri.adapters.ros2_contracts import (
    build_face_contract,
    build_gesture_contract,
    build_navigation_contract,
    build_stop_contract,
)
from ivastbot_hri.core import keys


class MockROS2Adapter:
    """Record future ROS 2-style contract messages without ROS 2 runtime."""

    def __init__(self):
        self._sent_messages = []

    @property
    def sent_messages(self) -> list[dict]:
        return self._sent_messages

    def send_face(self, command: str, payload: dict | None = None) -> dict:
        message = build_face_contract(command, payload)
        self._sent_messages.append(message)
        return message

    def send_gesture(self, command: str, payload: dict | None = None) -> dict:
        message = build_gesture_contract(command, payload)
        self._sent_messages.append(message)
        return message

    def send_navigation(self, command: str, payload: dict | None = None) -> dict:
        message = build_navigation_contract(command, payload)
        self._sent_messages.append(message)
        return message

    def send_stop(self, payload: dict | None = None) -> dict:
        message = build_stop_contract(payload)
        self._sent_messages.append(message)
        return message


class MockROS2FaceAdapter:
    """ActionLibrary-compatible wrapper for future face command publishing."""

    def __init__(self, mock_ros2_adapter: MockROS2Adapter | None = None):
        self.mock_ros2_adapter = mock_ros2_adapter or MockROS2Adapter()

    @property
    def sent_messages(self) -> list[dict]:
        return self.mock_ros2_adapter.sent_messages

    def send(self, command: str, payload: dict | None = None) -> dict:
        return self.mock_ros2_adapter.send_face(command, payload)


class MockROS2GestureAdapter:
    """ActionLibrary-compatible wrapper for future gesture command publishing."""

    def __init__(self, mock_ros2_adapter: MockROS2Adapter | None = None):
        self.mock_ros2_adapter = mock_ros2_adapter or MockROS2Adapter()

    @property
    def sent_messages(self) -> list[dict]:
        return self.mock_ros2_adapter.sent_messages

    def send(self, command: str, payload: dict | None = None) -> dict:
        if command == keys.STOP_ACTION:
            return self.mock_ros2_adapter.send_stop(payload)
        return self.mock_ros2_adapter.send_gesture(command, payload)


class MockROS2NavigationAdapter:
    """ActionLibrary-compatible wrapper for future navigation command publishing."""

    def __init__(self, mock_ros2_adapter: MockROS2Adapter | None = None):
        self.mock_ros2_adapter = mock_ros2_adapter or MockROS2Adapter()

    @property
    def sent_messages(self) -> list[dict]:
        return self.mock_ros2_adapter.sent_messages

    def send(self, command: str, payload: dict | None = None) -> dict:
        if command == keys.STOP_ACTION:
            return self.mock_ros2_adapter.send_stop(payload)
        return self.mock_ros2_adapter.send_navigation(command, payload)


__all__ = (
    "MockROS2Adapter",
    "MockROS2FaceAdapter",
    "MockROS2GestureAdapter",
    "MockROS2NavigationAdapter",
)

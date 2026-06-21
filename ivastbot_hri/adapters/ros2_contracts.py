"""Dependency-free ROS 2 contract shapes for future HRI integration."""

from ivastbot_hri.core import keys

FACE_COMMAND_CHANNEL = "hri.face.command"
GESTURE_COMMAND_CHANNEL = "hri.gesture.command"
NAVIGATION_COMMAND_CHANNEL = "hri.navigation.command"
STOP_COMMAND_CHANNEL = "hri.stop.command"
STATUS_EVENT_CHANNEL = "hri.status.event"

DEFAULT_SOURCE = "ivastbot_hri"

REQUIRED_CONTRACT_FIELDS = (
    "channel",
    "command",
    "payload",
    "timestamp",
    "source",
    "correlation_id",
)


def build_face_contract(command: str, payload: dict | None = None) -> dict:
    """Build a logical future ROS 2 face command contract."""
    return _build_contract(FACE_COMMAND_CHANNEL, command, payload)


def build_gesture_contract(command: str, payload: dict | None = None) -> dict:
    """Build a logical future ROS 2 gesture command contract."""
    return _build_contract(GESTURE_COMMAND_CHANNEL, command, payload)


def build_navigation_contract(command: str, payload: dict | None = None) -> dict:
    """Build a logical future ROS 2 navigation command contract."""
    return _build_contract(NAVIGATION_COMMAND_CHANNEL, command, payload)


def build_stop_contract(payload: dict | None = None) -> dict:
    """Build a logical future ROS 2 stop command contract."""
    return _build_contract(STOP_COMMAND_CHANNEL, keys.STOP_ACTION, payload)


def build_status_event_contract(command: str, payload: dict | None = None) -> dict:
    """Build a logical future ROS 2 status/event feedback contract."""
    return _build_contract(STATUS_EVENT_CHANNEL, command, payload)


def validate_contract(contract: dict) -> tuple[bool, str | None]:
    """Validate the minimal shape expected by future ROS 2 adapters."""
    if not isinstance(contract, dict):
        return False, "contract must be a dict"

    missing_fields = [
        field for field in REQUIRED_CONTRACT_FIELDS if field not in contract
    ]
    if missing_fields:
        return False, f"missing required fields: {', '.join(missing_fields)}"

    if not isinstance(contract["channel"], str) or not contract["channel"]:
        return False, "channel must be a non-empty string"

    if not isinstance(contract["command"], str) or not contract["command"]:
        return False, "command must be a non-empty string"

    if not isinstance(contract["payload"], dict):
        return False, "payload must be a dict"

    timestamp = contract["timestamp"]
    if timestamp is not None and not isinstance(timestamp, (int, float)):
        return False, "timestamp must be a number or None"

    if not isinstance(contract["source"], str) or not contract["source"]:
        return False, "source must be a non-empty string"

    correlation_id = contract["correlation_id"]
    if correlation_id is not None and not isinstance(correlation_id, str):
        return False, "correlation_id must be a string or None"

    return True, None


def _build_contract(channel: str, command: str, payload: dict | None = None) -> dict:
    return {
        "channel": channel,
        "command": command,
        "payload": dict(payload or {}),
        "timestamp": None,
        "source": DEFAULT_SOURCE,
        "correlation_id": None,
    }


__all__ = (
    "DEFAULT_SOURCE",
    "FACE_COMMAND_CHANNEL",
    "GESTURE_COMMAND_CHANNEL",
    "NAVIGATION_COMMAND_CHANNEL",
    "STOP_COMMAND_CHANNEL",
    "STATUS_EVENT_CHANNEL",
    "REQUIRED_CONTRACT_FIELDS",
    "build_face_contract",
    "build_gesture_contract",
    "build_navigation_contract",
    "build_stop_contract",
    "build_status_event_contract",
    "validate_contract",
)

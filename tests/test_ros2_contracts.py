import importlib
import sys

from ivastbot_hri.adapters.ros2_contracts import (
    FACE_COMMAND_CHANNEL,
    GESTURE_COMMAND_CHANNEL,
    NAVIGATION_COMMAND_CHANNEL,
    STATUS_EVENT_CHANNEL,
    STOP_COMMAND_CHANNEL,
    build_face_contract,
    build_gesture_contract,
    build_navigation_contract,
    build_status_event_contract,
    build_stop_contract,
    validate_contract,
)
from ivastbot_hri.core import keys


def test_face_contract_has_expected_channel_and_command():
    contract = build_face_contract(keys.SHOW_HAPPY_FACE, {"duration": 1.0})

    assert contract["channel"] == FACE_COMMAND_CHANNEL
    assert contract["command"] == keys.SHOW_HAPPY_FACE
    assert contract["payload"] == {"duration": 1.0}


def test_gesture_contract_has_expected_channel_and_default_payload():
    contract = build_gesture_contract(keys.WAVE_HAND)

    assert contract["channel"] == GESTURE_COMMAND_CHANNEL
    assert contract["command"] == keys.WAVE_HAND
    assert contract["payload"] == {}


def test_navigation_contract_has_expected_channel_and_payload():
    contract = build_navigation_contract(
        keys.GUIDE_TO_TARGET,
        {"target_id": "front_desk"},
    )

    assert contract["channel"] == NAVIGATION_COMMAND_CHANNEL
    assert contract["command"] == keys.GUIDE_TO_TARGET
    assert contract["payload"] == {"target_id": "front_desk"}


def test_stop_contract_has_expected_channel_and_stop_command():
    contract = build_stop_contract({"reason": "manual"})

    assert contract["channel"] == STOP_COMMAND_CHANNEL
    assert contract["command"] == keys.STOP_ACTION
    assert contract["payload"] == {"reason": "manual"}


def test_status_event_contract_has_expected_channel():
    contract = build_status_event_contract("ACTION_COMPLETE", {"action": keys.WAVE_HAND})

    assert contract["channel"] == STATUS_EVENT_CHANNEL
    assert contract["command"] == "ACTION_COMPLETE"
    assert contract["payload"] == {"action": keys.WAVE_HAND}


def test_contracts_include_required_future_ros_fields():
    contract = build_face_contract(keys.SHOW_NEUTRAL_FACE)

    assert contract["timestamp"] is None
    assert contract["source"] == "ivastbot_hri"
    assert contract["correlation_id"] is None


def test_validate_contract_accepts_valid_contracts():
    contract = build_gesture_contract(keys.POINT_LEFT, {"duration": 1.0})

    is_valid, error = validate_contract(contract)

    assert is_valid is True
    assert error is None


def test_validate_contract_rejects_missing_required_fields():
    is_valid, error = validate_contract({"channel": FACE_COMMAND_CHANNEL})

    assert is_valid is False
    assert "missing required fields" in error


def test_validate_contract_rejects_invalid_field_types():
    contract = build_face_contract(keys.SHOW_HAPPY_FACE)
    contract["payload"] = []

    is_valid, error = validate_contract(contract)

    assert is_valid is False
    assert error == "payload must be a dict"


def test_ros2_contracts_import_has_no_ros_dependency():
    before = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}

    sys.modules.pop("ivastbot_hri.adapters.ros2_contracts", None)
    module = importlib.import_module("ivastbot_hri.adapters.ros2_contracts")

    after = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}
    assert module.build_face_contract is not None
    assert after == before

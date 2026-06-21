import importlib
import sys

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.core.action_contracts import (
    ActionContractError,
    validate_action_payload,
)


@pytest.mark.parametrize(
    "action_key",
    [
        keys.WAVE_HAND,
        keys.POINT_LEFT,
        keys.POINT_RIGHT,
        keys.POINT_FORWARD,
        keys.SHOW_NEUTRAL_FACE,
        keys.SHOW_HAPPY_FACE,
        keys.SHOW_THINKING_FACE,
        keys.SHOW_GUIDING_FACE,
    ],
)
def test_duration_actions_accept_empty_or_optional_duration(action_key):
    assert validate_action_payload(action_key) == {}
    assert validate_action_payload(action_key, {"duration": 1.0}) == {
        "duration": 1.0
    }
    assert validate_action_payload(action_key, {"duration_ms": 500}) == {
        "duration_ms": 500
    }


@pytest.mark.parametrize(
    "action_key",
    [
        keys.IDLE,
        keys.LOOK_LEFT,
        keys.LOOK_RIGHT,
        keys.LOOK_CENTER,
        keys.STOP_ACTION,
    ],
)
def test_empty_payload_actions_accept_only_empty_payload(action_key):
    assert validate_action_payload(action_key) == {}

    with pytest.raises(ActionContractError, match="unsupported keys"):
        validate_action_payload(action_key, {"duration": 1.0})


def test_guide_to_target_requires_target_or_target_id():
    assert validate_action_payload(keys.GUIDE_TO_TARGET, {"target": "front"}) == {
        "target": "front"
    }
    assert validate_action_payload(keys.GUIDE_TO_TARGET, {"target_id": "A1"}) == {
        "target_id": "A1"
    }

    with pytest.raises(ActionContractError, match="requires 'target' or 'target_id'"):
        validate_action_payload(keys.GUIDE_TO_TARGET)


def test_guide_to_target_preserves_extra_payload_fields():
    payload = {"target": "front", "speed": "slow"}

    assert validate_action_payload(keys.GUIDE_TO_TARGET, payload) == payload


def test_duration_payload_rejects_unsupported_keys():
    with pytest.raises(ActionContractError, match="unsupported keys"):
        validate_action_payload(keys.WAVE_HAND, {"direction": "left"})


@pytest.mark.parametrize("duration", [-1, True, "fast"])
def test_duration_payload_rejects_invalid_duration_values(duration):
    with pytest.raises(ActionContractError):
        validate_action_payload(keys.WAVE_HAND, {"duration": duration})


def test_unknown_action_key_raises_contract_error():
    with pytest.raises(ActionContractError, match="Unknown action key"):
        validate_action_payload("UNKNOWN_ACTION")


def test_validate_action_payload_returns_defensive_copy():
    payload = {"duration": 1.0}
    result = validate_action_payload(keys.WAVE_HAND, payload)

    payload["duration"] = 2.0

    assert result == {"duration": 1.0}


def test_action_contracts_import_has_no_ros_dependency():
    before = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}

    sys.modules.pop("ivastbot_hri.core.action_contracts", None)
    module = importlib.import_module("ivastbot_hri.core.action_contracts")

    after = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}
    assert module.validate_action_payload is not None
    assert after == before

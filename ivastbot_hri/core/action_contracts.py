"""Payload contracts for high-level HRI actions."""

from ivastbot_hri.core import keys


class ActionContractError(ValueError):
    """Raised when an action key or payload violates its contract."""


_DURATION_KEYS = {"duration", "duration_ms"}

_DURATION_PAYLOAD_ACTIONS = {
    keys.WAVE_HAND,
    keys.POINT_LEFT,
    keys.POINT_RIGHT,
    keys.POINT_FORWARD,
    keys.SHOW_NEUTRAL_FACE,
    keys.SHOW_HAPPY_FACE,
    keys.SHOW_THINKING_FACE,
    keys.SHOW_GUIDING_FACE,
}

_EMPTY_PAYLOAD_ACTIONS = {
    keys.IDLE,
    keys.LOOK_LEFT,
    keys.LOOK_RIGHT,
    keys.LOOK_CENTER,
    keys.STOP_ACTION,
}

_GUIDE_TARGET_KEYS = {"target", "target_id"}


def validate_action_payload(action_key: str, payload: dict | None = None) -> dict:
    """Validate and return a defensive copy of an action payload."""
    if action_key not in keys.ACTION_KEYS:
        raise ActionContractError(f"Unknown action key: {action_key!r}")

    command_payload = dict(payload or {})

    if action_key in _DURATION_PAYLOAD_ACTIONS:
        _validate_allowed_keys(action_key, command_payload, _DURATION_KEYS)
        _validate_duration_values(action_key, command_payload)
        return command_payload

    if action_key in _EMPTY_PAYLOAD_ACTIONS:
        _validate_allowed_keys(action_key, command_payload, set())
        return command_payload

    if action_key == keys.GUIDE_TO_TARGET:
        _validate_guide_payload(action_key, command_payload)
        return command_payload

    raise ActionContractError(f"No payload contract defined for {action_key!r}")


def _validate_allowed_keys(action_key: str, payload: dict, allowed_keys: set[str]):
    unsupported_keys = sorted(set(payload) - allowed_keys)
    if unsupported_keys:
        raise ActionContractError(
            f"{action_key} payload has unsupported keys: {unsupported_keys}"
        )


def _validate_duration_values(action_key: str, payload: dict):
    for duration_key in _DURATION_KEYS.intersection(payload):
        duration = payload[duration_key]
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ActionContractError(
                f"{action_key} payload field {duration_key!r} must be numeric"
            )
        if duration < 0:
            raise ActionContractError(
                f"{action_key} payload field {duration_key!r} must be non-negative"
            )


def _validate_guide_payload(action_key: str, payload: dict):
    if not any(_has_value(payload.get(target_key)) for target_key in _GUIDE_TARGET_KEYS):
        raise ActionContractError(
            f"{action_key} payload requires 'target' or 'target_id'"
        )


def _has_value(value) -> bool:
    return value is not None and value != ""

from ivastbot_hri.core.action_result import ActionResult


def test_action_result_stores_fields_and_converts_to_dict():
    result = ActionResult(
        action_key="WAVE_HAND",
        executed=True,
        reason="executed",
        payload={"duration": 1.0},
    )

    assert result.action_key == "WAVE_HAND"
    assert result.executed is True
    assert result.reason == "executed"
    assert result.payload == {"duration": 1.0}
    assert result.error is None
    assert result.to_dict() == {
        "action_key": "WAVE_HAND",
        "executed": True,
        "reason": "executed",
        "payload": {"duration": 1.0},
        "error": None,
    }


def test_action_result_defaults_payload_to_empty_dict():
    result = ActionResult(
        action_key="IDLE",
        executed=False,
        reason="cooldown",
    )

    assert result.payload == {}
    assert result.to_dict()["payload"] == {}


def test_action_result_copies_payload_input_and_output():
    payload = {"duration_ms": 500}
    result = ActionResult(
        action_key="SHOW_HAPPY_FACE",
        executed=True,
        reason="executed",
        payload=payload,
    )

    payload["duration_ms"] = 1000
    output = result.to_dict()
    output["payload"]["duration_ms"] = 2000

    assert result.payload == {"duration_ms": 500}


def test_action_result_includes_error_when_present():
    result = ActionResult(
        action_key="UNKNOWN",
        executed=False,
        reason="invalid_action",
        payload={},
        error="Unknown action key",
    )

    assert result.to_dict()["error"] == "Unknown action key"

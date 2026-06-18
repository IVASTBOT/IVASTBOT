"""Deterministic high-level HRI interaction decisions."""

from ivastbot_hri.core import keys


class InteractionManager:
    """Convert simple perception state into high-level HRI actions."""

    _EXPRESSION_ACTIONS = {
        keys.EXPR_HAPPY: keys.SHOW_HAPPY_FACE,
        keys.EXPR_NEUTRAL: keys.SHOW_NEUTRAL_FACE,
        keys.EXPR_CONFUSED: keys.SHOW_THINKING_FACE,
        # Surprise is treated as a positive social cue for now.
        keys.EXPR_SURPRISE: keys.SHOW_HAPPY_FACE,
        keys.EXPR_UNKNOWN: keys.SHOW_NEUTRAL_FACE,
        None: keys.SHOW_NEUTRAL_FACE,
    }

    _POSITION_ACTIONS = {
        keys.PERSON_LEFT: keys.LOOK_LEFT,
        keys.PERSON_RIGHT: keys.LOOK_RIGHT,
        keys.PERSON_CENTER: keys.LOOK_CENTER,
        "left": keys.LOOK_LEFT,
        "right": keys.LOOK_RIGHT,
        "center": keys.LOOK_CENTER,
    }

    def __init__(self, action_library):
        self.action_library = action_library

    def handle_state(
        self,
        person_detected: bool,
        expression_key: str | None = None,
        person_position: str | None = None,
        payload: dict | None = None,
    ) -> list[dict]:
        """Handle one perception snapshot and return action execution results."""
        command_payload = dict(payload or {})
        results = []

        if not person_detected:
            results.append(self._execute(keys.IDLE, command_payload))
            return results

        expression_action = self._EXPRESSION_ACTIONS.get(
            expression_key,
            keys.SHOW_NEUTRAL_FACE,
        )
        results.append(self._execute(expression_action, command_payload))

        position_action = self._POSITION_ACTIONS.get(person_position)
        if position_action is not None:
            results.append(self._execute(position_action, command_payload))

        return results

    def _execute(self, action_key: str, payload: dict) -> dict:
        result = self.action_library.execute(action_key, payload)
        if result is not None:
            return result

        return {
            "action_key": action_key,
            "executed": True,
            "reason": "executed",
        }


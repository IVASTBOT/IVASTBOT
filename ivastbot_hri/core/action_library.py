"""High-level HRI action routing."""

from ivastbot_hri.core import keys


class ActionLibrary:
    """Route high-level action keys to optional local adapters."""

    _FACE_ACTIONS = {
        keys.SHOW_NEUTRAL_FACE,
        keys.SHOW_HAPPY_FACE,
        keys.SHOW_THINKING_FACE,
        keys.SHOW_GUIDING_FACE,
        keys.LOOK_LEFT,
        keys.LOOK_RIGHT,
        keys.LOOK_CENTER,
    }
    _GESTURE_ACTIONS = {
        keys.WAVE_HAND,
        keys.POINT_LEFT,
        keys.POINT_RIGHT,
        keys.POINT_FORWARD,
    }
    _NAVIGATION_ACTIONS = {
        keys.GUIDE_TO_TARGET,
    }

    def __init__(
        self,
        face_adapter=None,
        gesture_adapter=None,
        navigation_adapter=None,
        cooldown_manager=None,
    ):
        self.face_adapter = face_adapter
        self.gesture_adapter = gesture_adapter
        self.navigation_adapter = navigation_adapter
        self.cooldown_manager = cooldown_manager

    def execute(self, action_key: str, payload: dict | None = None):
        """Execute one high-level action using the configured adapters."""
        if action_key not in keys.ACTION_KEYS:
            raise ValueError(f"Unknown action key: {action_key!r}")

        command_payload = dict(payload or {})
        use_cooldown = self.cooldown_manager is not None

        if use_cooldown and not self.cooldown_manager.can_execute(action_key):
            return {
                "action_key": action_key,
                "executed": False,
                "reason": "cooldown",
            }

        if action_key == keys.IDLE:
            self._send(self.face_adapter, keys.SHOW_NEUTRAL_FACE, command_payload)
            return self._finish(action_key, use_cooldown)

        if action_key == keys.STOP_ACTION:
            self._send(self.gesture_adapter, keys.STOP_ACTION, command_payload)
            self._send(self.navigation_adapter, keys.STOP_ACTION, command_payload)
            return self._finish(action_key, use_cooldown)

        if action_key in self._FACE_ACTIONS:
            self._send(self.face_adapter, action_key, command_payload)
            return self._finish(action_key, use_cooldown)

        if action_key in self._GESTURE_ACTIONS:
            self._send(self.gesture_adapter, action_key, command_payload)
            return self._finish(action_key, use_cooldown)

        if action_key in self._NAVIGATION_ACTIONS:
            self._send(self.navigation_adapter, action_key, command_payload)
            return self._finish(action_key, use_cooldown)

        raise ValueError(f"Action key is defined but not routed: {action_key!r}")

    @staticmethod
    def _send(adapter, command, payload):
        if adapter is not None:
            adapter.send(command, payload)

    def _finish(self, action_key, use_cooldown):
        if not use_cooldown:
            return None

        self.cooldown_manager.record_execution(action_key)
        return {
            "action_key": action_key,
            "executed": True,
            "reason": "executed",
        }


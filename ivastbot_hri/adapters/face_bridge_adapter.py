"""Local face bridge adapter for UI-facing face commands."""

from ivastbot_hri.core import keys


class FaceBridgeAdapter:
    """Convert face action keys into local UI command dictionaries."""

    _COMMAND_MAP = {
        keys.SHOW_NEUTRAL_FACE: {"emotion": "neutral"},
        keys.SHOW_HAPPY_FACE: {"emotion": "happy"},
        keys.SHOW_THINKING_FACE: {"emotion": "thinking"},
        keys.SHOW_GUIDING_FACE: {"emotion": "guiding"},
        keys.SHOW_ANGRY_FACE: {"emotion": "angry"},
        keys.SHOW_BORED_FACE: {"emotion": "bored"},
        keys.LOOK_LEFT: {"gaze": "left"},
        keys.LOOK_RIGHT: {"gaze": "right"},
        keys.LOOK_CENTER: {"gaze": "center"},
    }

    def __init__(self, sender=None):
        self.sender = sender
        self.sent_commands = []

    def send(self, command: str, payload: dict | None = None):
        ui_command = self.to_ui_command(command, payload)
        self.sent_commands.append(ui_command)
        if self.sender is not None:
            self.sender(ui_command)
        return ui_command

    def to_ui_command(self, command: str, payload: dict | None = None) -> dict:
        if command not in self._COMMAND_MAP:
            raise ValueError(f"Unknown face bridge command: {command!r}")

        command_payload = dict(payload or {})
        return {
            **command_payload,
            **self._COMMAND_MAP[command],
        }

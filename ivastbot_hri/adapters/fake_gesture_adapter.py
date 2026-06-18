"""In-memory gesture adapter for local tests and demos."""


class FakeGestureAdapter:
    """Record gesture commands without requiring robot hardware."""

    def __init__(self):
        self.commands = []

    def send(self, command, payload=None):
        self.commands.append((command, dict(payload or {})))


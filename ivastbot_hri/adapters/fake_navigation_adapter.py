"""In-memory navigation adapter for local tests and demos."""


class FakeNavigationAdapter:
    """Record navigation commands without requiring ROS 2 or Nav2."""

    def __init__(self):
        self.commands = []

    def send(self, command, payload=None):
        self.commands.append((command, dict(payload or {})))


"""In-memory face adapter for local tests and demos."""


class FakeFaceAdapter:
    """Record face commands without requiring UI, network, or robot hardware."""

    def __init__(self):
        self.commands = []

    def send(self, command, payload=None):
        self.commands.append((command, dict(payload or {})))


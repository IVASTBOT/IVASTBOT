"""Action execution result model."""

from dataclasses import dataclass, field


@dataclass
class ActionResult:
    """Structured result returned by action execution."""

    action_key: str
    executed: bool
    reason: str
    payload: dict = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self):
        self.payload = dict(self.payload or {})

    def to_dict(self) -> dict:
        return {
            "action_key": self.action_key,
            "executed": self.executed,
            "reason": self.reason,
            "payload": dict(self.payload),
            "error": self.error,
        }

"""Cooldown helpers for HRI action anti-spam logic."""

from collections.abc import Callable
import time


class CooldownManager:
    """Track per-action cooldowns with an injectable clock."""

    def __init__(
        self,
        default_cooldown_seconds: float = 1.0,
        per_action_cooldowns: dict[str, float] | None = None,
        time_provider: Callable[[], float] | None = None,
    ):
        self.default_cooldown_seconds = self._validate_cooldown(
            default_cooldown_seconds
        )
        self.per_action_cooldowns = {
            action_key: self._validate_cooldown(cooldown_seconds)
            for action_key, cooldown_seconds in (per_action_cooldowns or {}).items()
        }
        self._time_provider = time_provider or time.monotonic
        self._last_execution_times: dict[str, float] = {}

    def can_execute(self, action_key: str) -> bool:
        """Return whether an action is outside its cooldown window."""
        return self.get_remaining_cooldown(action_key) <= 0.0

    def record_execution(self, action_key: str) -> None:
        """Record that an action has just run."""
        self._last_execution_times[action_key] = float(self._time_provider())

    def try_execute(self, action_key: str) -> bool:
        """Record and return True only when the action is not cooling down."""
        if not self.can_execute(action_key):
            return False
        self.record_execution(action_key)
        return True

    def reset(self, action_key: str | None = None) -> None:
        """Clear cooldown state for one action, or all actions."""
        if action_key is None:
            self._last_execution_times.clear()
            return
        self._last_execution_times.pop(action_key, None)

    def get_remaining_cooldown(self, action_key: str) -> float:
        """Return remaining cooldown seconds for an action."""
        last_execution_time = self._last_execution_times.get(action_key)
        if last_execution_time is None:
            return 0.0

        elapsed = float(self._time_provider()) - last_execution_time
        remaining = self._get_cooldown_seconds(action_key) - elapsed
        return max(0.0, remaining)

    def _get_cooldown_seconds(self, action_key: str) -> float:
        return self.per_action_cooldowns.get(
            action_key,
            self.default_cooldown_seconds,
        )

    @staticmethod
    def _validate_cooldown(cooldown_seconds: float) -> float:
        cooldown = float(cooldown_seconds)
        if cooldown < 0.0:
            raise ValueError("Cooldown seconds must be non-negative")
        return cooldown

"""Dependency-free expression smoothing for HRI perception."""

from collections import Counter, deque

from ivastbot_hri.core import keys


class ExpressionSmoother:
    """Smooth noisy expression keys with a rolling majority window."""

    def __init__(
        self,
        window_size: int = 5,
        min_confidence_count: int = 3,
        default_expression: str = keys.EXPR_UNKNOWN,
    ):
        self.window_size = self._validate_positive_int(window_size, "window_size")
        self.min_confidence_count = self._validate_positive_int(
            min_confidence_count,
            "min_confidence_count",
        )
        if self.min_confidence_count > self.window_size:
            raise ValueError("min_confidence_count must be <= window_size")
        self.default_expression = self._normalize_expression(default_expression)
        self._window = deque(maxlen=self.window_size)
        self._stable_expression = self.default_expression

    def update(self, expression_key: str | None) -> str:
        """Add a raw expression and return the current stable expression."""
        normalized_expression = self._normalize_expression(expression_key)
        self._window.append(normalized_expression)

        candidate = self._majority_candidate()
        if candidate is not None:
            self._stable_expression = candidate

        return self._stable_expression

    def reset(self) -> None:
        """Clear smoothing history and return to the default expression."""
        self._window.clear()
        self._stable_expression = self.default_expression

    def current(self) -> str:
        """Return the current stable expression."""
        return self._stable_expression

    def _majority_candidate(self) -> str | None:
        counts = Counter(self._window)
        if not counts:
            return None

        highest_count = max(counts.values())
        if highest_count < self.min_confidence_count:
            return None

        candidates = {
            expression
            for expression, count in counts.items()
            if count == highest_count
        }

        if self._stable_expression in candidates:
            return self._stable_expression

        for expression in reversed(self._window):
            if expression in candidates:
                return expression

        return None

    @staticmethod
    def _normalize_expression(expression_key: str | None) -> str:
        if expression_key in keys.EXPRESSION_KEYS:
            return expression_key
        return keys.EXPR_UNKNOWN

    @staticmethod
    def _validate_positive_int(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value


__all__ = ("ExpressionSmoother",)

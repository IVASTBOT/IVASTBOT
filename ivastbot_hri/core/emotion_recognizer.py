"""Dependency-free local expression recognizer."""

from ivastbot_hri.core import keys


class ExpressionRecognizer:
    """Map normalized face features to IVASTBOT expression keys."""

    def __init__(
        self,
        min_face_confidence: float = 0.5,
        happy_smile_threshold: float = 0.65,
        surprise_mouth_threshold: float = 0.65,
        surprise_eyebrow_threshold: float = 0.55,
        confused_eyebrow_threshold: float = 0.65,
    ):
        self.min_face_confidence = self._validate_threshold(min_face_confidence)
        self.happy_smile_threshold = self._validate_threshold(happy_smile_threshold)
        self.surprise_mouth_threshold = self._validate_threshold(
            surprise_mouth_threshold
        )
        self.surprise_eyebrow_threshold = self._validate_threshold(
            surprise_eyebrow_threshold
        )
        self.confused_eyebrow_threshold = self._validate_threshold(
            confused_eyebrow_threshold
        )

    def recognize(self, features: dict | None) -> str:
        """Return an expression key for normalized face features."""
        if features is None:
            return keys.EXPR_UNKNOWN

        face_confidence = self._score(features, "face_confidence", default=None)
        if (
            face_confidence is None
            or face_confidence < self.min_face_confidence
        ):
            return keys.EXPR_UNKNOWN

        smile_score = self._score(features, "smile_score")
        mouth_open_score = self._score(features, "mouth_open_score")
        eyebrow_raise_score = self._score(features, "eyebrow_raise_score")

        if smile_score >= self.happy_smile_threshold:
            return keys.EXPR_HAPPY

        if (
            mouth_open_score >= self.surprise_mouth_threshold
            and eyebrow_raise_score >= self.surprise_eyebrow_threshold
        ):
            return keys.EXPR_SURPRISE

        if (
            eyebrow_raise_score >= self.confused_eyebrow_threshold
            and smile_score < self.happy_smile_threshold
        ):
            return keys.EXPR_CONFUSED

        return keys.EXPR_NEUTRAL

    @staticmethod
    def _score(features: dict, name: str, default=0.0):
        value = features.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        return float(value)

    @staticmethod
    def _validate_threshold(value: float) -> float:
        threshold = float(value)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Expression recognizer thresholds must be 0.0 to 1.0")
        return threshold


__all__ = ("ExpressionRecognizer",)

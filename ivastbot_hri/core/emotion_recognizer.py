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
        angry_brow_down_threshold: float = 0.65,
        angry_eye_squint_threshold: float = 0.65,
        angry_mouth_press_threshold: float = 0.55,
        angry_smile_max: float = 0.4,
        bored_low_activity_threshold: float = 0.75,
        bored_neutral_frame_count: int = 3,
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
        self.angry_brow_down_threshold = self._validate_threshold(
            angry_brow_down_threshold
        )
        self.angry_eye_squint_threshold = self._validate_threshold(
            angry_eye_squint_threshold
        )
        self.angry_mouth_press_threshold = self._validate_threshold(
            angry_mouth_press_threshold
        )
        self.angry_smile_max = self._validate_threshold(angry_smile_max)
        self.bored_low_activity_threshold = self._validate_threshold(
            bored_low_activity_threshold
        )
        self.bored_neutral_frame_count = self._validate_positive_int(
            bored_neutral_frame_count,
            "bored_neutral_frame_count",
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
        brow_down_score = self._score(features, "brow_down_score")
        eye_squint_score = self._score(features, "eye_squint_score")
        mouth_press_score = self._score(features, "mouth_press_score")
        low_activity_score = self._score(features, "low_activity_score")
        neutral_frame_count = self._count(features, "neutral_frame_count")

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

        angry_signal_count = sum(
            (
                brow_down_score >= self.angry_brow_down_threshold,
                eye_squint_score >= self.angry_eye_squint_threshold,
                mouth_press_score >= self.angry_mouth_press_threshold,
            )
        )
        if angry_signal_count >= 1 and smile_score <= self.angry_smile_max:
            return keys.EXPR_ANGRY

        is_low_arousal = (
            smile_score < self.happy_smile_threshold
            and mouth_open_score < self.surprise_mouth_threshold
            and eyebrow_raise_score < self.confused_eyebrow_threshold
            and brow_down_score < self.angry_brow_down_threshold
            and eye_squint_score < self.angry_eye_squint_threshold
            and mouth_press_score < self.angry_mouth_press_threshold
        )
        has_bored_signal = (
            low_activity_score >= self.bored_low_activity_threshold
            or neutral_frame_count >= self.bored_neutral_frame_count
        )
        if is_low_arousal and has_bored_signal:
            return keys.EXPR_BORED

        return keys.EXPR_NEUTRAL

    @staticmethod
    def _score(features: dict, name: str, default=0.0):
        value = features.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        return float(value)

    @staticmethod
    def _count(features: dict, name: str) -> int:
        value = features.get(name, 0)
        if isinstance(value, bool) or not isinstance(value, int):
            return 0
        return max(0, value)

    @staticmethod
    def _validate_threshold(value: float) -> float:
        threshold = float(value)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Expression recognizer thresholds must be 0.0 to 1.0")
        return threshold

    @staticmethod
    def _validate_positive_int(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value


__all__ = ("ExpressionRecognizer",)

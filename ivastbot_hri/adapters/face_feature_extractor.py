"""Local face feature extraction boundary for expression recognition."""


class FaceFeatureExtractor:
    """Normalize face feature inputs for ExpressionRecognizer."""

    FEATURE_KEYS = (
        "smile_score",
        "eye_open_score",
        "eyebrow_raise_score",
        "mouth_open_score",
        "face_confidence",
    )

    _SCORE_KEYS = FEATURE_KEYS[:-1]

    _LANDMARK_ALIASES = {
        "smile": "smile_score",
        "smile_score": "smile_score",
        "eye_open": "eye_open_score",
        "eye_open_score": "eye_open_score",
        "eyebrow_raise": "eyebrow_raise_score",
        "eyebrow_raise_score": "eyebrow_raise_score",
        "mouth_open": "mouth_open_score",
        "mouth_open_score": "mouth_open_score",
        "confidence": "face_confidence",
        "face_confidence": "face_confidence",
    }

    def extract_from_scores(self, scores: dict | None) -> dict:
        """Normalize score-like input into expression recognizer features."""
        if not isinstance(scores, dict) or not scores:
            return self._empty_features()

        features = self._empty_features()
        meaningful_score_present = False

        for key in self._SCORE_KEYS:
            if key in scores:
                features[key] = self._clamp_score(scores[key])
                meaningful_score_present = self._is_number(scores[key]) or (
                    meaningful_score_present
                )

        if "face_confidence" in scores:
            features["face_confidence"] = self._clamp_score(scores["face_confidence"])
        elif meaningful_score_present:
            features["face_confidence"] = 1.0

        return features

    def extract_from_landmarks(
        self,
        landmarks: dict | list | None,
        confidence: float = 1.0,
    ) -> dict:
        """Normalize simple landmark-like data into recognizer features."""
        if landmarks is None:
            return self._empty_features()
        if isinstance(landmarks, dict):
            scores = {}
            for source_key, target_key in self._LANDMARK_ALIASES.items():
                if source_key in landmarks:
                    scores[target_key] = landmarks[source_key]
            if scores and "face_confidence" not in scores:
                scores["face_confidence"] = confidence
            return self.extract_from_scores(scores)
        return self._empty_features()

    def extract_from_frame(self, frame) -> dict:
        """Placeholder for future camera backends."""
        raise RuntimeError(
            "Frame-based face feature extraction requires an optional camera "
            "backend that is not implemented in Phase 7B. Use "
            "extract_from_scores or extract_from_landmarks for local tests."
        )

    def _empty_features(self) -> dict:
        return {key: 0.0 for key in self.FEATURE_KEYS}

    @staticmethod
    def _clamp_score(value) -> float:
        if not FaceFeatureExtractor._is_number(value):
            return 0.0
        return min(1.0, max(0.0, float(value)))

    @staticmethod
    def _is_number(value) -> bool:
        return not isinstance(value, bool) and isinstance(value, (int, float))


__all__ = ("FaceFeatureExtractor",)

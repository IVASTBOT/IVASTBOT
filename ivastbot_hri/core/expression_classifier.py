"""Pure-Python expression classifier trained from calibration feature samples."""

import json
import math
import random
from pathlib import Path

from ivastbot_hri.core import keys

FEATURE_NAMES = (
    "smile_score",
    "eye_open_score",
    "eyebrow_raise_score",
    "mouth_open_score",
    "face_confidence",
    "brow_down_score",
    "eye_squint_score",
    "mouth_press_score",
    "low_activity_score",
)

_LABEL_TO_EXPRESSION = {
    "neutral": keys.EXPR_NEUTRAL,
    "happy": keys.EXPR_HAPPY,
    "surprise": keys.EXPR_SURPRISE,
    "confused": keys.EXPR_CONFUSED,
    "angry": keys.EXPR_ANGRY,
    "bored": keys.EXPR_BORED,
    "unknown": keys.EXPR_UNKNOWN,
    keys.EXPR_NEUTRAL: keys.EXPR_NEUTRAL,
    keys.EXPR_HAPPY: keys.EXPR_HAPPY,
    keys.EXPR_SURPRISE: keys.EXPR_SURPRISE,
    keys.EXPR_CONFUSED: keys.EXPR_CONFUSED,
    keys.EXPR_ANGRY: keys.EXPR_ANGRY,
    keys.EXPR_BORED: keys.EXPR_BORED,
    keys.EXPR_UNKNOWN: keys.EXPR_UNKNOWN,
}

EXPRESSION_KEYS = (
    keys.EXPR_NEUTRAL,
    keys.EXPR_HAPPY,
    keys.EXPR_SURPRISE,
    keys.EXPR_CONFUSED,
    keys.EXPR_ANGRY,
    keys.EXPR_BORED,
    keys.EXPR_UNKNOWN,
)


class NearestCentroidExpressionClassifier:
    """Nearest-centroid classifier over normalized expression feature vectors."""

    def __init__(
        self,
        feature_names: tuple[str, ...] = FEATURE_NAMES,
        max_distance_threshold: float | None = 1.25,
        min_face_confidence: float = 0.5,
    ):
        if not feature_names:
            raise ValueError("feature_names must not be empty")
        self.feature_names = tuple(feature_names)
        self.max_distance_threshold = _optional_non_negative_float(
            max_distance_threshold,
            "max_distance_threshold",
        )
        self.min_face_confidence = _clamp_score(min_face_confidence)
        self.centroids: dict[str, list[float]] = {}
        self.label_counts: dict[str, int] = {}

    def fit(
        self,
        samples: list[dict],
    ) -> "NearestCentroidExpressionClassifier":
        """Fit one centroid per expression label from calibration samples."""
        if not isinstance(samples, list):
            raise ValueError("samples must be a list")
        if not samples:
            raise ValueError("At least one training sample is required")

        grouped_vectors: dict[str, list[list[float]]] = {}
        for index, sample in enumerate(samples):
            label, features = _sample_label_and_features(sample, index)
            grouped_vectors.setdefault(label, []).append(self._vectorize(features))

        self.centroids = {
            label: _mean_vector(vectors)
            for label, vectors in sorted(grouped_vectors.items())
        }
        self.label_counts = {
            label: len(vectors) for label, vectors in sorted(grouped_vectors.items())
        }
        return self

    def predict(self, features: dict) -> str:
        """Return the nearest expression key, or EXPR_UNKNOWN when not confident."""
        return self.predict_with_scores(features)["prediction"]

    def predict_with_scores(self, features: dict) -> dict:
        """Return prediction details including distances to each centroid."""
        if not self.centroids:
            return _prediction_result(
                prediction=keys.EXPR_UNKNOWN,
                reason="unfitted",
            )

        if not isinstance(features, dict):
            return _prediction_result(
                prediction=keys.EXPR_UNKNOWN,
                reason="invalid_features",
            )

        face_confidence = _feature_value(features, "face_confidence")
        if face_confidence < self.min_face_confidence:
            return _prediction_result(
                prediction=keys.EXPR_UNKNOWN,
                reason="low_face_confidence",
            )

        vector = self._vectorize(features)
        distances = {
            label: _euclidean_distance(vector, centroid)
            for label, centroid in self.centroids.items()
        }
        nearest_label = min(distances, key=distances.get)
        nearest_distance = distances[nearest_label]

        if (
            self.max_distance_threshold is not None
            and nearest_distance > self.max_distance_threshold
        ):
            return _prediction_result(
                prediction=keys.EXPR_UNKNOWN,
                reason="distance_threshold",
                distances=distances,
                nearest_label=nearest_label,
                nearest_distance=nearest_distance,
            )

        return _prediction_result(
            prediction=nearest_label,
            reason="predicted",
            distances=distances,
            nearest_label=nearest_label,
            nearest_distance=nearest_distance,
        )

    def to_dict(self) -> dict:
        """Serialize classifier state into JSON-compatible data."""
        return {
            "model_type": "nearest_centroid_expression_classifier",
            "version": 1,
            "feature_names": list(self.feature_names),
            "max_distance_threshold": self.max_distance_threshold,
            "min_face_confidence": self.min_face_confidence,
            "centroids": self.centroids,
            "label_counts": self.label_counts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NearestCentroidExpressionClassifier":
        """Deserialize classifier state from JSON-compatible data."""
        if not isinstance(data, dict):
            raise ValueError("classifier data must be a dictionary")

        classifier = cls(
            feature_names=tuple(data.get("feature_names", FEATURE_NAMES)),
            max_distance_threshold=data.get("max_distance_threshold", 1.25),
            min_face_confidence=data.get("min_face_confidence", 0.5),
        )

        centroids = data.get("centroids", {})
        if not isinstance(centroids, dict):
            raise ValueError("classifier centroids must be a dictionary")
        classifier.centroids = {
            _normalize_label(label): [float(value) for value in vector]
            for label, vector in centroids.items()
        }

        label_counts = data.get("label_counts", {})
        if not isinstance(label_counts, dict):
            raise ValueError("classifier label_counts must be a dictionary")
        classifier.label_counts = {
            _normalize_label(label): int(count)
            for label, count in label_counts.items()
        }
        return classifier

    def _vectorize(self, features: dict) -> list[float]:
        return [_feature_value(features, feature_name) for feature_name in self.feature_names]


def split_samples(
    samples: list[dict],
    test_ratio: float = 0.2,
    seed: int = 0,
) -> tuple[list[dict], list[dict]]:
    """Split samples into deterministic train/test lists."""
    if not isinstance(samples, list):
        raise ValueError("samples must be a list")
    ratio = float(test_ratio)
    if not 0.0 <= ratio <= 1.0:
        raise ValueError("test_ratio must be between 0.0 and 1.0")

    shuffled = list(samples)
    random.Random(seed).shuffle(shuffled)
    test_count = int(round(len(shuffled) * ratio))
    if shuffled and ratio > 0.0:
        test_count = max(1, test_count)
    if len(shuffled) > 1 and ratio < 1.0:
        test_count = min(test_count, len(shuffled) - 1)

    test_samples = shuffled[:test_count]
    train_samples = shuffled[test_count:]
    return train_samples, test_samples


def evaluate_classifier(
    classifier: NearestCentroidExpressionClassifier,
    samples: list[dict],
) -> dict:
    """Evaluate classifier accuracy and confusion over labeled samples."""
    if not isinstance(samples, list):
        raise ValueError("samples must be a list")

    per_label = {
        label: {"total": 0, "correct": 0, "accuracy": None}
        for label in EXPRESSION_KEYS
    }
    confusion = {label: {} for label in EXPRESSION_KEYS}
    correct = 0

    for index, sample in enumerate(samples):
        expected_label, features = _sample_label_and_features(sample, index)
        prediction = classifier.predict(features)
        per_label[expected_label]["total"] += 1
        confusion[expected_label][prediction] = (
            confusion[expected_label].get(prediction, 0) + 1
        )
        if prediction == expected_label:
            correct += 1
            per_label[expected_label]["correct"] += 1

    for summary in per_label.values():
        if summary["total"]:
            summary["accuracy"] = summary["correct"] / summary["total"]

    total = len(samples)
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else None,
        "per_label": per_label,
        "confusion": confusion,
    }


def save_expression_classifier(
    classifier: NearestCentroidExpressionClassifier,
    output_path: str,
) -> None:
    """Save classifier JSON to the explicitly provided path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(classifier.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_expression_classifier(
    input_path: str,
) -> NearestCentroidExpressionClassifier:
    """Load classifier JSON from disk."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Expression classifier file does not exist: {input_path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Expression classifier file must contain valid JSON: {input_path}"
        ) from error
    return NearestCentroidExpressionClassifier.from_dict(data)


def _sample_label_and_features(sample: dict, index: int) -> tuple[str, dict]:
    if not isinstance(sample, dict):
        raise ValueError(f"sample at index {index} must be a dictionary")
    if "label" not in sample:
        raise ValueError(f"sample at index {index} is missing label")
    if "features" not in sample or not isinstance(sample["features"], dict):
        raise ValueError(f"sample at index {index} is missing features")
    return _normalize_label(sample["label"]), sample["features"]


def _normalize_label(label: str) -> str:
    if not isinstance(label, str):
        raise ValueError("label must be a string")
    normalized = label.strip()
    if normalized in _LABEL_TO_EXPRESSION:
        return _LABEL_TO_EXPRESSION[normalized]
    lowered = normalized.lower()
    if lowered in _LABEL_TO_EXPRESSION:
        return _LABEL_TO_EXPRESSION[lowered]
    raise ValueError(f"Unsupported expression label: {label!r}")


def _feature_value(features: dict, feature_name: str) -> float:
    value = features.get(feature_name, 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return _clamp_score(value)


def _clamp_score(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _optional_non_negative_float(value, name: str) -> float | None:
    if value is None:
        return None
    parsed_value = float(value)
    if parsed_value < 0.0:
        raise ValueError(f"{name} must be non-negative or None")
    return parsed_value


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    vector_count = len(vectors)
    return [
        sum(vector[index] for vector in vectors) / vector_count
        for index in range(len(vectors[0]))
    ]


def _euclidean_distance(left: list[float], right: list[float]) -> float:
    return math.sqrt(
        sum((left_value - right_value) ** 2 for left_value, right_value in zip(left, right))
    )


def _prediction_result(
    prediction: str,
    reason: str,
    distances: dict[str, float] | None = None,
    nearest_label: str | None = None,
    nearest_distance: float | None = None,
) -> dict:
    return {
        "prediction": prediction,
        "reason": reason,
        "distances": distances or {},
        "nearest_label": nearest_label,
        "nearest_distance": nearest_distance,
    }


__all__ = (
    "EXPRESSION_KEYS",
    "FEATURE_NAMES",
    "NearestCentroidExpressionClassifier",
    "evaluate_classifier",
    "load_expression_classifier",
    "save_expression_classifier",
    "split_samples",
)

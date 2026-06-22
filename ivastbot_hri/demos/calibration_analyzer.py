"""Analyze expression calibration samples and recommend recognizer thresholds."""

import argparse
import json
from pathlib import Path

from ivastbot_hri.core import keys
from ivastbot_hri.core.emotion_recognizer import ExpressionRecognizer
from ivastbot_hri.demos.expression_calibration_collector import (
    SUPPORTED_CALIBRATION_LABELS,
)

_LABEL_TO_EXPRESSION = {
    "neutral": keys.EXPR_NEUTRAL,
    "happy": keys.EXPR_HAPPY,
    "surprise": keys.EXPR_SURPRISE,
    "confused": keys.EXPR_CONFUSED,
    "angry": keys.EXPR_ANGRY,
    "bored": keys.EXPR_BORED,
    "unknown": keys.EXPR_UNKNOWN,
}

_DEFAULT_THRESHOLDS = {
    "min_face_confidence": 0.5,
    "happy_smile_threshold": 0.65,
    "surprise_mouth_threshold": 0.65,
    "surprise_eyebrow_threshold": 0.55,
    "confused_eyebrow_threshold": 0.65,
    "angry_brow_down_threshold": 0.65,
    "angry_eye_squint_threshold": 0.65,
    "angry_mouth_press_threshold": 0.55,
    "angry_smile_max": 0.4,
    "bored_low_activity_threshold": 0.75,
}

_RECOGNIZER_THRESHOLD_KEYS = frozenset(
    (
        "min_face_confidence",
        "happy_smile_threshold",
        "surprise_mouth_threshold",
        "surprise_eyebrow_threshold",
        "confused_eyebrow_threshold",
        "angry_brow_down_threshold",
        "angry_eye_squint_threshold",
        "angry_mouth_press_threshold",
        "angry_smile_max",
        "bored_low_activity_threshold",
        "bored_neutral_frame_count",
    )
)


def load_calibration_samples(input_path: str) -> list[dict]:
    """Load and validate calibration samples from a JSON file."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Calibration sample file does not exist: {input_path}")
    if not path.is_file():
        raise ValueError(f"Calibration sample path is not a file: {input_path}")

    try:
        samples = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Calibration sample file must contain valid JSON: {input_path}"
        ) from error

    if not isinstance(samples, list):
        raise ValueError("Calibration sample file must contain a JSON list.")

    for index, sample in enumerate(samples):
        is_valid, reason = validate_calibration_sample(sample)
        if not is_valid:
            raise ValueError(f"Invalid calibration sample at index {index}: {reason}")

    return samples


def validate_calibration_sample(sample: dict) -> tuple[bool, str | None]:
    """Validate the sample shape produced by expression_calibration_collector."""
    if not isinstance(sample, dict):
        return False, "sample must be a dictionary"

    label = sample.get("label")
    if not isinstance(label, str) or not label.strip():
        return False, "sample is missing label"
    if label.strip().lower() not in SUPPORTED_CALIBRATION_LABELS:
        return False, f"unsupported label: {label!r}"

    features = sample.get("features")
    if not isinstance(features, dict):
        return False, "sample is missing features"
    for feature_name, feature_value in features.items():
        if not isinstance(feature_name, str):
            return False, "feature names must be strings"
        if not _is_number(feature_value):
            return False, f"feature value must be numeric: {feature_name}"

    predicted_expression = sample.get("predicted_expression")
    if predicted_expression is not None and not isinstance(predicted_expression, str):
        return False, "predicted_expression must be a string or None"

    matched_expected = sample.get("matched_expected")
    if matched_expected is not None and not isinstance(matched_expected, bool):
        return False, "matched_expected must be a bool or None"

    image_path = sample.get("image_path")
    if image_path is not None and not isinstance(image_path, str):
        return False, "image_path must be a string or None"

    notes = sample.get("notes")
    if notes is not None and not isinstance(notes, str):
        return False, "notes must be a string or None"

    return True, None


def summarize_by_label(samples: list[dict]) -> dict:
    """Return count and accuracy information grouped by calibration label."""
    validated_samples = _validated_samples(samples)
    label_summaries = {
        label: {
            "count": 0,
            "matched_count": 0,
            "mismatched_count": 0,
            "evaluated_count": 0,
            "accuracy": None,
        }
        for label in SUPPORTED_CALIBRATION_LABELS
    }

    for sample in validated_samples:
        label = _normalize_label(sample["label"])
        summary = label_summaries[label]
        summary["count"] += 1

        match = _sample_match(sample)
        if match is True:
            summary["matched_count"] += 1
            summary["evaluated_count"] += 1
        elif match is False:
            summary["mismatched_count"] += 1
            summary["evaluated_count"] += 1

    for summary in label_summaries.values():
        if summary["evaluated_count"]:
            summary["accuracy"] = summary["matched_count"] / summary["evaluated_count"]

    return {
        "total_samples": len(validated_samples),
        "label_counts": {
            label: summary["count"] for label, summary in label_summaries.items()
        },
        "labels": label_summaries,
    }


def compute_feature_stats(samples: list[dict]) -> dict:
    """Compute min, max, mean, and count for each feature per label."""
    validated_samples = _validated_samples(samples)
    grouped_values: dict[str, dict[str, list[float]]] = {
        label: {} for label in SUPPORTED_CALIBRATION_LABELS
    }

    for sample in validated_samples:
        label = _normalize_label(sample["label"])
        for feature_name, feature_value in sample["features"].items():
            grouped_values[label].setdefault(feature_name, []).append(
                float(feature_value)
            )

    label_stats = {}
    for label, feature_values in grouped_values.items():
        label_stats[label] = {
            feature_name: _stats_for_values(values)
            for feature_name, values in sorted(feature_values.items())
        }

    return {
        "total_samples": len(validated_samples),
        "labels": label_stats,
    }


def compute_confusion_summary(samples: list[dict]) -> dict:
    """Summarize expected labels against predicted expression keys."""
    validated_samples = _validated_samples(samples)
    matrix = {label: {} for label in SUPPORTED_CALIBRATION_LABELS}
    matched_count = 0
    mismatched_count = 0
    evaluated_count = 0

    for sample in validated_samples:
        predicted_expression = sample.get("predicted_expression")
        if predicted_expression is None:
            continue

        label = _normalize_label(sample["label"])
        matrix[label][predicted_expression] = matrix[label].get(
            predicted_expression, 0
        ) + 1
        evaluated_count += 1

        if _sample_match(sample):
            matched_count += 1
        else:
            mismatched_count += 1

    return {
        "total_samples": len(validated_samples),
        "evaluated_samples": evaluated_count,
        "matched_count": matched_count,
        "mismatched_count": mismatched_count,
        "accuracy": (
            matched_count / evaluated_count if evaluated_count else None
        ),
        "matrix": matrix,
    }


def recommend_thresholds(samples: list[dict]) -> dict:
    """Return conservative threshold recommendations from sample distributions."""
    validated_samples = _validated_samples(samples)
    thresholds = dict(_DEFAULT_THRESHOLDS)

    thresholds["min_face_confidence"] = _recommend_min_face_confidence(
        validated_samples
    )
    thresholds["happy_smile_threshold"] = _recommend_activation_threshold(
        _feature_values(validated_samples, "happy", "smile_score"),
        _feature_values_except(validated_samples, "happy", "smile_score"),
        thresholds["happy_smile_threshold"],
    )
    thresholds["surprise_mouth_threshold"] = _recommend_activation_threshold(
        _feature_values(validated_samples, "surprise", "mouth_open_score"),
        _feature_values_except(validated_samples, "surprise", "mouth_open_score"),
        thresholds["surprise_mouth_threshold"],
    )
    thresholds["surprise_eyebrow_threshold"] = _recommend_activation_threshold(
        _feature_values(validated_samples, "surprise", "eyebrow_raise_score"),
        _feature_values_except(validated_samples, "surprise", "eyebrow_raise_score"),
        thresholds["surprise_eyebrow_threshold"],
    )
    thresholds["confused_eyebrow_threshold"] = _recommend_activation_threshold(
        _feature_values(validated_samples, "confused", "eyebrow_raise_score"),
        _feature_values_except(validated_samples, "confused", "eyebrow_raise_score"),
        thresholds["confused_eyebrow_threshold"],
    )
    thresholds["angry_brow_down_threshold"] = _recommend_activation_threshold(
        _feature_values(validated_samples, "angry", "brow_down_score"),
        _feature_values_except(validated_samples, "angry", "brow_down_score"),
        thresholds["angry_brow_down_threshold"],
    )
    thresholds["angry_eye_squint_threshold"] = _recommend_activation_threshold(
        _feature_values(validated_samples, "angry", "eye_squint_score"),
        _feature_values_except(validated_samples, "angry", "eye_squint_score"),
        thresholds["angry_eye_squint_threshold"],
    )
    thresholds["angry_mouth_press_threshold"] = _recommend_activation_threshold(
        _feature_values(validated_samples, "angry", "mouth_press_score"),
        _feature_values_except(validated_samples, "angry", "mouth_press_score"),
        thresholds["angry_mouth_press_threshold"],
    )
    thresholds["angry_smile_max"] = _recommend_upper_limit(
        _feature_values(validated_samples, "angry", "smile_score"),
        thresholds["angry_smile_max"],
    )
    thresholds["bored_low_activity_threshold"] = _recommend_activation_threshold(
        _feature_values(validated_samples, "bored", "low_activity_score"),
        _feature_values_except(validated_samples, "bored", "low_activity_score"),
        thresholds["bored_low_activity_threshold"],
    )

    return {
        "thresholds": thresholds,
        "smoothing": {
            "window_size": 5,
            "min_confidence_count": 3,
            "note": "Keep smoothing conservative until each label has enough samples.",
        },
        "summary": summarize_by_label(validated_samples),
        "confusion": compute_confusion_summary(validated_samples),
        "feature_stats": compute_feature_stats(validated_samples),
    }


def save_threshold_recommendations(
    recommendations: dict,
    output_path: str,
) -> None:
    """Save threshold recommendations as UTF-8 JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(recommendations, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def build_expression_recognizer_from_thresholds(
    thresholds: dict,
) -> ExpressionRecognizer:
    """Build ExpressionRecognizer using a flat or nested threshold dictionary."""
    if not isinstance(thresholds, dict):
        raise ValueError("thresholds must be a dictionary")

    threshold_values = thresholds.get("thresholds", thresholds)
    if not isinstance(threshold_values, dict):
        raise ValueError("thresholds['thresholds'] must be a dictionary")

    recognizer_kwargs = {
        key: value
        for key, value in threshold_values.items()
        if key in _RECOGNIZER_THRESHOLD_KEYS
    }
    return ExpressionRecognizer(**recognizer_kwargs)


def main() -> int:
    """CLI entry point for local threshold analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze IVASTBOT HRI expression calibration samples."
    )
    parser.add_argument("input_path", help="Path to calibration sample JSON.")
    parser.add_argument(
        "--output",
        help="Optional output path for threshold recommendation JSON.",
    )
    args = parser.parse_args()

    samples = load_calibration_samples(args.input_path)
    recommendations = recommend_thresholds(samples)
    if args.output:
        save_threshold_recommendations(recommendations, args.output)
    else:
        print(json.dumps(recommendations, indent=2, ensure_ascii=False))

    return 0


def _validated_samples(samples: list[dict]) -> list[dict]:
    if not isinstance(samples, list):
        raise ValueError("samples must be a list")
    for index, sample in enumerate(samples):
        is_valid, reason = validate_calibration_sample(sample)
        if not is_valid:
            raise ValueError(f"Invalid calibration sample at index {index}: {reason}")
    return samples


def _normalize_label(label: str) -> str:
    return label.strip().lower()


def _sample_match(sample: dict) -> bool | None:
    matched_expected = sample.get("matched_expected")
    if matched_expected is not None:
        return bool(matched_expected)

    predicted_expression = sample.get("predicted_expression")
    if predicted_expression is None:
        return None

    return predicted_expression == _LABEL_TO_EXPRESSION[_normalize_label(sample["label"])]


def _stats_for_values(values: list[float]) -> dict:
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def _feature_values(
    samples: list[dict],
    label: str,
    feature_name: str,
) -> list[float]:
    return sorted(
        float(sample["features"][feature_name])
        for sample in samples
        if _normalize_label(sample["label"]) == label
        and feature_name in sample["features"]
    )


def _feature_values_except(
    samples: list[dict],
    label: str,
    feature_name: str,
) -> list[float]:
    return sorted(
        float(sample["features"][feature_name])
        for sample in samples
        if _normalize_label(sample["label"]) != label
        and feature_name in sample["features"]
    )


def _recommend_min_face_confidence(samples: list[dict]) -> float:
    known_confidences = sorted(
        float(sample["features"]["face_confidence"])
        for sample in samples
        if _normalize_label(sample["label"]) != "unknown"
        and "face_confidence" in sample["features"]
    )
    if not known_confidences:
        return _DEFAULT_THRESHOLDS["min_face_confidence"]

    known_floor = _quantile(known_confidences, 0.25)
    candidate = max(0.1, known_floor * 0.8)
    unknown_confidences = _feature_values(samples, "unknown", "face_confidence")
    if unknown_confidences:
        candidate = max(candidate, max(unknown_confidences) + 0.05)
    candidate = min(candidate, known_floor)
    return _rounded_score(candidate)


def _recommend_activation_threshold(
    positive_values: list[float],
    negative_values: list[float],
    default: float,
) -> float:
    if not positive_values:
        return default

    positive_anchor = _quantile(positive_values, 0.25)
    candidate = positive_anchor * 0.9
    if negative_values:
        candidate = max(candidate, _quantile(negative_values, 0.75) + 0.05)
    return _rounded_score(candidate)


def _recommend_upper_limit(values: list[float], default: float) -> float:
    if not values:
        return default
    return _rounded_score(_quantile(values, 0.75) + 0.05)


def _quantile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * quantile)
    return sorted_values[index]


def _rounded_score(value: float) -> float:
    return round(min(1.0, max(0.0, float(value))), 3)


def _is_number(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


__all__ = (
    "build_expression_recognizer_from_thresholds",
    "compute_confusion_summary",
    "compute_feature_stats",
    "load_calibration_samples",
    "recommend_thresholds",
    "save_threshold_recommendations",
    "summarize_by_label",
    "validate_calibration_sample",
)


if __name__ == "__main__":
    raise SystemExit(main())

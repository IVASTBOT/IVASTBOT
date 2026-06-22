"""Utilities for collecting HRI expression calibration samples."""

import json
from collections import Counter
from pathlib import Path

from ivastbot_hri.adapters.face_feature_extractor import FaceFeatureExtractor
from ivastbot_hri.core import keys

SUPPORTED_CALIBRATION_LABELS = (
    "neutral",
    "happy",
    "surprise",
    "confused",
    "angry",
    "bored",
    "unknown",
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


def build_calibration_sample(
    label: str,
    features: dict,
    raw_expression: str | None = None,
    notes: str | None = None,
) -> dict:
    """Build one normalized calibration sample."""
    normalized_label = _normalize_label(label)
    normalized_features = FaceFeatureExtractor().extract_from_scores(features)
    return {
        "label": normalized_label,
        "expected_expression": _LABEL_TO_EXPRESSION[normalized_label],
        "features": normalized_features,
        "raw_expression": raw_expression,
        "notes": notes,
    }


def save_calibration_samples(samples: list[dict], output_path: str) -> None:
    """Save calibration samples as UTF-8 JSON at the explicitly provided path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(samples, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def summarize_calibration_samples(samples: list[dict]) -> dict:
    """Summarize calibration sample counts by label."""
    counts = Counter(sample.get("label", "unknown") for sample in samples)
    return {
        "total_samples": len(samples),
        "label_counts": {
            label: counts.get(label, 0) for label in SUPPORTED_CALIBRATION_LABELS
        },
    }


def _normalize_label(label: str) -> str:
    normalized_label = str(label).strip().lower()
    if normalized_label not in SUPPORTED_CALIBRATION_LABELS:
        raise ValueError(
            f"Unsupported calibration label: {label!r}. Expected one of "
            f"{SUPPORTED_CALIBRATION_LABELS}."
        )
    return normalized_label


__all__ = (
    "SUPPORTED_CALIBRATION_LABELS",
    "build_calibration_sample",
    "save_calibration_samples",
    "summarize_calibration_samples",
)

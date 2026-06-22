"""Utilities for collecting HRI expression calibration samples."""

import json
from collections import Counter
from pathlib import Path

from ivastbot_hri.adapters.face_feature_extractor import FaceFeatureExtractor
from ivastbot_hri.core import keys
from ivastbot_hri.core.emotion_recognizer import ExpressionRecognizer

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

SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")


def build_calibration_sample(
    label: str,
    image_path: str | dict | None = None,
    features: dict | None = None,
    predicted_expression: str | None = None,
    notes: str | None = None,
) -> dict:
    """Build one normalized calibration sample."""
    if isinstance(image_path, dict) and features is None:
        features = image_path
        image_path = None

    normalized_label = _normalize_label(label)
    expected_expression = _LABEL_TO_EXPRESSION[normalized_label]
    normalized_features = FaceFeatureExtractor().extract_from_scores(features)
    return {
        "label": normalized_label,
        "image_path": str(image_path) if image_path is not None else None,
        "features": normalized_features,
        "expected_expression": expected_expression,
        "predicted_expression": predicted_expression,
        "matched_expected": _matches_expected(expected_expression, predicted_expression),
        "notes": notes,
    }


def iter_labeled_image_paths(root_dir: str) -> list[dict]:
    """Return supported image paths grouped by expression label folder."""
    root_path = Path(root_dir)
    if not root_path.exists():
        raise FileNotFoundError(f"Calibration image root does not exist: {root_dir}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Calibration image root is not a directory: {root_dir}")

    entries = []
    for label_dir in sorted(path for path in root_path.iterdir() if path.is_dir()):
        label = _normalize_label(label_dir.name)
        for image_path in sorted(label_dir.iterdir()):
            if image_path.is_file() and image_path.suffix.lower() in (
                SUPPORTED_IMAGE_EXTENSIONS
            ):
                entries.append(
                    {
                        "label": label,
                        "image_path": str(image_path),
                    }
                )

    return entries


def collect_from_image_folder(
    root_dir: str,
    model_path: str | None = None,
    backend=None,
    cv2_module=None,
) -> list[dict]:
    """Collect calibration samples from a labeled image folder."""
    image_entries = iter_labeled_image_paths(root_dir)
    if not image_entries:
        return []

    active_backend = backend or _build_image_feature_backend(model_path)
    cv2 = cv2_module or _load_cv2_for_images()
    extractor = FaceFeatureExtractor()
    recognizer = ExpressionRecognizer()
    samples = []

    for entry in image_entries:
        image_path = entry["image_path"]
        frame = cv2.imread(image_path)
        if frame is None:
            raise RuntimeError(f"Unable to read calibration image: {image_path}")

        features = extractor.extract_from_scores(active_backend.extract_scores(frame))
        predicted_expression = recognizer.recognize(features)
        samples.append(
            build_calibration_sample(
                label=entry["label"],
                image_path=image_path,
                features=features,
                predicted_expression=predicted_expression,
            )
        )

    return samples


def save_calibration_samples(samples: list[dict], output_path: str) -> None:
    """Save calibration samples as UTF-8 JSON at the explicitly provided path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(samples, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def summarize_calibration_samples(samples: list[dict]) -> dict:
    """Summarize calibration sample counts and expected-expression matches."""
    counts = Counter(sample.get("label", "unknown") for sample in samples)
    matched_samples = sum(
        1 for sample in samples if sample.get("matched_expected") is True
    )
    mismatched_samples = sum(
        1 for sample in samples if sample.get("matched_expected") is False
    )
    not_evaluated_samples = len(samples) - matched_samples - mismatched_samples
    return {
        "total_samples": len(samples),
        "label_counts": {
            label: counts.get(label, 0) for label in SUPPORTED_CALIBRATION_LABELS
        },
        "matched_samples": matched_samples,
        "mismatched_samples": mismatched_samples,
        "not_evaluated_samples": not_evaluated_samples,
    }


def _normalize_label(label: str) -> str:
    normalized_label = str(label).strip().lower()
    if normalized_label not in SUPPORTED_CALIBRATION_LABELS:
        raise ValueError(
            f"Unsupported calibration label: {label!r}. Expected one of "
            f"{SUPPORTED_CALIBRATION_LABELS}."
        )
    return normalized_label


def _matches_expected(
    expected_expression: str,
    predicted_expression: str | None,
) -> bool | None:
    if predicted_expression is None:
        return None
    return predicted_expression == expected_expression


def _load_cv2_for_images():
    from ivastbot_hri.demos.visual_webcam_expression_demo import _load_cv2

    return _load_cv2()


def _build_image_feature_backend(model_path: str | None):
    from ivastbot_hri.demos.visual_webcam_expression_demo import (
        MEDIAPIPE_TASKS_MODEL_REQUIRED_MESSAGE,
        MediaPipeTasksFaceLandmarkerBackend,
        _resolve_face_landmarker_model_path,
    )

    resolved_model_path = _resolve_face_landmarker_model_path(model_path)
    if resolved_model_path is None:
        raise RuntimeError(MEDIAPIPE_TASKS_MODEL_REQUIRED_MESSAGE)
    return MediaPipeTasksFaceLandmarkerBackend(resolved_model_path)


__all__ = (
    "SUPPORTED_CALIBRATION_LABELS",
    "SUPPORTED_IMAGE_EXTENSIONS",
    "build_calibration_sample",
    "iter_labeled_image_paths",
    "collect_from_image_folder",
    "save_calibration_samples",
    "summarize_calibration_samples",
)

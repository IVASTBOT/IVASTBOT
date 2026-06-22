import importlib
import json
import sys

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.demos.calibration_analyzer import (
    build_expression_recognizer_from_thresholds,
    compute_confusion_summary,
    compute_feature_stats,
    load_calibration_samples,
    recommend_thresholds,
    save_threshold_recommendations,
    summarize_by_label,
    validate_calibration_sample,
)


def sample(
    label: str,
    features: dict,
    predicted_expression: str | None = None,
    matched_expected: bool | None = None,
) -> dict:
    return {
        "label": label,
        "features": features,
        "predicted_expression": predicted_expression,
        "matched_expected": matched_expected,
        "notes": None,
        "image_path": None,
    }


def representative_samples() -> list[dict]:
    return [
        sample(
            "happy",
            {"smile_score": 0.82, "face_confidence": 0.95},
            keys.EXPR_HAPPY,
            True,
        ),
        sample(
            "happy",
            {"smile_score": 0.9, "face_confidence": 0.96},
            keys.EXPR_NEUTRAL,
            False,
        ),
        sample(
            "neutral",
            {"smile_score": 0.15, "face_confidence": 0.93},
            keys.EXPR_NEUTRAL,
            True,
        ),
        sample(
            "surprise",
            {
                "mouth_open_score": 0.78,
                "eyebrow_raise_score": 0.68,
                "face_confidence": 0.94,
            },
            keys.EXPR_SURPRISE,
            True,
        ),
        sample(
            "confused",
            {
                "eyebrow_raise_score": 0.8,
                "smile_score": 0.05,
                "face_confidence": 0.92,
            },
            keys.EXPR_CONFUSED,
            True,
        ),
        sample(
            "angry",
            {
                "brow_down_score": 0.86,
                "eye_squint_score": 0.79,
                "mouth_press_score": 0.62,
                "smile_score": 0.1,
                "face_confidence": 0.91,
            },
            keys.EXPR_ANGRY,
            True,
        ),
        sample(
            "bored",
            {"low_activity_score": 0.88, "face_confidence": 0.9},
            keys.EXPR_BORED,
            True,
        ),
        sample(
            "unknown",
            {"face_confidence": 0.2},
            keys.EXPR_UNKNOWN,
            True,
        ),
    ]


def test_importing_calibration_analyzer_requires_no_optional_runtime():
    forbidden_roots = {
        "cv2",
        "mediapipe",
        "numpy",
        "openni",
        "requests",
        "rclpy",
        "serial",
        "websocket",
        "websockets",
    }
    before = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }

    sys.modules.pop("ivastbot_hri.demos.calibration_analyzer", None)
    module = importlib.import_module("ivastbot_hri.demos.calibration_analyzer")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.recommend_thresholds is not None
    assert after == before


def test_load_calibration_samples_reads_valid_json(tmp_path):
    input_path = tmp_path / "samples.json"
    samples = representative_samples()
    input_path.write_text(json.dumps(samples), encoding="utf-8")

    assert load_calibration_samples(str(input_path)) == samples


def test_load_calibration_samples_missing_file_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Calibration sample file"):
        load_calibration_samples(str(tmp_path / "missing.json"))


def test_load_calibration_samples_invalid_json_gives_clear_error(tmp_path):
    input_path = tmp_path / "samples.json"
    input_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="valid JSON"):
        load_calibration_samples(str(input_path))


def test_validate_calibration_sample_accepts_valid_sample():
    is_valid, reason = validate_calibration_sample(representative_samples()[0])

    assert is_valid is True
    assert reason is None


def test_validate_calibration_sample_rejects_missing_label_or_features():
    missing_label = {"features": {"smile_score": 0.9}}
    missing_features = {"label": "happy"}

    assert validate_calibration_sample(missing_label) == (
        False,
        "sample is missing label",
    )
    assert validate_calibration_sample(missing_features) == (
        False,
        "sample is missing features",
    )


def test_validate_calibration_sample_rejects_non_numeric_features():
    is_valid, reason = validate_calibration_sample(
        sample("happy", {"smile_score": "high"})
    )

    assert is_valid is False
    assert "feature value must be numeric" in reason


def test_summarize_by_label_counts_samples_and_accuracy():
    summary = summarize_by_label(representative_samples())

    assert summary["total_samples"] == 8
    assert summary["label_counts"]["happy"] == 2
    assert summary["label_counts"]["angry"] == 1
    assert summary["labels"]["happy"]["matched_count"] == 1
    assert summary["labels"]["happy"]["mismatched_count"] == 1
    assert summary["labels"]["happy"]["accuracy"] == 0.5


def test_compute_feature_stats_computes_mean_min_max_per_label():
    stats = compute_feature_stats(representative_samples())
    happy_smile = stats["labels"]["happy"]["smile_score"]

    assert happy_smile["count"] == 2
    assert happy_smile["min"] == 0.82
    assert happy_smile["max"] == 0.9
    assert happy_smile["mean"] == pytest.approx(0.86)


def test_compute_confusion_summary_counts_matched_and_mismatched_predictions():
    confusion = compute_confusion_summary(representative_samples())

    assert confusion["evaluated_samples"] == 8
    assert confusion["matched_count"] == 7
    assert confusion["mismatched_count"] == 1
    assert confusion["accuracy"] == pytest.approx(7 / 8)
    assert confusion["matrix"]["happy"][keys.EXPR_HAPPY] == 1
    assert confusion["matrix"]["happy"][keys.EXPR_NEUTRAL] == 1


def test_recommend_thresholds_returns_expected_sections_and_keys():
    recommendations = recommend_thresholds(representative_samples())
    thresholds = recommendations["thresholds"]

    assert isinstance(recommendations, dict)
    assert "summary" in recommendations
    assert "confusion" in recommendations
    assert "feature_stats" in recommendations
    assert "smoothing" in recommendations
    assert "min_face_confidence" in thresholds
    assert "happy_smile_threshold" in thresholds
    assert "surprise_mouth_threshold" in thresholds
    assert "surprise_eyebrow_threshold" in thresholds
    assert "confused_eyebrow_threshold" in thresholds
    assert "angry_brow_down_threshold" in thresholds
    assert "angry_eye_squint_threshold" in thresholds
    assert "bored_low_activity_threshold" in thresholds


def test_happy_samples_influence_happy_smile_threshold():
    low_happy_samples = [
        sample("happy", {"smile_score": 0.55, "face_confidence": 0.9}),
        sample("happy", {"smile_score": 0.6, "face_confidence": 0.9}),
        sample("neutral", {"smile_score": 0.1, "face_confidence": 0.9}),
    ]
    high_happy_samples = [
        sample("happy", {"smile_score": 0.85, "face_confidence": 0.9}),
        sample("happy", {"smile_score": 0.9, "face_confidence": 0.9}),
        sample("neutral", {"smile_score": 0.1, "face_confidence": 0.9}),
    ]

    low_threshold = recommend_thresholds(low_happy_samples)["thresholds"][
        "happy_smile_threshold"
    ]
    high_threshold = recommend_thresholds(high_happy_samples)["thresholds"][
        "happy_smile_threshold"
    ]

    assert high_threshold > low_threshold


def test_surprise_samples_influence_mouth_and_eyebrow_thresholds():
    recommendations = recommend_thresholds(representative_samples())
    thresholds = recommendations["thresholds"]

    assert thresholds["surprise_mouth_threshold"] == pytest.approx(0.702)
    assert thresholds["surprise_eyebrow_threshold"] > 0.55
    assert thresholds["surprise_eyebrow_threshold"] <= 1.0


def test_angry_samples_influence_brow_down_and_eye_squint_thresholds():
    thresholds = recommend_thresholds(representative_samples())["thresholds"]

    assert thresholds["angry_brow_down_threshold"] == pytest.approx(0.774)
    assert thresholds["angry_eye_squint_threshold"] == pytest.approx(0.711)


def test_unknown_low_confidence_influences_min_face_confidence_conservatively():
    thresholds = recommend_thresholds(representative_samples())["thresholds"]

    assert thresholds["min_face_confidence"] > 0.2
    assert thresholds["min_face_confidence"] <= 0.9


def test_bored_samples_influence_low_activity_threshold():
    thresholds = recommend_thresholds(representative_samples())["thresholds"]

    assert thresholds["bored_low_activity_threshold"] == pytest.approx(0.792)


def test_recommendations_are_deterministic():
    first = recommend_thresholds(representative_samples())
    second = recommend_thresholds(representative_samples())

    assert first == second


def test_save_threshold_recommendations_writes_valid_json(tmp_path):
    recommendations = recommend_thresholds(representative_samples())
    output_path = tmp_path / "nested" / "thresholds.json"

    save_threshold_recommendations(recommendations, str(output_path))

    assert json.loads(output_path.read_text(encoding="utf-8")) == recommendations


def test_build_expression_recognizer_from_thresholds_uses_tuned_values():
    recognizer = build_expression_recognizer_from_thresholds(
        {"thresholds": {"happy_smile_threshold": 0.8}}
    )

    assert (
        recognizer.recognize({"smile_score": 0.75, "face_confidence": 0.9})
        != keys.EXPR_HAPPY
    )
    assert (
        recognizer.recognize({"smile_score": 0.85, "face_confidence": 0.9})
        == keys.EXPR_HAPPY
    )

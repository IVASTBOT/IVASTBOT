import importlib
import json
import sys

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.demos.expression_calibration_collector import (
    SUPPORTED_CALIBRATION_LABELS,
    build_calibration_sample,
    save_calibration_samples,
    summarize_calibration_samples,
)


def test_importing_calibration_collector_requires_no_optional_runtime():
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

    sys.modules.pop("ivastbot_hri.demos.expression_calibration_collector", None)
    module = importlib.import_module(
        "ivastbot_hri.demos.expression_calibration_collector"
    )

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.build_calibration_sample is not None
    assert after == before


def test_supported_labels_include_all_expression_labels():
    assert SUPPORTED_CALIBRATION_LABELS == (
        "neutral",
        "happy",
        "surprise",
        "confused",
        "angry",
        "bored",
        "unknown",
    )


def test_build_calibration_sample_normalizes_features():
    sample = build_calibration_sample(
        label="angry",
        features={
            "brow_down_score": 0.8,
            "eye_squint_score": 0.7,
            "mouth_press_score": 0.6,
            "face_confidence": 0.95,
        },
        raw_expression=keys.EXPR_ANGRY,
        notes="brow down and squint",
    )

    assert sample["label"] == "angry"
    assert sample["expected_expression"] == keys.EXPR_ANGRY
    assert sample["features"]["brow_down_score"] == 0.8
    assert sample["features"]["eye_squint_score"] == 0.7
    assert sample["features"]["mouth_press_score"] == 0.6
    assert sample["raw_expression"] == keys.EXPR_ANGRY
    assert sample["notes"] == "brow down and squint"


def test_build_calibration_sample_rejects_unknown_label():
    with pytest.raises(ValueError, match="Unsupported calibration label"):
        build_calibration_sample("sleepy", {})


def test_save_calibration_samples_writes_valid_json(tmp_path):
    samples = [
        build_calibration_sample("happy", {"smile_score": 0.9}),
        build_calibration_sample("bored", {"low_activity_score": 0.9}),
    ]
    output_path = tmp_path / "nested" / "calibration.json"

    save_calibration_samples(samples, str(output_path))

    assert json.loads(output_path.read_text(encoding="utf-8")) == samples


def test_summarize_calibration_samples_counts_labels():
    samples = [
        build_calibration_sample("happy", {"smile_score": 0.9}),
        build_calibration_sample("happy", {"smile_score": 0.8}),
        build_calibration_sample("angry", {"brow_down_score": 0.9}),
    ]

    summary = summarize_calibration_samples(samples)

    assert summary["total_samples"] == 3
    assert summary["label_counts"]["happy"] == 2
    assert summary["label_counts"]["angry"] == 1
    assert summary["label_counts"]["bored"] == 0

import importlib
import json
import sys

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.demos.expression_calibration_collector import (
    SUPPORTED_CALIBRATION_LABELS,
    build_calibration_sample,
    collect_from_image_folder,
    iter_labeled_image_paths,
    save_calibration_samples,
    summarize_calibration_samples,
)


class FakeCv2:
    def __init__(self):
        self.read_paths = []

    def imread(self, image_path):
        self.read_paths.append(image_path)
        return {"image_path": image_path}


class FakeBackend:
    def extract_scores(self, frame):
        image_path = frame["image_path"].replace("\\", "/")
        if "/happy/" in image_path:
            return {"smile_score": 0.9, "face_confidence": 0.95}
        if "/angry/" in image_path:
            return {
                "brow_down_score": 0.9,
                "eye_squint_score": 0.8,
                "face_confidence": 0.95,
            }
        return {"face_confidence": 0.1}


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
        image_path="calibration_images/angry/a.png",
        features={
            "brow_down_score": 0.8,
            "eye_squint_score": 0.7,
            "mouth_press_score": 0.6,
            "face_confidence": 0.95,
        },
        predicted_expression=keys.EXPR_ANGRY,
        notes="brow down and squint",
    )

    assert sample["label"] == "angry"
    assert sample["image_path"] == "calibration_images/angry/a.png"
    assert sample["expected_expression"] == keys.EXPR_ANGRY
    assert sample["features"]["brow_down_score"] == 0.8
    assert sample["features"]["eye_squint_score"] == 0.7
    assert sample["features"]["mouth_press_score"] == 0.6
    assert sample["predicted_expression"] == keys.EXPR_ANGRY
    assert sample["matched_expected"] is True
    assert sample["notes"] == "brow down and squint"


def test_build_calibration_sample_supports_manual_sample_without_image_path():
    sample = build_calibration_sample(
        label="happy",
        features={"smile_score": 0.9},
        predicted_expression=keys.EXPR_NEUTRAL,
    )

    assert sample["image_path"] is None
    assert sample["predicted_expression"] == keys.EXPR_NEUTRAL
    assert sample["matched_expected"] is False


def test_build_calibration_sample_rejects_unknown_label():
    with pytest.raises(ValueError, match="Unsupported calibration label"):
        build_calibration_sample("sleepy", {})


def test_iter_labeled_image_paths_detects_supported_images(tmp_path):
    root = tmp_path / "calibration_images"
    (root / "happy").mkdir(parents=True)
    (root / "angry").mkdir()
    (root / "happy" / "one.png").write_text("", encoding="utf-8")
    (root / "happy" / "two.jpg").write_text("", encoding="utf-8")
    (root / "angry" / "three.jpeg").write_text("", encoding="utf-8")
    (root / "angry" / "ignore.txt").write_text("", encoding="utf-8")

    entries = iter_labeled_image_paths(str(root))

    assert entries == [
        {"label": "angry", "image_path": str(root / "angry" / "three.jpeg")},
        {"label": "happy", "image_path": str(root / "happy" / "one.png")},
        {"label": "happy", "image_path": str(root / "happy" / "two.jpg")},
    ]


def test_iter_labeled_image_paths_rejects_unsupported_labels(tmp_path):
    root = tmp_path / "calibration_images"
    (root / "sleepy").mkdir(parents=True)
    (root / "sleepy" / "one.png").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported calibration label"):
        iter_labeled_image_paths(str(root))


def test_iter_labeled_image_paths_missing_root_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Calibration image root"):
        iter_labeled_image_paths(str(tmp_path / "missing"))


def test_collect_from_image_folder_uses_fake_backend_and_cv2(tmp_path):
    root = tmp_path / "calibration_images"
    (root / "happy").mkdir(parents=True)
    (root / "angry").mkdir()
    (root / "happy" / "smile.png").write_text("", encoding="utf-8")
    (root / "angry" / "brow.jpg").write_text("", encoding="utf-8")
    fake_cv2 = FakeCv2()

    samples = collect_from_image_folder(
        str(root),
        backend=FakeBackend(),
        cv2_module=fake_cv2,
    )

    assert [sample["label"] for sample in samples] == ["angry", "happy"]
    assert [sample["predicted_expression"] for sample in samples] == [
        keys.EXPR_ANGRY,
        keys.EXPR_HAPPY,
    ]
    assert all(sample["matched_expected"] is True for sample in samples)
    assert fake_cv2.read_paths == [sample["image_path"] for sample in samples]


def test_collect_from_image_folder_requires_model_without_fake_backend(tmp_path):
    root = tmp_path / "calibration_images"
    (root / "happy").mkdir(parents=True)
    (root / "happy" / "smile.png").write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="FaceLandmarker requires a .task model"):
        collect_from_image_folder(str(root), cv2_module=FakeCv2())


def test_save_calibration_samples_writes_valid_json(tmp_path):
    samples = [
        build_calibration_sample("happy", features={"smile_score": 0.9}),
        build_calibration_sample("bored", features={"low_activity_score": 0.9}),
    ]
    output_path = tmp_path / "nested" / "calibration.json"

    save_calibration_samples(samples, str(output_path))

    assert json.loads(output_path.read_text(encoding="utf-8")) == samples


def test_summarize_calibration_samples_counts_labels():
    samples = [
        build_calibration_sample(
            "happy",
            features={"smile_score": 0.9},
            predicted_expression=keys.EXPR_HAPPY,
        ),
        build_calibration_sample(
            "happy",
            features={"smile_score": 0.8},
            predicted_expression=keys.EXPR_NEUTRAL,
        ),
        build_calibration_sample("angry", features={"brow_down_score": 0.9}),
    ]

    summary = summarize_calibration_samples(samples)

    assert summary["total_samples"] == 3
    assert summary["label_counts"]["happy"] == 2
    assert summary["label_counts"]["angry"] == 1
    assert summary["label_counts"]["bored"] == 0
    assert summary["matched_samples"] == 1
    assert summary["mismatched_samples"] == 1
    assert summary["not_evaluated_samples"] == 1

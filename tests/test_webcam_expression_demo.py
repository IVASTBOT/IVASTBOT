import importlib
import sys

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.demos import webcam_expression_demo


def test_importing_webcam_expression_demo_requires_no_optional_runtime():
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

    sys.modules.pop("ivastbot_hri.demos.webcam_expression_demo", None)
    module = importlib.import_module("ivastbot_hri.demos.webcam_expression_demo")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.run_webcam_demo is not None
    assert after == before


def test_build_webcam_expression_pipeline_returns_usable_components():
    pipeline = webcam_expression_demo.build_webcam_expression_pipeline()

    assert pipeline["feature_extractor"].extract_from_scores({"smile_score": 0.9})
    assert pipeline["recognizer"].recognize(
        {"smile_score": 0.9, "face_confidence": 1.0}
    ) == keys.EXPR_HAPPY
    assert pipeline["smoother"].current() == keys.EXPR_UNKNOWN


def test_process_feature_scores_returns_expected_debug_keys():
    result = webcam_expression_demo.process_feature_scores(
        {
            "smile_score": 0.9,
            "mouth_open_score": 0.2,
            "eyebrow_raise_score": 0.1,
            "eye_open_score": 0.8,
            "face_confidence": 0.95,
        }
    )

    assert set(result) == {
        "extracted_features",
        "raw_expression",
        "smoothed_expression",
    }
    assert result["extracted_features"]["smile_score"] == 0.9
    assert result["raw_expression"] == keys.EXPR_HAPPY
    assert result["smoothed_expression"] == keys.EXPR_HAPPY


def test_high_smile_scores_produce_happy_raw_expression():
    result = webcam_expression_demo.process_feature_scores(
        {"smile_score": 0.95, "face_confidence": 0.95}
    )

    assert result["raw_expression"] == keys.EXPR_HAPPY


def test_low_confidence_produces_unknown_raw_expression():
    result = webcam_expression_demo.process_feature_scores(
        {"smile_score": 0.95, "face_confidence": 0.1}
    )

    assert result["raw_expression"] == keys.EXPR_UNKNOWN


def test_process_feature_scores_can_reuse_pipeline_for_smoothing():
    pipeline = webcam_expression_demo.build_webcam_expression_pipeline()

    first_result = webcam_expression_demo.process_feature_scores(
        {"smile_score": 0.95, "face_confidence": 0.95},
        pipeline=pipeline,
    )
    second_result = webcam_expression_demo.process_feature_scores(
        {"mouth_open_score": 0.8, "eyebrow_raise_score": 0.8, "face_confidence": 0.95},
        pipeline=pipeline,
    )

    assert first_result["raw_expression"] == keys.EXPR_HAPPY
    assert second_result["raw_expression"] == keys.EXPR_SURPRISE
    assert second_result["smoothed_expression"] == keys.EXPR_HAPPY


def test_run_webcam_demo_fails_gracefully_if_cv2_is_unavailable(monkeypatch):
    real_import_module = importlib.import_module

    def fake_import_module(name, package=None):
        if name == "cv2":
            raise ImportError("OpenCV is not installed")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(
        RuntimeError,
        match=webcam_expression_demo.OPENCV_UNAVAILABLE_MESSAGE,
    ):
        webcam_expression_demo.run_webcam_demo(max_frames=1)


def test_run_webcam_demo_does_not_open_webcam_until_called(monkeypatch):
    def fail_if_cv2_is_loaded(name, package=None):
        if name == "cv2":
            raise AssertionError("cv2 should not be imported for pipeline setup")
        return importlib.import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fail_if_cv2_is_loaded)

    pipeline = webcam_expression_demo.build_webcam_expression_pipeline()
    result = webcam_expression_demo.process_feature_scores(
        {"smile_score": 0.9, "face_confidence": 0.95},
        pipeline=pipeline,
    )

    assert result["raw_expression"] == keys.EXPR_HAPPY

import importlib
import sys

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.demos import visual_webcam_expression_demo as visual_demo


class FakeCv2:
    FONT_HERSHEY_SIMPLEX = 1

    def __init__(self):
        self.text_calls = []

    def putText(self, frame, text, position, font, scale, color, thickness):
        self.text_calls.append(
            {
                "frame": frame,
                "text": text,
                "position": position,
                "font": font,
                "scale": scale,
                "color": color,
                "thickness": thickness,
            }
        )
        return frame


class FakeBackend:
    def __init__(self, scores):
        self.scores = scores
        self.frames = []

    def extract_scores(self, frame):
        self.frames.append(frame)
        return self.scores


def test_importing_visual_demo_requires_no_optional_runtime():
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

    sys.modules.pop("ivastbot_hri.demos.visual_webcam_expression_demo", None)
    module = importlib.import_module(
        "ivastbot_hri.demos.visual_webcam_expression_demo"
    )

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.run_visual_webcam_demo is not None
    assert after == before


def test_build_visual_expression_pipeline_returns_usable_components():
    pipeline = visual_demo.build_visual_expression_pipeline()

    assert pipeline["feature_extractor"].extract_from_scores({"smile_score": 0.9})
    assert pipeline["recognizer"].recognize(
        {"smile_score": 0.9, "face_confidence": 1.0}
    ) == keys.EXPR_HAPPY
    assert pipeline["smoother"].current() == keys.EXPR_UNKNOWN


def test_overlay_debug_info_writes_expected_lines_with_fake_cv2():
    fake_cv2 = FakeCv2()
    frame = {"fake": "frame"}
    debug_info = {
        "raw_expression": keys.EXPR_HAPPY,
        "smoothed_expression": keys.EXPR_HAPPY,
        "extracted_features": {
            "smile_score": 0.9,
            "mouth_open_score": 0.2,
            "eyebrow_raise_score": 0.1,
            "eye_open_score": 0.8,
            "face_confidence": 0.95,
        },
    }

    returned_frame = visual_demo.overlay_debug_info(
        frame,
        debug_info,
        cv2_module=fake_cv2,
    )

    assert returned_frame is frame
    texts = [call["text"] for call in fake_cv2.text_calls]
    assert "raw_expression: EXPR_HAPPY" in texts
    assert "smoothed_expression: EXPR_HAPPY" in texts
    assert "smile_score: 0.90" in texts
    assert "mouth_open_score: 0.20" in texts
    assert "eyebrow_raise_score: 0.10" in texts
    assert "eye_open_score: 0.80" in texts
    assert "face_confidence: 0.95" in texts
    assert "press q to quit" in texts


def test_process_frame_with_fake_backend_returns_debug_info():
    pipeline = visual_demo.build_visual_expression_pipeline()
    backend = FakeBackend({"smile_score": 0.95, "face_confidence": 0.95})

    first_result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "frame"},
        extractor=pipeline["feature_extractor"],
        recognizer=pipeline["recognizer"],
        smoother=pipeline["smoother"],
        backend=backend,
    )
    second_result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "second_frame"},
        extractor=pipeline["feature_extractor"],
        recognizer=pipeline["recognizer"],
        smoother=pipeline["smoother"],
        backend=backend,
    )

    assert first_result["extracted_features"]["smile_score"] == 0.95
    assert first_result["raw_expression"] == keys.EXPR_HAPPY
    assert first_result["smoothed_expression"] == keys.EXPR_UNKNOWN
    assert second_result["smoothed_expression"] == keys.EXPR_HAPPY
    assert backend.frames == [{"fake": "frame"}, {"fake": "second_frame"}]


def test_process_frame_with_missing_mediapipe_backend_raises_clear_error(
    monkeypatch,
):
    pipeline = visual_demo.build_visual_expression_pipeline()
    real_import_module = importlib.import_module

    def fake_import_module(name, package=None):
        if name == "mediapipe":
            raise ImportError("MediaPipe is not installed")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match=visual_demo.MEDIAPIPE_UNAVAILABLE_MESSAGE):
        visual_demo.process_frame_with_optional_backend(
            frame=object(),
            extractor=pipeline["feature_extractor"],
            recognizer=pipeline["recognizer"],
            smoother=pipeline["smoother"],
        )


def test_run_visual_webcam_demo_fails_gracefully_if_cv2_is_unavailable(
    monkeypatch,
):
    real_import_module = importlib.import_module

    def fake_import_module(name, package=None):
        if name == "cv2":
            raise ImportError("OpenCV is not installed")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match=visual_demo.OPENCV_UNAVAILABLE_MESSAGE):
        visual_demo.run_visual_webcam_demo(max_frames=1)


def test_run_visual_webcam_demo_does_not_run_on_import(monkeypatch):
    def fail_if_cv2_or_mediapipe_loads(name, package=None):
        if name in {"cv2", "mediapipe"}:
            raise AssertionError(f"{name} should not load during import")
        return importlib.import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fail_if_cv2_or_mediapipe_loads)

    pipeline = visual_demo.build_visual_expression_pipeline()

    assert pipeline["smoother"].current() == keys.EXPR_UNKNOWN

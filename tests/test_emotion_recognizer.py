import importlib
import sys

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.core.emotion_recognizer import ExpressionRecognizer


def test_none_input_returns_unknown():
    recognizer = ExpressionRecognizer()

    assert recognizer.recognize(None) == keys.EXPR_UNKNOWN


def test_missing_or_low_confidence_returns_unknown():
    recognizer = ExpressionRecognizer()

    assert recognizer.recognize({"smile_score": 1.0}) == keys.EXPR_UNKNOWN
    assert recognizer.recognize(
        {"face_confidence": 0.4, "smile_score": 1.0}
    ) == keys.EXPR_UNKNOWN


def test_high_smile_score_returns_happy():
    recognizer = ExpressionRecognizer()

    expression = recognizer.recognize(
        {
            "face_confidence": 0.9,
            "smile_score": 0.8,
            "mouth_open_score": 0.1,
            "eyebrow_raise_score": 0.1,
        }
    )

    assert expression == keys.EXPR_HAPPY


def test_high_mouth_open_and_eyebrow_raise_returns_surprise():
    recognizer = ExpressionRecognizer()

    expression = recognizer.recognize(
        {
            "face_confidence": 0.9,
            "smile_score": 0.1,
            "mouth_open_score": 0.8,
            "eyebrow_raise_score": 0.7,
        }
    )

    assert expression == keys.EXPR_SURPRISE


def test_high_eyebrow_raise_with_low_smile_returns_confused():
    recognizer = ExpressionRecognizer()

    expression = recognizer.recognize(
        {
            "face_confidence": 0.9,
            "smile_score": 0.1,
            "mouth_open_score": 0.2,
            "eyebrow_raise_score": 0.8,
        }
    )

    assert expression == keys.EXPR_CONFUSED


def test_normal_features_return_neutral():
    recognizer = ExpressionRecognizer()

    expression = recognizer.recognize(
        {
            "face_confidence": 0.9,
            "smile_score": 0.2,
            "eye_open_score": 0.7,
            "mouth_open_score": 0.2,
            "eyebrow_raise_score": 0.2,
        }
    )

    assert expression == keys.EXPR_NEUTRAL


def test_thresholds_can_be_customized():
    recognizer = ExpressionRecognizer(
        happy_smile_threshold=0.35,
        min_face_confidence=0.25,
    )

    expression = recognizer.recognize(
        {
            "face_confidence": 0.3,
            "smile_score": 0.4,
            "mouth_open_score": 0.1,
            "eyebrow_raise_score": 0.1,
        }
    )

    assert expression == keys.EXPR_HAPPY


def test_invalid_threshold_raises_value_error():
    with pytest.raises(ValueError, match="thresholds"):
        ExpressionRecognizer(happy_smile_threshold=1.5)


def test_recognizer_imports_existing_expression_keys():
    module = importlib.import_module("ivastbot_hri.core.emotion_recognizer")

    assert module.keys.EXPR_HAPPY == keys.EXPR_HAPPY
    assert ExpressionRecognizer().recognize(
        {"face_confidence": 0.9, "smile_score": 0.9}
    ) in keys.EXPRESSION_KEYS


def test_emotion_recognizer_import_has_no_ros_camera_or_hardware_dependency():
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

    sys.modules.pop("ivastbot_hri.core.emotion_recognizer", None)
    module = importlib.import_module("ivastbot_hri.core.emotion_recognizer")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.ExpressionRecognizer is not None
    assert after == before

import importlib
import sys

import pytest

from ivastbot_hri.adapters.face_feature_extractor import FaceFeatureExtractor
from ivastbot_hri.core import keys
from ivastbot_hri.core.emotion_recognizer import ExpressionRecognizer


EXPECTED_FEATURE_KEYS = {
    "smile_score",
    "eye_open_score",
    "eyebrow_raise_score",
    "mouth_open_score",
    "brow_down_score",
    "eye_squint_score",
    "mouth_press_score",
    "gaze_away_score",
    "low_activity_score",
    "face_confidence",
}


def test_output_always_contains_expected_feature_keys():
    extractor = FaceFeatureExtractor()

    features = extractor.extract_from_scores({"smile_score": 0.4})

    assert set(features) == EXPECTED_FEATURE_KEYS


def test_none_input_returns_low_confidence_unknown_safe_features():
    extractor = FaceFeatureExtractor()

    features = extractor.extract_from_scores(None)

    assert features == {
        "smile_score": 0.0,
        "eye_open_score": 0.0,
        "eyebrow_raise_score": 0.0,
        "mouth_open_score": 0.0,
        "brow_down_score": 0.0,
        "eye_squint_score": 0.0,
        "mouth_press_score": 0.0,
        "gaze_away_score": 0.0,
        "low_activity_score": 0.0,
        "face_confidence": 0.0,
    }


def test_missing_fields_are_filled_safely():
    extractor = FaceFeatureExtractor()

    features = extractor.extract_from_scores({"smile_score": 0.25})

    assert features == {
        "smile_score": 0.25,
        "eye_open_score": 0.0,
        "eyebrow_raise_score": 0.0,
        "mouth_open_score": 0.0,
        "brow_down_score": 0.0,
        "eye_squint_score": 0.0,
        "mouth_press_score": 0.0,
        "gaze_away_score": 0.0,
        "low_activity_score": 0.0,
        "face_confidence": 1.0,
    }


def test_values_are_clamped_between_zero_and_one():
    extractor = FaceFeatureExtractor()

    features = extractor.extract_from_scores(
        {
            "smile_score": 2.0,
            "eye_open_score": True,
            "eyebrow_raise_score": "high",
            "mouth_open_score": -1.0,
            "brow_down_score": 0.7,
            "eye_squint_score": 2.0,
            "mouth_press_score": -1.0,
            "gaze_away_score": "side",
            "low_activity_score": 0.5,
            "face_confidence": 3.0,
        }
    )

    assert features == {
        "smile_score": 1.0,
        "eye_open_score": 0.0,
        "eyebrow_raise_score": 0.0,
        "mouth_open_score": 0.0,
        "brow_down_score": 0.7,
        "eye_squint_score": 1.0,
        "mouth_press_score": 0.0,
        "gaze_away_score": 0.0,
        "low_activity_score": 0.5,
        "face_confidence": 1.0,
    }


def test_invalid_low_values_are_clamped_to_zero():
    extractor = FaceFeatureExtractor()

    features = extractor.extract_from_scores(
        {"smile_score": -0.2, "face_confidence": -0.5}
    )

    assert features["smile_score"] == 0.0
    assert features["face_confidence"] == 0.0


def test_extract_from_scores_is_deterministic_and_does_not_mutate_input():
    extractor = FaceFeatureExtractor()
    scores = {"smile_score": 0.5, "mouth_open_score": 0.1}

    first_features = extractor.extract_from_scores(scores)
    second_features = extractor.extract_from_scores(scores)

    assert first_features == second_features
    assert scores == {"smile_score": 0.5, "mouth_open_score": 0.1}


def test_extract_from_landmarks_supports_simple_normalized_aliases():
    extractor = FaceFeatureExtractor()

    features = extractor.extract_from_landmarks(
        {
            "smile": 0.7,
            "eye_open": 0.8,
            "eyebrow_raise": 0.2,
            "mouth_open": 0.1,
            "brow_down": 0.3,
            "eye_squint": 0.4,
            "mouth_press": 0.5,
            "low_activity": 0.6,
        },
        confidence=0.9,
    )

    assert features == {
        "smile_score": 0.7,
        "eye_open_score": 0.8,
        "eyebrow_raise_score": 0.2,
        "mouth_open_score": 0.1,
        "brow_down_score": 0.3,
        "eye_squint_score": 0.4,
        "mouth_press_score": 0.5,
        "gaze_away_score": 0.0,
        "low_activity_score": 0.6,
        "face_confidence": 0.9,
    }


def test_extract_from_landmarks_missing_or_invalid_input_is_safe():
    extractor = FaceFeatureExtractor()

    assert extractor.extract_from_landmarks(None)["face_confidence"] == 0.0
    assert extractor.extract_from_landmarks([])["face_confidence"] == 0.0


def test_extract_from_frame_raises_clear_runtime_error():
    extractor = FaceFeatureExtractor()

    with pytest.raises(RuntimeError, match="Frame-based face feature extraction"):
        extractor.extract_from_frame(frame=object())


def test_extracted_high_smile_is_recognized_as_happy():
    extractor = FaceFeatureExtractor()
    recognizer = ExpressionRecognizer()

    features = extractor.extract_from_scores(
        {"smile_score": 0.9, "mouth_open_score": 0.1}
    )

    assert recognizer.recognize(features) == keys.EXPR_HAPPY


def test_extracted_surprise_features_are_recognized_as_surprise():
    extractor = FaceFeatureExtractor()
    recognizer = ExpressionRecognizer()

    features = extractor.extract_from_scores(
        {"mouth_open_score": 0.8, "eyebrow_raise_score": 0.8}
    )

    assert recognizer.recognize(features) == keys.EXPR_SURPRISE


def test_missing_input_leads_to_unknown_through_recognizer():
    extractor = FaceFeatureExtractor()
    recognizer = ExpressionRecognizer()

    features = extractor.extract_from_scores(None)

    assert recognizer.recognize(features) == keys.EXPR_UNKNOWN


def test_neutral_scores_lead_to_neutral_expression():
    extractor = FaceFeatureExtractor()
    recognizer = ExpressionRecognizer()

    features = extractor.extract_from_scores(
        {
            "smile_score": 0.2,
            "eye_open_score": 0.7,
            "eyebrow_raise_score": 0.2,
            "mouth_open_score": 0.2,
        }
    )

    assert recognizer.recognize(features) == keys.EXPR_NEUTRAL


def test_face_feature_extractor_import_has_no_ros_camera_or_hardware_dependency():
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

    sys.modules.pop("ivastbot_hri.adapters.face_feature_extractor", None)
    module = importlib.import_module("ivastbot_hri.adapters.face_feature_extractor")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.FaceFeatureExtractor is not None
    assert after == before

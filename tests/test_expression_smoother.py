import importlib
import sys

import pytest

from ivastbot_hri.adapters.face_feature_extractor import FaceFeatureExtractor
from ivastbot_hri.core import keys
from ivastbot_hri.core.emotion_recognizer import ExpressionRecognizer
from ivastbot_hri.core.expression_smoother import ExpressionSmoother


def test_initial_current_returns_default_expression():
    smoother = ExpressionSmoother()

    assert smoother.current() == keys.EXPR_UNKNOWN


def test_reset_clears_internal_state():
    smoother = ExpressionSmoother(window_size=3, min_confidence_count=2)
    smoother.update(keys.EXPR_HAPPY)
    smoother.update(keys.EXPR_HAPPY)

    assert smoother.current() == keys.EXPR_HAPPY

    smoother.reset()

    assert smoother.current() == keys.EXPR_UNKNOWN
    assert smoother.update(keys.EXPR_NEUTRAL) == keys.EXPR_UNKNOWN


def test_majority_expression_becomes_stable_after_min_confidence_count():
    smoother = ExpressionSmoother(window_size=5, min_confidence_count=3)

    assert smoother.update(keys.EXPR_HAPPY) == keys.EXPR_UNKNOWN
    assert smoother.update(keys.EXPR_HAPPY) == keys.EXPR_UNKNOWN
    assert smoother.update(keys.EXPR_NEUTRAL) == keys.EXPR_UNKNOWN
    assert smoother.update(keys.EXPR_HAPPY) == keys.EXPR_HAPPY


def test_noisy_expressions_do_not_immediately_change_stable_output():
    smoother = ExpressionSmoother(window_size=5, min_confidence_count=3)

    for expression in (
        keys.EXPR_HAPPY,
        keys.EXPR_HAPPY,
        keys.EXPR_HAPPY,
    ):
        smoother.update(expression)

    assert smoother.current() == keys.EXPR_HAPPY

    for expression in (
        keys.EXPR_NEUTRAL,
        keys.EXPR_CONFUSED,
    ):
        assert smoother.update(expression) == keys.EXPR_HAPPY


def test_none_input_is_treated_as_unknown():
    smoother = ExpressionSmoother(window_size=3, min_confidence_count=2)

    assert smoother.update(None) == keys.EXPR_UNKNOWN
    assert smoother.update(None) == keys.EXPR_UNKNOWN
    assert smoother.current() == keys.EXPR_UNKNOWN


def test_invalid_input_is_treated_as_unknown():
    smoother = ExpressionSmoother(
        window_size=3,
        min_confidence_count=2,
        default_expression=keys.EXPR_NEUTRAL,
    )

    assert smoother.update("NOT_AN_EXPRESSION") == keys.EXPR_NEUTRAL
    assert smoother.update("STILL_NOT_VALID") == keys.EXPR_UNKNOWN


def test_custom_window_size_works():
    smoother = ExpressionSmoother(window_size=2, min_confidence_count=2)

    smoother.update(keys.EXPR_HAPPY)
    assert smoother.update(keys.EXPR_HAPPY) == keys.EXPR_HAPPY
    assert smoother.update(keys.EXPR_NEUTRAL) == keys.EXPR_HAPPY
    assert smoother.update(keys.EXPR_NEUTRAL) == keys.EXPR_NEUTRAL


def test_custom_min_confidence_count_works():
    smoother = ExpressionSmoother(window_size=4, min_confidence_count=1)

    assert smoother.update(keys.EXPR_CONFUSED) == keys.EXPR_CONFUSED


def test_stable_expression_persists_if_no_new_majority_is_reached():
    smoother = ExpressionSmoother(window_size=5, min_confidence_count=3)

    smoother.update(keys.EXPR_HAPPY)
    smoother.update(keys.EXPR_HAPPY)
    smoother.update(keys.EXPR_HAPPY)

    assert smoother.current() == keys.EXPR_HAPPY
    assert smoother.update(keys.EXPR_CONFUSED) == keys.EXPR_HAPPY
    assert smoother.update(keys.EXPR_SURPRISE) == keys.EXPR_HAPPY


def test_invalid_configuration_raises_value_error():
    with pytest.raises(ValueError, match="window_size"):
        ExpressionSmoother(window_size=0)
    with pytest.raises(ValueError, match="min_confidence_count"):
        ExpressionSmoother(min_confidence_count=0)
    with pytest.raises(ValueError, match="<="):
        ExpressionSmoother(window_size=2, min_confidence_count=3)


def test_feature_extractor_recognizer_and_smoother_pipeline():
    extractor = FaceFeatureExtractor()
    recognizer = ExpressionRecognizer()
    smoother = ExpressionSmoother(window_size=3, min_confidence_count=2)

    first_raw = recognizer.recognize(
        extractor.extract_from_scores({"smile_score": 0.9})
    )
    second_raw = recognizer.recognize(
        extractor.extract_from_scores({"smile_score": 0.8})
    )

    assert first_raw == keys.EXPR_HAPPY
    assert smoother.update(first_raw) == keys.EXPR_UNKNOWN
    assert second_raw == keys.EXPR_HAPPY
    assert smoother.update(second_raw) == keys.EXPR_HAPPY


def test_expression_smoother_import_has_no_ros_camera_or_hardware_dependency():
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

    sys.modules.pop("ivastbot_hri.core.expression_smoother", None)
    module = importlib.import_module("ivastbot_hri.core.expression_smoother")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.ExpressionSmoother is not None
    assert after == before

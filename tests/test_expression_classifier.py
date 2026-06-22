import importlib
import json
import sys

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.core.expression_classifier import (
    FEATURE_NAMES,
    NearestCentroidExpressionClassifier,
    evaluate_classifier,
    load_expression_classifier,
    save_expression_classifier,
    split_samples,
)


def sample(label: str, features: dict) -> dict:
    return {"label": label, "features": features}


def training_samples() -> list[dict]:
    return [
        sample(
            "happy",
            {"smile_score": 0.9, "face_confidence": 0.95},
        ),
        sample(
            keys.EXPR_HAPPY,
            {"smile_score": 0.82, "face_confidence": 0.94},
        ),
        sample(
            "surprise",
            {
                "mouth_open_score": 0.9,
                "eyebrow_raise_score": 0.8,
                "face_confidence": 0.95,
            },
        ),
        sample(
            "angry",
            {
                "brow_down_score": 0.85,
                "eye_squint_score": 0.75,
                "mouth_press_score": 0.65,
                "face_confidence": 0.94,
            },
        ),
        sample(
            "bored",
            {"low_activity_score": 0.9, "face_confidence": 0.92},
        ),
        sample(
            "neutral",
            {"eye_open_score": 0.7, "face_confidence": 0.93},
        ),
        sample(
            "unknown",
            {"face_confidence": 0.1},
        ),
    ]


def fitted_classifier() -> NearestCentroidExpressionClassifier:
    return NearestCentroidExpressionClassifier().fit(training_samples())


def test_importing_expression_classifier_requires_no_optional_runtime():
    forbidden_roots = {
        "cv2",
        "mediapipe",
        "numpy",
        "sklearn",
        "tensorflow",
        "torch",
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

    sys.modules.pop("ivastbot_hri.core.expression_classifier", None)
    module = importlib.import_module("ivastbot_hri.core.expression_classifier")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.NearestCentroidExpressionClassifier is not None
    assert after == before


def test_fit_computes_centroids_and_label_counts():
    classifier = fitted_classifier()

    assert keys.EXPR_HAPPY in classifier.centroids
    assert classifier.label_counts[keys.EXPR_HAPPY] == 2
    smile_index = FEATURE_NAMES.index("smile_score")
    assert classifier.centroids[keys.EXPR_HAPPY][smile_index] == pytest.approx(0.86)


def test_predict_returns_expected_expression_for_simple_samples():
    classifier = fitted_classifier()

    assert classifier.predict({"smile_score": 0.88, "face_confidence": 0.95}) == (
        keys.EXPR_HAPPY
    )
    assert classifier.predict(
        {
            "mouth_open_score": 0.88,
            "eyebrow_raise_score": 0.78,
            "face_confidence": 0.95,
        }
    ) == keys.EXPR_SURPRISE
    assert classifier.predict(
        {
            "brow_down_score": 0.86,
            "eye_squint_score": 0.76,
            "mouth_press_score": 0.66,
            "face_confidence": 0.95,
        }
    ) == keys.EXPR_ANGRY
    assert classifier.predict({"low_activity_score": 0.88, "face_confidence": 0.95}) == (
        keys.EXPR_BORED
    )


def test_missing_features_default_to_zero():
    classifier = NearestCentroidExpressionClassifier().fit(
        [
            sample("happy", {"smile_score": 1.0, "face_confidence": 1.0}),
            sample("neutral", {"face_confidence": 1.0}),
        ]
    )

    assert classifier.predict({"face_confidence": 1.0}) == keys.EXPR_NEUTRAL


def test_low_face_confidence_returns_unknown():
    classifier = fitted_classifier()

    result = classifier.predict_with_scores({"smile_score": 1.0, "face_confidence": 0.1})

    assert result["prediction"] == keys.EXPR_UNKNOWN
    assert result["reason"] == "low_face_confidence"


def test_unfitted_classifier_returns_unknown():
    classifier = NearestCentroidExpressionClassifier()

    result = classifier.predict_with_scores({"smile_score": 1.0, "face_confidence": 1.0})

    assert result["prediction"] == keys.EXPR_UNKNOWN
    assert result["reason"] == "unfitted"


def test_distance_threshold_can_reject_far_features():
    classifier = NearestCentroidExpressionClassifier(max_distance_threshold=0.1).fit(
        [
            sample("happy", {"smile_score": 1.0, "face_confidence": 1.0}),
            sample("neutral", {"face_confidence": 1.0}),
        ]
    )

    result = classifier.predict_with_scores(
        {
            "smile_score": 0.5,
            "mouth_open_score": 0.5,
            "face_confidence": 1.0,
        }
    )

    assert result["prediction"] == keys.EXPR_UNKNOWN
    assert result["reason"] == "distance_threshold"


def test_fit_rejects_empty_samples_with_clear_error():
    with pytest.raises(ValueError, match="At least one training sample"):
        NearestCentroidExpressionClassifier().fit([])


def test_unsupported_label_raises_clear_error():
    with pytest.raises(ValueError, match="Unsupported expression label"):
        NearestCentroidExpressionClassifier().fit([sample("sleepy", {})])


def test_to_dict_from_dict_round_trip_preserves_behavior():
    classifier = fitted_classifier()
    restored = NearestCentroidExpressionClassifier.from_dict(classifier.to_dict())
    features = {"smile_score": 0.88, "face_confidence": 0.95}

    assert restored.to_dict() == classifier.to_dict()
    assert restored.predict(features) == classifier.predict(features)


def test_save_load_expression_classifier_round_trip(tmp_path):
    classifier = fitted_classifier()
    output_path = tmp_path / "models" / "expression_classifier.json"

    save_expression_classifier(classifier, str(output_path))
    restored = load_expression_classifier(str(output_path))

    assert json.loads(output_path.read_text(encoding="utf-8")) == classifier.to_dict()
    assert restored.predict({"smile_score": 0.88, "face_confidence": 0.95}) == (
        keys.EXPR_HAPPY
    )


def test_load_expression_classifier_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Expression classifier file"):
        load_expression_classifier(str(tmp_path / "missing.json"))


def test_split_samples_is_deterministic():
    samples = training_samples()

    first = split_samples(samples, test_ratio=0.3, seed=42)
    second = split_samples(samples, test_ratio=0.3, seed=42)
    different = split_samples(samples, test_ratio=0.3, seed=43)

    assert first == second
    assert first != different


def test_evaluate_classifier_returns_counts_accuracy_and_confusion():
    classifier = NearestCentroidExpressionClassifier().fit(
        [
            sample("happy", {"smile_score": 1.0, "face_confidence": 1.0}),
            sample("neutral", {"face_confidence": 1.0}),
        ]
    )
    evaluation = evaluate_classifier(
        classifier,
        [
            sample("happy", {"smile_score": 1.0, "face_confidence": 1.0}),
            sample("happy", {"face_confidence": 1.0}),
            sample("neutral", {"face_confidence": 1.0}),
        ],
    )

    assert evaluation["total"] == 3
    assert evaluation["correct"] == 2
    assert evaluation["accuracy"] == pytest.approx(2 / 3)
    assert evaluation["per_label"][keys.EXPR_HAPPY]["total"] == 2
    assert evaluation["per_label"][keys.EXPR_HAPPY]["correct"] == 1
    assert evaluation["confusion"][keys.EXPR_HAPPY][keys.EXPR_HAPPY] == 1
    assert evaluation["confusion"][keys.EXPR_HAPPY][keys.EXPR_NEUTRAL] == 1

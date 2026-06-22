import importlib
import json
import sys

from ivastbot_hri.core import keys
from ivastbot_hri.core.expression_classifier import load_expression_classifier
from ivastbot_hri.demos.train_expression_classifier import train_expression_classifier


def calibration_samples() -> list[dict]:
    return [
        {
            "label": "happy",
            "features": {"smile_score": 0.9, "face_confidence": 0.95},
            "predicted_expression": keys.EXPR_HAPPY,
            "matched_expected": True,
        },
        {
            "label": "happy",
            "features": {"smile_score": 0.85, "face_confidence": 0.95},
            "predicted_expression": keys.EXPR_HAPPY,
            "matched_expected": True,
        },
        {
            "label": "neutral",
            "features": {"face_confidence": 0.95},
            "predicted_expression": keys.EXPR_NEUTRAL,
            "matched_expected": True,
        },
        {
            "label": "angry",
            "features": {
                "brow_down_score": 0.85,
                "eye_squint_score": 0.8,
                "face_confidence": 0.95,
            },
            "predicted_expression": keys.EXPR_ANGRY,
            "matched_expected": True,
        },
    ]


def test_importing_train_expression_classifier_does_not_train_or_require_runtime(
    tmp_path,
):
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
    output_path = tmp_path / "expression_classifier.json"

    sys.modules.pop("ivastbot_hri.demos.train_expression_classifier", None)
    module = importlib.import_module("ivastbot_hri.demos.train_expression_classifier")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.train_expression_classifier is not None
    assert after == before
    assert not output_path.exists()


def test_train_expression_classifier_saves_model_and_returns_evaluation(tmp_path):
    input_path = tmp_path / "samples.json"
    output_path = tmp_path / "models" / "expression_classifier.json"
    input_path.write_text(json.dumps(calibration_samples()), encoding="utf-8")

    result = train_expression_classifier(
        input_path=str(input_path),
        output_path=str(output_path),
        test_ratio=0.0,
    )

    assert output_path.exists()
    assert result["train_count"] == 4
    assert result["test_count"] == 0
    assert result["evaluation"]["total"] == 4
    assert result["evaluation"]["accuracy"] == 1.0

    classifier = load_expression_classifier(str(output_path))
    assert classifier.predict({"smile_score": 0.88, "face_confidence": 0.95}) == (
        keys.EXPR_HAPPY
    )

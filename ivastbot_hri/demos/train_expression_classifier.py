"""CLI helper for training the pure-Python expression classifier."""

import argparse
import json

from ivastbot_hri.core.expression_classifier import (
    NearestCentroidExpressionClassifier,
    evaluate_classifier,
    save_expression_classifier,
    split_samples,
)
from ivastbot_hri.demos.calibration_analyzer import load_calibration_samples


def train_expression_classifier(
    input_path: str,
    output_path: str,
    test_ratio: float = 0.2,
    seed: int = 0,
    max_distance_threshold: float | None = 1.25,
    min_face_confidence: float = 0.5,
) -> dict:
    """Train, evaluate, and save a nearest-centroid expression classifier."""
    samples = load_calibration_samples(input_path)
    train_samples, test_samples = split_samples(samples, test_ratio=test_ratio, seed=seed)
    if not train_samples:
        raise ValueError("Training split is empty; provide more samples or lower test_ratio.")

    classifier = NearestCentroidExpressionClassifier(
        max_distance_threshold=max_distance_threshold,
        min_face_confidence=min_face_confidence,
    ).fit(train_samples)
    evaluation_samples = test_samples or train_samples
    evaluation = evaluate_classifier(classifier, evaluation_samples)
    save_expression_classifier(classifier, output_path)

    return {
        "input_path": input_path,
        "output_path": output_path,
        "train_count": len(train_samples),
        "test_count": len(test_samples),
        "evaluation": evaluation,
    }


def main() -> int:
    """Run classifier training from the command line."""
    parser = argparse.ArgumentParser(
        description="Train a pure-Python IVASTBOT HRI expression classifier."
    )
    parser.add_argument("--input", required=True, help="Calibration sample JSON path.")
    parser.add_argument("--output", required=True, help="Classifier JSON output path.")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-distance-threshold", type=float, default=1.25)
    parser.add_argument("--min-face-confidence", type=float, default=0.5)
    args = parser.parse_args()

    result = train_expression_classifier(
        input_path=args.input,
        output_path=args.output,
        test_ratio=args.test_ratio,
        seed=args.seed,
        max_distance_threshold=args.max_distance_threshold,
        min_face_confidence=args.min_face_confidence,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


__all__ = ("main", "train_expression_classifier")


if __name__ == "__main__":
    raise SystemExit(main())

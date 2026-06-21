"""Optional local webcam demo for the HRI expression pipeline."""

import importlib
from pprint import pprint

from ivastbot_hri.adapters.face_feature_extractor import FaceFeatureExtractor
from ivastbot_hri.core.emotion_recognizer import ExpressionRecognizer
from ivastbot_hri.core.expression_smoother import ExpressionSmoother

OPENCV_UNAVAILABLE_MESSAGE = (
    "OpenCV is required for webcam demo. Install opencv-python to use this demo."
)
WEBCAM_UNAVAILABLE_MESSAGE = "Unable to open webcam for HRI expression demo."


def build_webcam_expression_pipeline() -> dict:
    """Build reusable local expression pipeline components."""
    return {
        "feature_extractor": FaceFeatureExtractor(),
        "recognizer": ExpressionRecognizer(),
        "smoother": ExpressionSmoother(window_size=3, min_confidence_count=1),
    }


def process_feature_scores(scores: dict, pipeline: dict | None = None) -> dict:
    """Process normalized score input through extraction, recognition, and smoothing."""
    active_pipeline = pipeline or build_webcam_expression_pipeline()
    extracted_features = active_pipeline["feature_extractor"].extract_from_scores(
        scores
    )
    raw_expression = active_pipeline["recognizer"].recognize(extracted_features)
    smoothed_expression = active_pipeline["smoother"].update(raw_expression)

    return {
        "extracted_features": extracted_features,
        "raw_expression": raw_expression,
        "smoothed_expression": smoothed_expression,
    }


def run_webcam_demo(camera_index: int = 0, max_frames: int | None = None) -> list[dict]:
    """Run an optional webcam debug loop using placeholder per-frame scores."""
    cv2 = _load_cv2()
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(WEBCAM_UNAVAILABLE_MESSAGE)

    pipeline = build_webcam_expression_pipeline()
    results = []
    frame_count = 0

    try:
        while max_frames is None or frame_count < max_frames:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("Unable to read frame from webcam.")

            debug_result = process_feature_scores(
                _placeholder_scores_for_frame(frame_count, frame),
                pipeline=pipeline,
            )
            results.append(debug_result)
            pprint(debug_result)
            frame_count += 1
    finally:
        capture.release()

    return results


def main() -> int:
    """Run the webcam demo from the command line."""
    run_webcam_demo()
    return 0


def _load_cv2():
    try:
        return importlib.import_module("cv2")
    except ImportError as error:
        raise RuntimeError(OPENCV_UNAVAILABLE_MESSAGE) from error


def _placeholder_scores_for_frame(frame_count: int, frame) -> dict:
    return {
        "smile_score": 0.0,
        "mouth_open_score": 0.0,
        "eyebrow_raise_score": 0.0,
        "eye_open_score": 0.0,
        "face_confidence": 0.0,
        "frame_index": frame_count,
    }


if __name__ == "__main__":
    raise SystemExit(main())

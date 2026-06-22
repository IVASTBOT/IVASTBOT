"""Visual webcam expression demo with OpenCV overlay.

Usage:
    python -m ivastbot_hri.demos.visual_webcam_expression_demo

Controls:
    Press q to quit.

Suggested manual install:
    pip install opencv-python mediapipe
"""

import importlib

from ivastbot_hri.adapters.face_feature_extractor import FaceFeatureExtractor
from ivastbot_hri.core.emotion_recognizer import ExpressionRecognizer
from ivastbot_hri.core.expression_smoother import ExpressionSmoother

OPENCV_UNAVAILABLE_MESSAGE = (
    "OpenCV is required for visual webcam demo. Install opencv-python to use "
    "this demo."
)
MEDIAPIPE_UNAVAILABLE_MESSAGE = (
    "MediaPipe is required for real facial landmark extraction. Install "
    "mediapipe to use real expression detection."
)
WEBCAM_UNAVAILABLE_MESSAGE = "Unable to open webcam for visual expression demo."
WINDOW_NAME = "IVASTBOT HRI Expression Demo"


def build_visual_expression_pipeline() -> dict:
    """Build reusable local expression pipeline components."""
    return {
        "feature_extractor": FaceFeatureExtractor(),
        "recognizer": ExpressionRecognizer(),
        "smoother": ExpressionSmoother(window_size=5, min_confidence_count=2),
    }


def overlay_debug_info(frame, debug_info: dict, cv2_module=None):
    """Overlay expression and feature debug text on a frame."""
    cv2 = cv2_module or _load_cv2()
    font = getattr(cv2, "FONT_HERSHEY_SIMPLEX", 0)
    lines = _debug_overlay_lines(debug_info)

    for index, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (12, 28 + index * 24),
            font,
            0.6,
            (0, 255, 0),
            2,
        )

    return frame


def process_frame_with_optional_backend(
    frame,
    extractor,
    recognizer,
    smoother,
    backend=None,
) -> dict:
    """Extract frame features and run recognition/smoothing."""
    active_backend = backend or MediaPipeFaceFeatureBackend()
    scores = active_backend.extract_scores(frame)
    extracted_features = extractor.extract_from_scores(scores)
    raw_expression = recognizer.recognize(extracted_features)
    smoothed_expression = smoother.update(raw_expression)

    return {
        "extracted_features": extracted_features,
        "raw_expression": raw_expression,
        "smoothed_expression": smoothed_expression,
    }


def run_visual_webcam_demo(
    camera_index: int = 0,
    max_frames: int | None = None,
) -> list[dict]:
    """Run the visual webcam expression demo."""
    cv2 = _load_cv2()
    backend = MediaPipeFaceFeatureBackend()
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(WEBCAM_UNAVAILABLE_MESSAGE)

    pipeline = build_visual_expression_pipeline()
    results = []
    frame_count = 0

    try:
        while max_frames is None or frame_count < max_frames:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("Unable to read frame from webcam.")

            debug_info = process_frame_with_optional_backend(
                frame,
                pipeline["feature_extractor"],
                pipeline["recognizer"],
                pipeline["smoother"],
                backend=backend,
            )
            overlay_debug_info(frame, debug_info, cv2_module=cv2)
            cv2.imshow(WINDOW_NAME, frame)
            results.append(debug_info)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            frame_count += 1
    finally:
        capture.release()
        cv2.destroyAllWindows()
        if hasattr(backend, "close"):
            backend.close()

    return results


def main() -> int:
    """Run the visual webcam expression demo from the command line."""
    run_visual_webcam_demo()
    return 0


class MediaPipeFaceFeatureBackend:
    """Extract approximate normalized expression scores from MediaPipe landmarks."""

    def __init__(self):
        mediapipe = _load_mediapipe()
        self._mp_face_mesh = mediapipe.solutions.face_mesh
        self._face_mesh = self._mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def extract_scores(self, frame) -> dict:
        cv2 = _load_cv2()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._face_mesh.process(rgb_frame)

        if not result.multi_face_landmarks:
            return _empty_scores()

        landmarks = result.multi_face_landmarks[0].landmark
        return _scores_from_landmarks(landmarks)

    def close(self) -> None:
        if hasattr(self._face_mesh, "close"):
            self._face_mesh.close()


def _load_cv2():
    try:
        return importlib.import_module("cv2")
    except ImportError as error:
        raise RuntimeError(OPENCV_UNAVAILABLE_MESSAGE) from error


def _load_mediapipe():
    try:
        return importlib.import_module("mediapipe")
    except ImportError as error:
        raise RuntimeError(MEDIAPIPE_UNAVAILABLE_MESSAGE) from error


def _scores_from_landmarks(landmarks) -> dict:
    left_mouth = landmarks[61]
    right_mouth = landmarks[291]
    upper_lip = landmarks[13]
    lower_lip = landmarks[14]
    left_eye_top = landmarks[159]
    left_eye_bottom = landmarks[145]
    right_eye_top = landmarks[386]
    right_eye_bottom = landmarks[374]
    left_brow = landmarks[105]
    right_brow = landmarks[334]

    mouth_width = _distance(left_mouth, right_mouth)
    mouth_open = _distance(upper_lip, lower_lip)
    left_eye_open = _distance(left_eye_top, left_eye_bottom)
    right_eye_open = _distance(right_eye_top, right_eye_bottom)
    brow_raise = (_vertical_gap(left_brow, left_eye_top) + _vertical_gap(
        right_brow,
        right_eye_top,
    )) / 2.0

    mouth_open_score = _clamp(mouth_open / max(mouth_width * 0.35, 0.001))
    eye_open_score = _clamp(((left_eye_open + right_eye_open) / 2.0) / 0.035)
    eyebrow_raise_score = _clamp(brow_raise / 0.09)
    smile_score = _clamp((mouth_width - mouth_open * 0.25) / 0.16)

    return {
        "smile_score": smile_score,
        "mouth_open_score": mouth_open_score,
        "eyebrow_raise_score": eyebrow_raise_score,
        "eye_open_score": eye_open_score,
        "face_confidence": 1.0,
    }


def _debug_overlay_lines(debug_info: dict) -> list[str]:
    features = debug_info.get("extracted_features", {})
    return [
        f"raw_expression: {debug_info.get('raw_expression')}",
        f"smoothed_expression: {debug_info.get('smoothed_expression')}",
        f"smile_score: {_format_score(features.get('smile_score'))}",
        f"mouth_open_score: {_format_score(features.get('mouth_open_score'))}",
        f"eyebrow_raise_score: {_format_score(features.get('eyebrow_raise_score'))}",
        f"eye_open_score: {_format_score(features.get('eye_open_score'))}",
        f"face_confidence: {_format_score(features.get('face_confidence'))}",
        "press q to quit",
    ]


def _empty_scores() -> dict:
    return {
        "smile_score": 0.0,
        "mouth_open_score": 0.0,
        "eyebrow_raise_score": 0.0,
        "eye_open_score": 0.0,
        "face_confidence": 0.0,
    }


def _format_score(value) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "0.00"
    return f"{float(value):.2f}"


def _distance(point_a, point_b) -> float:
    return (
        (float(point_a.x) - float(point_b.x)) ** 2
        + (float(point_a.y) - float(point_b.y)) ** 2
    ) ** 0.5


def _vertical_gap(point_a, point_b) -> float:
    return abs(float(point_a.y) - float(point_b.y))


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


if __name__ == "__main__":
    raise SystemExit(main())

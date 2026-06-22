"""Visual webcam expression demo with OpenCV overlay.

Usage:
    set IVASTBOT_FACE_LANDMARKER_MODEL=F:\\models\\face_landmarker.task
    python -m ivastbot_hri.demos.visual_webcam_expression_demo

Controls:
    Press q to quit.

Suggested manual install:
    pip install opencv-python mediapipe
"""

import importlib
import os

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
MEDIAPIPE_FACE_MESH_UNAVAILABLE_MESSAGE = (
    "The installed MediaPipe version may not support the legacy FaceMesh "
    "Solutions API. Install a compatible MediaPipe version or implement a "
    "MediaPipe Tasks backend for this demo. The demo cannot continue without "
    "a FaceMesh backend, but it should not crash with AttributeError."
)
MEDIAPIPE_TASKS_MODEL_REQUIRED_MESSAGE = (
    "MediaPipe Tasks FaceLandmarker requires a .task model file. Set "
    "IVASTBOT_FACE_LANDMARKER_MODEL to the path of face_landmarker.task."
)
MEDIAPIPE_TASKS_UNAVAILABLE_MESSAGE = (
    "MediaPipe Tasks FaceLandmarker API is unavailable. Install a MediaPipe "
    "version that provides mediapipe.tasks.python.vision.FaceLandmarker."
)
WEBCAM_UNAVAILABLE_MESSAGE = "Unable to open webcam for visual expression demo."
WINDOW_NAME = "IVASTBOT HRI Expression Demo"
FACE_LANDMARKER_MODEL_ENV_VAR = "IVASTBOT_FACE_LANDMARKER_MODEL"


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
    model_path: str | None = None,
) -> dict:
    """Extract frame features and run recognition/smoothing."""
    active_backend = backend or _build_default_feature_backend(model_path)
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
    model_path: str | None = None,
) -> list[dict]:
    """Run the visual webcam expression demo."""
    cv2 = _load_cv2()
    backend = _build_default_feature_backend(model_path)
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
        self._mp_face_mesh = _load_mediapipe_face_mesh()
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


class MediaPipeTasksFaceLandmarkerBackend:
    """Extract expression scores from the MediaPipe Tasks FaceLandmarker API."""

    def __init__(self, model_path: str | None = None):
        resolved_model_path = _resolve_face_landmarker_model_path(model_path)
        if resolved_model_path is None:
            raise RuntimeError(MEDIAPIPE_TASKS_MODEL_REQUIRED_MESSAGE)

        self.model_path = resolved_model_path
        components = _load_mediapipe_tasks_components()
        self._mediapipe = components["mediapipe"]
        face_landmarker = components["FaceLandmarker"]
        options = components["FaceLandmarkerOptions"](
            base_options=components["BaseOptions"](
                model_asset_path=self.model_path,
            ),
            running_mode=components["RunningMode"].IMAGE,
            output_face_blendshapes=True,
        )
        self._landmarker = face_landmarker.create_from_options(options)

    def extract_scores(self, frame) -> dict:
        cv2 = _load_cv2()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._landmarker.detect(self._create_image(rgb_frame))
        return _scores_from_tasks_result(result)

    def close(self) -> None:
        if hasattr(self._landmarker, "close"):
            self._landmarker.close()

    def _create_image(self, rgb_frame):
        image_cls = getattr(self._mediapipe, "Image", None)
        image_format = getattr(self._mediapipe, "ImageFormat", None)
        srgb_format = getattr(image_format, "SRGB", None)
        if image_cls is None or srgb_format is None:
            raise RuntimeError(MEDIAPIPE_TASKS_UNAVAILABLE_MESSAGE)
        return image_cls(image_format=srgb_format, data=rgb_frame)


def _build_default_feature_backend(model_path: str | None = None):
    try:
        return MediaPipeFaceFeatureBackend()
    except RuntimeError as error:
        if str(error) == MEDIAPIPE_UNAVAILABLE_MESSAGE:
            raise
        resolved_model_path = _resolve_face_landmarker_model_path(model_path)
        if resolved_model_path is None:
            raise RuntimeError(MEDIAPIPE_TASKS_MODEL_REQUIRED_MESSAGE) from error
        return MediaPipeTasksFaceLandmarkerBackend(resolved_model_path)


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


def _load_mediapipe_face_mesh():
    mediapipe = _load_mediapipe()
    solutions = getattr(mediapipe, "solutions", None)
    face_mesh = getattr(solutions, "face_mesh", None)
    if face_mesh is not None:
        return face_mesh

    try:
        return importlib.import_module("mediapipe.python.solutions.face_mesh")
    except (AttributeError, ImportError) as error:
        raise RuntimeError(MEDIAPIPE_FACE_MESH_UNAVAILABLE_MESSAGE) from error


def _load_mediapipe_tasks_components() -> dict:
    mediapipe = _load_mediapipe()
    try:
        vision = importlib.import_module("mediapipe.tasks.python.vision")
    except ImportError as error:
        raise RuntimeError(MEDIAPIPE_TASKS_UNAVAILABLE_MESSAGE) from error

    base_options = getattr(getattr(mediapipe, "tasks", None), "BaseOptions", None)
    if base_options is None:
        try:
            tasks_python = importlib.import_module("mediapipe.tasks.python")
        except ImportError as error:
            raise RuntimeError(MEDIAPIPE_TASKS_UNAVAILABLE_MESSAGE) from error
        base_options = getattr(tasks_python, "BaseOptions", None)

    required_components = {
        "BaseOptions": base_options,
        "FaceLandmarker": getattr(vision, "FaceLandmarker", None),
        "FaceLandmarkerOptions": getattr(vision, "FaceLandmarkerOptions", None),
        "RunningMode": getattr(vision, "RunningMode", None),
    }
    missing = [
        name for name, component in required_components.items() if component is None
    ]
    if missing:
        raise RuntimeError(
            f"{MEDIAPIPE_TASKS_UNAVAILABLE_MESSAGE} Missing: {', '.join(missing)}."
        )

    return {
        "mediapipe": mediapipe,
        **required_components,
    }


def _resolve_face_landmarker_model_path(model_path: str | None = None) -> str | None:
    resolved_model_path = model_path or os.environ.get(FACE_LANDMARKER_MODEL_ENV_VAR)
    if resolved_model_path is None:
        return None
    stripped_model_path = str(resolved_model_path).strip()
    return stripped_model_path or None


def _scores_from_tasks_result(result) -> dict:
    if result is None:
        return _empty_scores()

    blendshape_scores = _scores_from_blendshapes(
        getattr(result, "face_blendshapes", None)
    )
    if blendshape_scores is not None:
        return blendshape_scores

    face_landmarks = getattr(result, "face_landmarks", None)
    if not face_landmarks:
        return _empty_scores()

    return _scores_from_landmarks(face_landmarks[0])


def _scores_from_blendshapes(face_blendshapes) -> dict | None:
    categories = list(_iter_blendshape_categories(face_blendshapes))
    if not categories:
        return None

    scores_by_name = {
        _normalize_blendshape_name(category): _category_score(category)
        for category in categories
    }
    eye_blink_scores = [
        _score_for_blendshape_names(scores_by_name, ("eyeblinkleft",)),
        _score_for_blendshape_names(scores_by_name, ("eyeblinkright",)),
    ]
    known_blink_scores = [
        score for score in eye_blink_scores if score is not None
    ]
    blink_score = (
        sum(known_blink_scores) / len(known_blink_scores)
        if known_blink_scores
        else 1.0
    )

    return {
        "smile_score": _score_or_zero(
            _score_for_blendshape_names(
                scores_by_name,
                (
                    "mouthsmileleft",
                    "mouthsmileright",
                    "mouthsmile",
                ),
            )
        ),
        "mouth_open_score": _score_or_zero(
            _score_for_blendshape_names(
                scores_by_name,
                (
                    "jawopen",
                    "mouthopen",
                ),
            )
        ),
        "eyebrow_raise_score": _score_or_zero(
            _score_for_blendshape_names(
                scores_by_name,
                (
                    "browouterupleft",
                    "browouterupright",
                    "browinnerup",
                ),
            )
        ),
        "eye_open_score": _clamp(1.0 - blink_score),
        "brow_down_score": _score_or_zero(
            _score_for_blendshape_names(
                scores_by_name,
                (
                    "browdownleft",
                    "browdownright",
                    "browdown",
                ),
            )
        ),
        "eye_squint_score": _score_or_zero(
            _score_for_blendshape_names(
                scores_by_name,
                (
                    "eyesquintleft",
                    "eyesquintright",
                    "eyesquint",
                ),
            )
        ),
        "mouth_press_score": _score_or_zero(
            _score_for_blendshape_names(
                scores_by_name,
                (
                    "mouthpressleft",
                    "mouthpressright",
                    "mouthpress",
                ),
            )
        ),
        "gaze_away_score": 0.0,
        "low_activity_score": 0.0,
        "face_confidence": 1.0,
    }


def _scores_from_landmarks(landmarks) -> dict:
    try:
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
    except (AttributeError, IndexError, TypeError, ValueError):
        return _empty_scores_with_confidence(1.0)

    mouth_open_score = _clamp(mouth_open / max(mouth_width * 0.35, 0.001))
    eye_open_score = _clamp(((left_eye_open + right_eye_open) / 2.0) / 0.035)
    eyebrow_raise_score = _clamp(brow_raise / 0.09)
    smile_score = _clamp((mouth_width - mouth_open * 0.25) / 0.16)

    return {
        "smile_score": smile_score,
        "mouth_open_score": mouth_open_score,
        "eyebrow_raise_score": eyebrow_raise_score,
        "eye_open_score": eye_open_score,
        "brow_down_score": 0.0,
        "eye_squint_score": 0.0,
        "mouth_press_score": 0.0,
        "gaze_away_score": 0.0,
        "low_activity_score": 0.0,
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
        f"brow_down_score: {_format_score(features.get('brow_down_score'))}",
        f"eye_squint_score: {_format_score(features.get('eye_squint_score'))}",
        f"mouth_press_score: {_format_score(features.get('mouth_press_score'))}",
        f"face_confidence: {_format_score(features.get('face_confidence'))}",
        "press q to quit",
    ]


def _empty_scores() -> dict:
    return _empty_scores_with_confidence(0.0)


def _empty_scores_with_confidence(face_confidence: float) -> dict:
    return {
        "smile_score": 0.0,
        "mouth_open_score": 0.0,
        "eyebrow_raise_score": 0.0,
        "eye_open_score": 0.0,
        "brow_down_score": 0.0,
        "eye_squint_score": 0.0,
        "mouth_press_score": 0.0,
        "gaze_away_score": 0.0,
        "low_activity_score": 0.0,
        "face_confidence": _clamp(face_confidence),
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


def _iter_blendshape_categories(face_blendshapes):
    for group in face_blendshapes or ():
        categories = getattr(group, "categories", group)
        for category in categories or ():
            yield category


def _normalize_blendshape_name(category) -> str:
    name = getattr(category, "category_name", None)
    if name is None:
        name = getattr(category, "display_name", "")
    return str(name).replace("_", "").replace("-", "").lower()


def _category_score(category) -> float:
    return _clamp(getattr(category, "score", 0.0))


def _score_for_blendshape_names(
    scores_by_name: dict[str, float],
    names: tuple[str, ...],
) -> float | None:
    found_scores = [
        score for name, score in scores_by_name.items() if name in names
    ]
    if not found_scores:
        return None
    return _clamp(max(found_scores))


def _score_or_zero(score: float | None) -> float:
    if score is None:
        return 0.0
    return _clamp(score)


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


if __name__ == "__main__":
    raise SystemExit(main())

"""Visual webcam expression demo with OpenCV overlay.

Usage:
    python -m ivastbot_hri.demos.visual_webcam_expression_demo

Classifier mode:
    set IVASTBOT_EXPRESSION_CLASSIFIER_MODEL=F:\\models\\expression_classifier.json
    python -m ivastbot_hri.demos.visual_webcam_expression_demo

Comparison mode:
    set IVASTBOT_COMPARE_RECOGNIZERS=1
    set IVASTBOT_EXPRESSION_CLASSIFIER_MODEL=F:\\models\\expression_classifier.json
    python -m ivastbot_hri.demos.visual_webcam_expression_demo

MediaPipe Tasks model:
    set IVASTBOT_FACE_LANDMARKER_MODEL=F:\\models\\face_landmarker.task
    python -m ivastbot_hri.demos.visual_webcam_expression_demo

Controls:
    Click a face to lock it manually.
    q: quit
    u/a: return to automatic selection
    n/p: cycle visible candidates
    l: manually lock the current target

Suggested manual install:
    pip install opencv-python mediapipe
"""

import importlib
import os

from ivastbot_hri.adapters.face_feature_extractor import FaceFeatureExtractor
from ivastbot_hri.core import keys
from ivastbot_hri.core.emotion_recognizer import ExpressionRecognizer
from ivastbot_hri.core.expression_smoother import ExpressionSmoother
from ivastbot_hri.core.target_lock import (
    TargetLockManager,
    normalize_candidate,
)

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
EXPRESSION_CLASSIFIER_MODEL_ENV_VAR = "IVASTBOT_EXPRESSION_CLASSIFIER_MODEL"
COMPARE_RECOGNIZERS_ENV_VAR = "IVASTBOT_COMPARE_RECOGNIZERS"
PREFER_CLASSIFIER_ENV_VAR = "IVASTBOT_PREFER_CLASSIFIER"
EXPRESSION_CLASSIFIER_LOAD_ERROR_MESSAGE = (
    "Unable to load expression classifier from "
    f"{EXPRESSION_CLASSIFIER_MODEL_ENV_VAR}."
)
TRUE_ENV_VALUES = ("1", "true", "yes", "on")


def build_visual_expression_pipeline(
    expression_classifier=None,
    compare_recognizers: bool | None = None,
    prefer_classifier: bool | None = None,
) -> dict:
    """Build reusable local expression pipeline components."""
    active_classifier = (
        expression_classifier
        if expression_classifier is not None
        else load_optional_expression_classifier()
    )
    active_compare = (
        is_env_flag_enabled(COMPARE_RECOGNIZERS_ENV_VAR)
        if compare_recognizers is None
        else bool(compare_recognizers)
    )
    active_prefer_classifier = (
        is_env_flag_enabled(PREFER_CLASSIFIER_ENV_VAR)
        if prefer_classifier is None
        else bool(prefer_classifier)
    )
    return {
        "feature_extractor": FaceFeatureExtractor(),
        "recognizer": ExpressionRecognizer(),
        "expression_classifier": active_classifier,
        "compare_recognizers": active_compare,
        "prefer_classifier": active_prefer_classifier,
        "recognizer_mode": _recognizer_mode(active_compare, active_classifier),
        "smoother": ExpressionSmoother(window_size=5, min_confidence_count=2),
        "target_lock_manager": TargetLockManager(),
    }


def load_optional_expression_classifier(
    env_var: str = EXPRESSION_CLASSIFIER_MODEL_ENV_VAR,
    loader=None,
):
    """Load the optional expression classifier only when env_var is set."""
    model_path = os.environ.get(env_var, "").strip()
    if not model_path:
        return None

    if loader is None:
        from ivastbot_hri.core.expression_classifier import load_expression_classifier

        loader = load_expression_classifier

    try:
        return loader(model_path)
    except (FileNotFoundError, OSError, ValueError) as error:
        raise RuntimeError(
            f"{EXPRESSION_CLASSIFIER_LOAD_ERROR_MESSAGE} Path: {model_path}"
        ) from error


def is_env_flag_enabled(env_var: str) -> bool:
    """Return True when the environment variable is set to a known true value."""
    return os.environ.get(env_var, "").strip().lower() in TRUE_ENV_VALUES


def select_final_expression(
    rule_expression: str,
    classifier_expression: str | None,
    classifier_available: bool,
    prefer_classifier: bool = False,
) -> str:
    """Select the expression that should feed smoothing and downstream behavior."""
    if not classifier_available:
        return rule_expression

    candidate = classifier_expression or keys.EXPR_UNKNOWN
    if candidate == keys.EXPR_UNKNOWN:
        return rule_expression
    if prefer_classifier or rule_expression == keys.EXPR_UNKNOWN:
        return candidate
    return rule_expression


def build_recognition_debug_info(
    recognizer_mode: str,
    rule_expression: str,
    classifier_expression: str | None,
    final_expression: str,
    smoothed_expression: str,
    classifier_available: bool,
    target_mode: str = "auto",
    target_locked: bool = False,
    target_id=None,
    target_backend_index: int | None = None,
    candidate_count: int = 0,
) -> dict:
    """Build recognition debug data for tests and overlay text."""
    normalized_classifier_expression = classifier_expression or keys.EXPR_UNKNOWN
    resolved_target_id = (
        target_id if target_id is not None else target_backend_index
    )
    return {
        "recognizer_mode": recognizer_mode,
        "target_mode": target_mode,
        "target_locked": bool(target_locked),
        "target_id": resolved_target_id,
        "target_backend_index": target_backend_index,
        "candidate_count": candidate_count,
        "target_candidate_count": candidate_count,
        "rule_expression": rule_expression,
        "classifier_expression": normalized_classifier_expression,
        "final_expression": final_expression,
        "raw_expression": final_expression,
        "smoothed_expression": smoothed_expression,
        "classifier_available": classifier_available,
        "recognizers_disagree": (
            classifier_available
            and rule_expression != normalized_classifier_expression
        ),
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

    _draw_target_candidates(frame, debug_info, cv2)
    _draw_locked_target_bbox(frame, debug_info, cv2)
    return frame


def find_candidate_at_point(candidates, x: float, y: float):
    """Return the smallest face candidate containing the selected point."""
    matches = []
    for index, candidate in enumerate(candidates or ()):
        try:
            normalized = normalize_candidate(candidate)
        except (TypeError, ValueError):
            continue
        box_x, box_y, width, height = normalized.bbox
        if box_x <= x <= box_x + width and box_y <= y <= box_y + height:
            matches.append(
                (
                    normalized.area,
                    -normalized.confidence,
                    normalized.raw_backend_index is None,
                    normalized.raw_backend_index
                    if normalized.raw_backend_index is not None
                    else index,
                    index,
                    normalized,
                )
            )
    if not matches:
        return None
    return min(matches, key=lambda item: item[:-1])[-1]


def handle_target_click(target_manager, candidates, x: float, y: float):
    """Manually lock the face candidate under a click point."""
    selected = find_candidate_at_point(candidates, x, y)
    if selected is None:
        return None
    return target_manager.manual_lock(selected, candidates)


def handle_target_key(key, target_manager, candidates):
    """Apply a target-control key without depending on OpenCV."""
    normalized_key = _normalize_target_key(key)
    if normalized_key == "q":
        return "quit"
    if normalized_key in {"u", "a"}:
        target_manager.manual_unlock()
        return "auto"
    if normalized_key == "l":
        current = target_manager.get_locked_target()
        if current is None:
            return None
        target_manager.manual_lock(current, candidates)
        return "locked"
    if normalized_key == "n":
        selected = target_manager.cycle_next_candidate(candidates)
        return "next" if selected is not None else None
    if normalized_key == "p":
        selected = target_manager.cycle_previous_candidate(candidates)
        return "previous" if selected is not None else None
    return None


def _draw_target_candidates(frame, debug_info: dict, cv2) -> None:
    candidates = debug_info.get("target_candidates", ())
    if not hasattr(cv2, "rectangle") or not hasattr(cv2, "putText"):
        return

    font = getattr(cv2, "FONT_HERSHEY_SIMPLEX", 0)
    for index, candidate in enumerate(candidates):
        try:
            normalized = normalize_candidate(candidate)
        except (TypeError, ValueError):
            continue
        x, y, width, height = (
            int(round(float(value))) for value in normalized.bbox
        )
        cv2.rectangle(
            frame,
            (x, y),
            (x + width, y + height),
            (255, 160, 0),
            1,
        )
        label = (
            normalized.candidate_id
            if normalized.candidate_id is not None
            else normalized.raw_backend_index
        )
        cv2.putText(
            frame,
            f"candidate {label if label is not None else index}",
            (x, max(18, y - 6)),
            font,
            0.5,
            (255, 160, 0),
            1,
        )


def _draw_locked_target_bbox(frame, debug_info: dict, cv2) -> None:
    bbox = debug_info.get("target_bbox")
    if (
        not debug_info.get("target_visible")
        or not isinstance(bbox, (tuple, list))
        or len(bbox) != 4
        or not hasattr(cv2, "rectangle")
    ):
        return

    x, y, width, height = (int(round(float(value))) for value in bbox)
    is_manual = debug_info.get("target_mode") == "manual"
    color = (255, 0, 255) if is_manual else (0, 255, 255)
    cv2.rectangle(
        frame,
        (x, y),
        (x + width, y + height),
        color,
        3,
    )
    if hasattr(cv2, "putText"):
        cv2.putText(
            frame,
            "MANUAL TARGET" if is_manual else "AUTO TARGET",
            (x, max(18, y - 24)),
            getattr(cv2, "FONT_HERSHEY_SIMPLEX", 0),
            0.55,
            color,
            2,
        )


def process_frame_with_optional_backend(
    frame,
    extractor,
    recognizer,
    smoother,
    backend=None,
    model_path: str | None = None,
    expression_classifier=None,
    recognizer_mode: str | None = None,
    compare_recognizers: bool = False,
    prefer_classifier: bool = False,
    target_lock_manager=None,
) -> dict:
    """Extract frame features and run recognition/smoothing."""
    active_backend = backend or _build_default_feature_backend(model_path)
    frame_width, frame_height = _frame_dimensions(frame)
    active_target_lock = target_lock_manager or TargetLockManager(
        frame_width=frame_width,
        frame_height=frame_height,
    )
    active_target_lock.set_frame_size(frame_width, frame_height)
    candidates = _extract_backend_candidates(
        active_backend,
        frame,
        frame_width,
        frame_height,
    )
    locked_target = active_target_lock.update(candidates)
    active_compare = compare_recognizers or recognizer_mode == "compare"
    active_mode = recognizer_mode or _recognizer_mode(
        active_compare,
        expression_classifier,
    )

    if locked_target is None:
        return _no_target_debug_info(
            extractor=extractor,
            target_lock_manager=active_target_lock,
            recognizer_mode=active_mode,
            classifier_available=expression_classifier is not None,
            candidates=candidates,
        )

    extracted_features = extractor.extract_from_scores(locked_target.features)
    if active_compare:
        rule_expression = recognizer.recognize(extracted_features)
        classifier_available = expression_classifier is not None
        classifier_expression = (
            expression_classifier.predict(extracted_features)
            if classifier_available
            else keys.EXPR_UNKNOWN
        )
        final_expression = select_final_expression(
            rule_expression=rule_expression,
            classifier_expression=classifier_expression,
            classifier_available=classifier_available,
            prefer_classifier=prefer_classifier,
        )
        smoothed_expression = smoother.update(final_expression)
        target_debug = active_target_lock.debug_info(target_visible=True)
        debug_info = build_recognition_debug_info(
            recognizer_mode=active_mode,
            rule_expression=rule_expression,
            classifier_expression=classifier_expression,
            final_expression=final_expression,
            smoothed_expression=smoothed_expression,
            classifier_available=classifier_available,
            target_mode=target_debug["target_mode"],
            target_locked=target_debug["target_locked"],
            target_id=target_debug["target_id"],
            target_backend_index=target_debug["target_backend_index"],
            candidate_count=len(candidates),
        )
        debug_info["extracted_features"] = extracted_features
        _attach_target_debug_info(
            debug_info,
            active_target_lock,
            target_visible=True,
            candidates=candidates,
        )
        return debug_info

    raw_expression = _recognize_expression(
        extracted_features,
        recognizer,
        expression_classifier,
    )
    smoothed_expression = smoother.update(raw_expression)
    debug_info = {
        "recognizer_mode": active_mode,
        "extracted_features": extracted_features,
        "raw_expression": raw_expression,
        "smoothed_expression": smoothed_expression,
    }
    _attach_target_debug_info(
        debug_info,
        active_target_lock,
        target_visible=True,
        candidates=candidates,
    )
    return debug_info


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
    control_state = {"candidates": []}

    if hasattr(cv2, "namedWindow"):
        cv2.namedWindow(WINDOW_NAME)
    if hasattr(cv2, "setMouseCallback"):
        left_button_event = getattr(cv2, "EVENT_LBUTTONDOWN", 1)

        def _on_mouse(event, x, y, flags=None, param=None):
            if event == left_button_event:
                handle_target_click(
                    pipeline["target_lock_manager"],
                    control_state["candidates"],
                    x,
                    y,
                )

        cv2.setMouseCallback(WINDOW_NAME, _on_mouse)

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
                expression_classifier=pipeline["expression_classifier"],
                recognizer_mode=pipeline["recognizer_mode"],
                compare_recognizers=pipeline["compare_recognizers"],
                prefer_classifier=pipeline["prefer_classifier"],
                target_lock_manager=pipeline["target_lock_manager"],
            )
            control_state["candidates"] = debug_info.get(
                "target_candidates",
                [],
            )
            overlay_debug_info(frame, debug_info, cv2_module=cv2)
            cv2.imshow(WINDOW_NAME, frame)
            results.append(debug_info)

            key_result = handle_target_key(
                cv2.waitKey(1) & 0xFF,
                pipeline["target_lock_manager"],
                control_state["candidates"],
            )
            if key_result == "quit":
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
            max_num_faces=5,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def extract_scores(self, frame) -> dict:
        candidates = self.extract_candidates(frame)
        if not candidates:
            return _empty_scores()
        return candidates[0]["features"]

    def extract_candidates(self, frame) -> list[dict]:
        cv2 = _load_cv2()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._face_mesh.process(rgb_frame)

        if not result.multi_face_landmarks:
            return []

        frame_width, frame_height = _frame_dimensions(frame)
        return [
            _candidate_from_landmarks(
                face_landmarks.landmark,
                index,
                frame_width,
                frame_height,
            )
            for index, face_landmarks in enumerate(result.multi_face_landmarks)
        ]

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
        candidates = self.extract_candidates(frame)
        if not candidates:
            return _empty_scores()
        return candidates[0]["features"]

    def extract_candidates(self, frame) -> list[dict]:
        cv2 = _load_cv2()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._landmarker.detect(self._create_image(rgb_frame))
        frame_width, frame_height = _frame_dimensions(frame)
        return _candidates_from_tasks_result(
            result,
            frame_width,
            frame_height,
        )

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


def _recognize_expression(
    extracted_features: dict,
    recognizer,
    expression_classifier=None,
) -> str:
    if expression_classifier is not None:
        return expression_classifier.predict(extracted_features)
    return recognizer.recognize(extracted_features)


def _recognizer_mode(compare_recognizers: bool, expression_classifier=None) -> str:
    if compare_recognizers:
        return "compare"
    if expression_classifier is not None:
        return "classifier"
    return "rule"


def _extract_backend_candidates(
    backend,
    frame,
    frame_width: float,
    frame_height: float,
) -> list:
    extract_candidates = getattr(backend, "extract_candidates", None)
    if callable(extract_candidates):
        candidates = extract_candidates(frame)
        return list(candidates or ())

    scores = backend.extract_scores(frame)
    if not isinstance(scores, dict) or not scores:
        return []
    confidence = scores.get("face_confidence", 1.0)
    return [
        {
            "candidate_id": 0,
            "bbox": (
                frame_width * 0.25,
                frame_height * 0.25,
                frame_width * 0.5,
                frame_height * 0.5,
            ),
            "confidence": confidence,
            "features": scores,
            "raw_backend_index": 0,
        }
    ]


def _no_target_debug_info(
    extractor,
    target_lock_manager,
    recognizer_mode: str,
    classifier_available: bool,
    candidates,
) -> dict:
    target_debug = target_lock_manager.debug_info(target_visible=False)
    if recognizer_mode == "compare":
        debug_info = build_recognition_debug_info(
            recognizer_mode=recognizer_mode,
            rule_expression=keys.EXPR_UNKNOWN,
            classifier_expression=keys.EXPR_UNKNOWN,
            final_expression=keys.EXPR_UNKNOWN,
            smoothed_expression=keys.EXPR_UNKNOWN,
            classifier_available=classifier_available,
            target_mode=target_debug["target_mode"],
            target_locked=target_debug["target_locked"],
            target_id=target_debug["target_id"],
            target_backend_index=target_debug["target_backend_index"],
            candidate_count=len(list(candidates or ())),
        )
    else:
        debug_info = {
            "recognizer_mode": recognizer_mode,
            "raw_expression": keys.EXPR_UNKNOWN,
            "smoothed_expression": keys.EXPR_UNKNOWN,
        }
    debug_info["extracted_features"] = extractor.extract_from_scores(
        _empty_scores()
    )
    _attach_target_debug_info(
        debug_info,
        target_lock_manager,
        target_visible=False,
        candidates=candidates,
    )
    return debug_info


def _attach_target_debug_info(
    debug_info: dict,
    target_lock_manager,
    target_visible: bool,
    candidates,
) -> None:
    debug_info.update(
        target_lock_manager.debug_info(target_visible=target_visible)
    )
    debug_info["target_candidates"] = list(candidates or ())
    debug_info["target_candidate_count"] = len(
        debug_info["target_candidates"]
    )
    debug_info["candidate_count"] = debug_info["target_candidate_count"]


def _candidates_from_tasks_result(
    result,
    frame_width: float,
    frame_height: float,
) -> list[dict]:
    if result is None:
        return []

    face_landmarks = list(getattr(result, "face_landmarks", None) or ())
    face_blendshapes = list(
        getattr(result, "face_blendshapes", None) or ()
    )
    face_count = max(len(face_landmarks), len(face_blendshapes))
    candidates = []

    for index in range(face_count):
        landmarks = (
            face_landmarks[index] if index < len(face_landmarks) else None
        )
        blendshapes = (
            face_blendshapes[index]
            if index < len(face_blendshapes)
            else None
        )
        features = (
            _scores_from_blendshapes([blendshapes])
            if blendshapes is not None
            else None
        )
        if features is None:
            features = (
                _scores_from_landmarks(landmarks)
                if landmarks
                else _empty_scores()
            )

        bbox = (
            _bbox_from_landmarks(
                landmarks,
                frame_width,
                frame_height,
            )
            if landmarks
            else _fallback_candidate_bbox(
                index,
                face_count,
                frame_width,
                frame_height,
            )
        )
        candidates.append(
            {
                "candidate_id": index,
                "bbox": bbox,
                "confidence": features.get("face_confidence", 0.0),
                "features": features,
                "raw_backend_index": index,
            }
        )

    return candidates


def _candidate_from_landmarks(
    landmarks,
    index: int,
    frame_width: float,
    frame_height: float,
) -> dict:
    features = _scores_from_landmarks(landmarks)
    return {
        "candidate_id": index,
        "bbox": _bbox_from_landmarks(
            landmarks,
            frame_width,
            frame_height,
        ),
        "confidence": features.get("face_confidence", 0.0),
        "features": features,
        "raw_backend_index": index,
    }


def _bbox_from_landmarks(
    landmarks,
    frame_width: float,
    frame_height: float,
) -> tuple[float, float, float, float]:
    points = []
    for landmark in landmarks or ():
        try:
            x = _clamp(float(landmark.x)) * frame_width
            y = _clamp(float(landmark.y)) * frame_height
        except (AttributeError, TypeError, ValueError):
            continue
        points.append((x, y))

    if not points:
        return _fallback_candidate_bbox(
            0,
            1,
            frame_width,
            frame_height,
        )

    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    return min_x, min_y, max_x - min_x, max_y - min_y


def _fallback_candidate_bbox(
    index: int,
    count: int,
    frame_width: float,
    frame_height: float,
) -> tuple[float, float, float, float]:
    safe_count = max(1, count)
    box_width = frame_width / safe_count
    return (
        index * box_width,
        frame_height * 0.25,
        box_width,
        frame_height * 0.5,
    )


def _frame_dimensions(frame) -> tuple[float, float]:
    shape = getattr(frame, "shape", None)
    if shape is not None and len(shape) >= 2:
        try:
            height = float(shape[0])
            width = float(shape[1])
        except (TypeError, ValueError):
            pass
        else:
            if width > 0.0 and height > 0.0:
                return width, height
    return 640.0, 480.0


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
    target_mode = debug_info.get("target_mode", "auto")
    candidate_count = debug_info.get(
        "candidate_count",
        debug_info.get("target_candidate_count", 0),
    )
    target_locked = bool(debug_info.get("target_locked"))
    target_visible = bool(debug_info.get("target_visible"))
    if target_mode == "manual-lost":
        target_status = "manual target lost"
    elif target_visible:
        target_status = "tracking"
    elif target_locked:
        target_status = "locked target missing"
    else:
        target_status = "no locked target"

    lines = [
        f"target_mode: {target_mode}",
        f"target_locked: {_yes_no(target_locked)}",
        f"target_status: {target_status}",
        f"target_id: {debug_info.get('target_id')}",
        "target_confidence: "
        f"{_format_score(debug_info.get('target_confidence'))}",
        f"target_bbox: {_format_bbox(debug_info.get('target_bbox'))}",
        f"lost_frames: {debug_info.get('lost_frames', 0)}",
        f"candidate_count: {candidate_count}",
        "controls: q quit | u unlock | n/p cycle | l lock | a auto",
        "click face to lock target",
        f"recognizer_mode: {debug_info.get('recognizer_mode', 'rule')}",
    ]
    if debug_info.get("recognizer_mode") == "compare":
        lines.extend(
            [
                f"rule_expression: {debug_info.get('rule_expression')}",
                f"classifier_expression: {debug_info.get('classifier_expression')}",
                f"final_expression: {debug_info.get('final_expression')}",
                f"smoothed_expression: {debug_info.get('smoothed_expression')}",
                "recognizers_disagree: "
                f"{_yes_no(debug_info.get('recognizers_disagree'))}",
            ]
        )
    else:
        lines.extend(
            [
                f"raw_expression: {debug_info.get('raw_expression')}",
                f"smoothed_expression: {debug_info.get('smoothed_expression')}",
            ]
        )
    lines.extend(
        [
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
    )
    return lines


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


def _normalize_target_key(key) -> str:
    if isinstance(key, str):
        return key.strip().lower()[:1]
    if isinstance(key, int) and 0 <= key <= 255:
        return chr(key).lower()
    return ""


def _format_bbox(bbox) -> str:
    if not isinstance(bbox, (tuple, list)) or len(bbox) != 4:
        return "none"
    try:
        return ",".join(str(int(round(float(value)))) for value in bbox)
    except (TypeError, ValueError):
        return "none"


def _yes_no(value) -> str:
    return "yes" if bool(value) else "no"


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

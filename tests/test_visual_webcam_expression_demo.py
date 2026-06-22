import importlib
import sys
from types import SimpleNamespace

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.demos import visual_webcam_expression_demo as visual_demo


@pytest.fixture(autouse=True)
def clear_expression_classifier_env(monkeypatch):
    monkeypatch.delenv(
        visual_demo.EXPRESSION_CLASSIFIER_MODEL_ENV_VAR,
        raising=False,
    )


class FakeCv2:
    FONT_HERSHEY_SIMPLEX = 1

    def __init__(self):
        self.text_calls = []

    def putText(self, frame, text, position, font, scale, color, thickness):
        self.text_calls.append(
            {
                "frame": frame,
                "text": text,
                "position": position,
                "font": font,
                "scale": scale,
                "color": color,
                "thickness": thickness,
            }
        )
        return frame


class FakeBackend:
    def __init__(self, scores):
        self.scores = scores
        self.frames = []

    def extract_scores(self, frame):
        self.frames.append(frame)
        return self.scores


class FakeClassifier:
    def __init__(self, prediction):
        self.prediction = prediction
        self.features = []

    def predict(self, features):
        self.features.append(features)
        return self.prediction


class FakeRecognizer:
    def __init__(self, expression):
        self.expression = expression
        self.features = []

    def recognize(self, features):
        self.features.append(features)
        return self.expression


class FakeSmoother:
    def __init__(self):
        self.expressions = []

    def update(self, expression):
        self.expressions.append(expression)
        return expression


class FakeFaceMeshModule:
    class FaceMesh:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


class FakeBaseOptions:
    def __init__(self, model_asset_path):
        self.model_asset_path = model_asset_path


class FakeFaceLandmarkerOptions:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeRunningMode:
    IMAGE = "IMAGE"


class FakeFaceLandmarker:
    created_options = None

    @classmethod
    def create_from_options(cls, options):
        cls.created_options = options
        return cls()

    def detect(self, image):
        return SimpleNamespace(face_blendshapes=[], face_landmarks=[])


class FakeImage:
    def __init__(self, image_format, data):
        self.image_format = image_format
        self.data = data


class FakeImageFormat:
    SRGB = "SRGB"


def test_importing_visual_demo_requires_no_optional_runtime():
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

    sys.modules.pop("ivastbot_hri.demos.visual_webcam_expression_demo", None)
    module = importlib.import_module(
        "ivastbot_hri.demos.visual_webcam_expression_demo"
    )

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.run_visual_webcam_demo is not None
    assert after == before


def test_build_visual_expression_pipeline_returns_usable_components():
    pipeline = visual_demo.build_visual_expression_pipeline()

    assert pipeline["feature_extractor"].extract_from_scores({"smile_score": 0.9})
    assert pipeline["recognizer"].recognize(
        {"smile_score": 0.9, "face_confidence": 1.0}
    ) == keys.EXPR_HAPPY
    assert pipeline["expression_classifier"] is None
    assert pipeline["recognizer_mode"] == "rule"
    assert pipeline["smoother"].current() == keys.EXPR_UNKNOWN


def test_load_optional_expression_classifier_returns_none_when_env_missing(monkeypatch):
    monkeypatch.delenv(
        visual_demo.EXPRESSION_CLASSIFIER_MODEL_ENV_VAR,
        raising=False,
    )

    assert visual_demo.load_optional_expression_classifier() is None


def test_load_optional_expression_classifier_uses_loader_when_env_is_set(monkeypatch):
    classifier = FakeClassifier(keys.EXPR_HAPPY)
    loaded_paths = []

    def fake_loader(model_path):
        loaded_paths.append(model_path)
        return classifier

    monkeypatch.setenv(
        visual_demo.EXPRESSION_CLASSIFIER_MODEL_ENV_VAR,
        "F:\\models\\expression_classifier.json",
    )

    assert visual_demo.load_optional_expression_classifier(loader=fake_loader) is (
        classifier
    )
    assert loaded_paths == ["F:\\models\\expression_classifier.json"]


def test_load_optional_expression_classifier_invalid_path_raises_runtime_error(
    monkeypatch,
    tmp_path,
):
    missing_path = tmp_path / "missing_classifier.json"
    monkeypatch.setenv(
        visual_demo.EXPRESSION_CLASSIFIER_MODEL_ENV_VAR,
        str(missing_path),
    )

    with pytest.raises(
        RuntimeError,
        match=visual_demo.EXPRESSION_CLASSIFIER_LOAD_ERROR_MESSAGE,
    ) as error_info:
        visual_demo.load_optional_expression_classifier()

    assert isinstance(error_info.value.__cause__, FileNotFoundError)


def test_overlay_debug_info_writes_expected_lines_with_fake_cv2():
    fake_cv2 = FakeCv2()
    frame = {"fake": "frame"}
    debug_info = {
        "recognizer_mode": "classifier",
        "raw_expression": keys.EXPR_HAPPY,
        "smoothed_expression": keys.EXPR_HAPPY,
        "extracted_features": {
            "smile_score": 0.9,
            "mouth_open_score": 0.2,
            "eyebrow_raise_score": 0.1,
            "eye_open_score": 0.8,
            "brow_down_score": 0.3,
            "eye_squint_score": 0.4,
            "mouth_press_score": 0.5,
            "face_confidence": 0.95,
        },
    }

    returned_frame = visual_demo.overlay_debug_info(
        frame,
        debug_info,
        cv2_module=fake_cv2,
    )

    assert returned_frame is frame
    texts = [call["text"] for call in fake_cv2.text_calls]
    assert "recognizer_mode: classifier" in texts
    assert "raw_expression: EXPR_HAPPY" in texts
    assert "smoothed_expression: EXPR_HAPPY" in texts
    assert "smile_score: 0.90" in texts
    assert "mouth_open_score: 0.20" in texts
    assert "eyebrow_raise_score: 0.10" in texts
    assert "eye_open_score: 0.80" in texts
    assert "brow_down_score: 0.30" in texts
    assert "eye_squint_score: 0.40" in texts
    assert "mouth_press_score: 0.50" in texts
    assert "face_confidence: 0.95" in texts
    assert "press q to quit" in texts


def test_process_frame_with_fake_backend_returns_debug_info():
    pipeline = visual_demo.build_visual_expression_pipeline()
    backend = FakeBackend({"smile_score": 0.95, "face_confidence": 0.95})

    first_result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "frame"},
        extractor=pipeline["feature_extractor"],
        recognizer=pipeline["recognizer"],
        smoother=pipeline["smoother"],
        backend=backend,
    )
    second_result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "second_frame"},
        extractor=pipeline["feature_extractor"],
        recognizer=pipeline["recognizer"],
        smoother=pipeline["smoother"],
        backend=backend,
    )

    assert first_result["extracted_features"]["smile_score"] == 0.95
    assert first_result["recognizer_mode"] == "rule"
    assert first_result["raw_expression"] == keys.EXPR_HAPPY
    assert first_result["smoothed_expression"] == keys.EXPR_UNKNOWN
    assert second_result["smoothed_expression"] == keys.EXPR_HAPPY
    assert backend.frames == [{"fake": "frame"}, {"fake": "second_frame"}]


def test_process_frame_uses_rule_recognizer_when_classifier_is_absent():
    backend = FakeBackend({"smile_score": 0.9, "face_confidence": 0.95})
    recognizer = FakeRecognizer(keys.EXPR_HAPPY)
    smoother = FakeSmoother()
    extractor = visual_demo.FaceFeatureExtractor()

    result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "frame"},
        extractor=extractor,
        recognizer=recognizer,
        smoother=smoother,
        backend=backend,
    )

    assert result["recognizer_mode"] == "rule"
    assert result["raw_expression"] == keys.EXPR_HAPPY
    assert recognizer.features == [result["extracted_features"]]
    assert smoother.expressions == [keys.EXPR_HAPPY]


def test_process_frame_uses_classifier_prediction_when_classifier_exists():
    backend = FakeBackend({"smile_score": 0.9, "face_confidence": 0.95})
    recognizer = FakeRecognizer(keys.EXPR_HAPPY)
    classifier = FakeClassifier(keys.EXPR_ANGRY)
    smoother = FakeSmoother()
    extractor = visual_demo.FaceFeatureExtractor()

    result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "frame"},
        extractor=extractor,
        recognizer=recognizer,
        smoother=smoother,
        backend=backend,
        expression_classifier=classifier,
    )

    assert result["recognizer_mode"] == "classifier"
    assert result["raw_expression"] == keys.EXPR_ANGRY
    assert classifier.features == [result["extracted_features"]]
    assert recognizer.features == []
    assert smoother.expressions == [keys.EXPR_ANGRY]


def test_process_frame_with_missing_mediapipe_backend_raises_clear_error(
    monkeypatch,
):
    pipeline = visual_demo.build_visual_expression_pipeline()
    real_import_module = importlib.import_module

    def fake_import_module(name, package=None):
        if name == "mediapipe":
            raise ImportError("MediaPipe is not installed")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match=visual_demo.MEDIAPIPE_UNAVAILABLE_MESSAGE):
        visual_demo.process_frame_with_optional_backend(
            frame=object(),
            extractor=pipeline["feature_extractor"],
            recognizer=pipeline["recognizer"],
            smoother=pipeline["smoother"],
        )


def test_mediapipe_backend_raises_runtime_error_for_missing_facemesh_api(
    monkeypatch,
):
    fake_mediapipe = SimpleNamespace()

    def fake_import_module(name, package=None):
        if name == "mediapipe":
            return fake_mediapipe
        if name == "mediapipe.python.solutions.face_mesh":
            raise ImportError("legacy FaceMesh is unavailable")
        return importlib.import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(
        RuntimeError,
        match="legacy FaceMesh Solutions API",
    ) as error_info:
        visual_demo.MediaPipeFaceFeatureBackend()

    assert isinstance(error_info.value.__cause__, ImportError)
    assert "MediaPipe Tasks backend" in str(error_info.value)


def test_default_backend_requires_tasks_model_when_legacy_facemesh_is_unavailable(
    monkeypatch,
):
    fake_mediapipe = SimpleNamespace()

    def fake_import_module(name, package=None):
        if name == "mediapipe":
            return fake_mediapipe
        if name == "mediapipe.python.solutions.face_mesh":
            raise ImportError("legacy FaceMesh is unavailable")
        return importlib.import_module(name, package)

    monkeypatch.delenv(visual_demo.FACE_LANDMARKER_MODEL_ENV_VAR, raising=False)
    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(
        RuntimeError,
        match="MediaPipe Tasks FaceLandmarker requires a .task model file",
    ):
        visual_demo._build_default_feature_backend()


def test_load_mediapipe_face_mesh_uses_mediapipe_solutions(monkeypatch):
    fake_mediapipe = SimpleNamespace(
        solutions=SimpleNamespace(face_mesh=FakeFaceMeshModule)
    )

    def fake_import_module(name, package=None):
        if name == "mediapipe":
            return fake_mediapipe
        raise AssertionError(f"Unexpected import: {name}")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert visual_demo._load_mediapipe_face_mesh() is FakeFaceMeshModule


def test_load_mediapipe_face_mesh_uses_legacy_import_fallback(monkeypatch):
    fake_mediapipe = SimpleNamespace()

    def fake_import_module(name, package=None):
        if name == "mediapipe":
            return fake_mediapipe
        if name == "mediapipe.python.solutions.face_mesh":
            return FakeFaceMeshModule
        raise AssertionError(f"Unexpected import: {name}")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert visual_demo._load_mediapipe_face_mesh() is FakeFaceMeshModule


def test_default_backend_reads_tasks_model_path_from_environment(monkeypatch):
    fake_mediapipe, fake_vision = _fake_tasks_modules()

    def fake_import_module(name, package=None):
        if name == "mediapipe":
            return fake_mediapipe
        if name == "mediapipe.python.solutions.face_mesh":
            raise ImportError("legacy FaceMesh is unavailable")
        if name == "mediapipe.tasks.python.vision":
            return fake_vision
        raise AssertionError(f"Unexpected import: {name}")

    monkeypatch.setenv(
        visual_demo.FACE_LANDMARKER_MODEL_ENV_VAR,
        "F:\\models\\face_landmarker.task",
    )
    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    backend = visual_demo._build_default_feature_backend()

    assert isinstance(backend, visual_demo.MediaPipeTasksFaceLandmarkerBackend)
    assert backend.model_path == "F:\\models\\face_landmarker.task"
    assert (
        FakeFaceLandmarker.created_options.kwargs["base_options"].model_asset_path
        == "F:\\models\\face_landmarker.task"
    )


def test_tasks_backend_can_be_constructed_with_fake_mediapipe_modules(
    monkeypatch,
):
    fake_mediapipe, fake_vision = _fake_tasks_modules()

    def fake_import_module(name, package=None):
        if name == "mediapipe":
            return fake_mediapipe
        if name == "mediapipe.tasks.python.vision":
            return fake_vision
        raise AssertionError(f"Unexpected import: {name}")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    backend = visual_demo.MediaPipeTasksFaceLandmarkerBackend(
        model_path="face_landmarker.task"
    )

    assert backend.model_path == "face_landmarker.task"
    assert (
        FakeFaceLandmarker.created_options.kwargs["running_mode"]
        == FakeRunningMode.IMAGE
    )
    assert FakeFaceLandmarker.created_options.kwargs["output_face_blendshapes"] is True


def test_tasks_blendshape_result_maps_to_expression_feature_scores():
    result = SimpleNamespace(
        face_blendshapes=[
            [
                SimpleNamespace(category_name="mouthSmileLeft", score=0.7),
                SimpleNamespace(category_name="mouthSmileRight", score=0.5),
                SimpleNamespace(category_name="jawOpen", score=0.4),
                SimpleNamespace(category_name="eyeBlinkLeft", score=0.2),
                SimpleNamespace(category_name="eyeBlinkRight", score=0.4),
                SimpleNamespace(category_name="browOuterUpLeft", score=0.6),
                SimpleNamespace(category_name="browOuterUpRight", score=0.2),
                SimpleNamespace(category_name="browDownLeft", score=0.8),
                SimpleNamespace(category_name="eyeSquintRight", score=0.7),
                SimpleNamespace(category_name="mouthPressLeft", score=0.55),
            ]
        ],
        face_landmarks=[],
    )

    scores = visual_demo._scores_from_tasks_result(result)

    assert set(scores) == {
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
    assert scores["smile_score"] == 0.7
    assert scores["mouth_open_score"] == 0.4
    assert scores["eye_open_score"] == pytest.approx(0.7)
    assert scores["eyebrow_raise_score"] == 0.6
    assert scores["brow_down_score"] == 0.8
    assert scores["eye_squint_score"] == 0.7
    assert scores["mouth_press_score"] == 0.55
    assert scores["face_confidence"] == 1.0


def test_tasks_blendshape_scores_are_clamped_and_missing_values_are_safe():
    result = SimpleNamespace(
        face_blendshapes=[
            [
                SimpleNamespace(category_name="mouthSmileLeft", score=1.5),
                SimpleNamespace(category_name="jawOpen", score=-0.5),
                SimpleNamespace(category_name="eyeBlinkLeft", score=2.0),
                SimpleNamespace(category_name="browDownLeft", score=2.0),
                SimpleNamespace(category_name="eyeSquintLeft", score=-1.0),
                SimpleNamespace(category_name="mouthPressLeft", score=2.0),
            ]
        ],
        face_landmarks=[],
    )

    scores = visual_demo._scores_from_tasks_result(result)

    assert scores == {
        "smile_score": 1.0,
        "eye_open_score": 0.0,
        "eyebrow_raise_score": 0.0,
        "mouth_open_score": 0.0,
        "brow_down_score": 1.0,
        "eye_squint_score": 0.0,
        "mouth_press_score": 1.0,
        "gaze_away_score": 0.0,
        "low_activity_score": 0.0,
        "face_confidence": 1.0,
    }


def test_run_visual_webcam_demo_fails_gracefully_if_cv2_is_unavailable(
    monkeypatch,
):
    real_import_module = importlib.import_module

    def fake_import_module(name, package=None):
        if name == "cv2":
            raise ImportError("OpenCV is not installed")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match=visual_demo.OPENCV_UNAVAILABLE_MESSAGE):
        visual_demo.run_visual_webcam_demo(max_frames=1)


def test_run_visual_webcam_demo_does_not_run_on_import(monkeypatch):
    def fail_if_cv2_or_mediapipe_loads(name, package=None):
        if name in {"cv2", "mediapipe"}:
            raise AssertionError(f"{name} should not load during import")
        return importlib.import_module(name, package)

    monkeypatch.delenv(
        visual_demo.EXPRESSION_CLASSIFIER_MODEL_ENV_VAR,
        raising=False,
    )
    monkeypatch.setattr(importlib, "import_module", fail_if_cv2_or_mediapipe_loads)

    pipeline = visual_demo.build_visual_expression_pipeline()

    assert pipeline["smoother"].current() == keys.EXPR_UNKNOWN


def _fake_tasks_modules():
    FakeFaceLandmarker.created_options = None
    fake_mediapipe = SimpleNamespace(
        tasks=SimpleNamespace(BaseOptions=FakeBaseOptions),
        Image=FakeImage,
        ImageFormat=FakeImageFormat,
    )
    fake_vision = SimpleNamespace(
        FaceLandmarker=FakeFaceLandmarker,
        FaceLandmarkerOptions=FakeFaceLandmarkerOptions,
        RunningMode=FakeRunningMode,
    )
    return fake_mediapipe, fake_vision

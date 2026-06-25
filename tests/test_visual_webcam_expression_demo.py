import importlib
import sys
from types import SimpleNamespace

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.core.target_lock import TargetLockManager
from ivastbot_hri.demos import visual_webcam_expression_demo as visual_demo


@pytest.fixture(autouse=True)
def clear_expression_classifier_env(monkeypatch):
    monkeypatch.delenv(
        visual_demo.EXPRESSION_CLASSIFIER_MODEL_ENV_VAR,
        raising=False,
    )
    monkeypatch.delenv(
        visual_demo.COMPARE_RECOGNIZERS_ENV_VAR,
        raising=False,
    )
    monkeypatch.delenv(
        visual_demo.PREFER_CLASSIFIER_ENV_VAR,
        raising=False,
    )


class FakeCv2:
    FONT_HERSHEY_SIMPLEX = 1

    def __init__(self):
        self.text_calls = []
        self.rectangle_calls = []

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

    def rectangle(self, frame, start, end, color, thickness):
        self.rectangle_calls.append(
            {
                "frame": frame,
                "start": start,
                "end": end,
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


class FakeCandidateBackend:
    def __init__(self, candidates):
        self.candidates = candidates
        self.frames = []

    def extract_candidates(self, frame):
        self.frames.append(frame)
        return self.candidates


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


def test_importing_visual_demo_does_not_load_classifier_from_environment(
    monkeypatch,
    tmp_path,
):
    missing_model = tmp_path / "missing_classifier.json"
    monkeypatch.setenv(
        visual_demo.EXPRESSION_CLASSIFIER_MODEL_ENV_VAR,
        str(missing_model),
    )

    sys.modules.pop("ivastbot_hri.demos.visual_webcam_expression_demo", None)
    module = importlib.import_module(
        "ivastbot_hri.demos.visual_webcam_expression_demo"
    )

    assert module.load_optional_expression_classifier is not None
    assert not missing_model.exists()


def test_build_visual_expression_pipeline_returns_usable_components():
    pipeline = visual_demo.build_visual_expression_pipeline()

    assert pipeline["feature_extractor"].extract_from_scores({"smile_score": 0.9})
    assert pipeline["recognizer"].recognize(
        {"smile_score": 0.9, "face_confidence": 1.0}
    ) == keys.EXPR_HAPPY
    assert pipeline["expression_classifier"] is None
    assert pipeline["compare_recognizers"] is False
    assert pipeline["prefer_classifier"] is False
    assert pipeline["recognizer_mode"] == "rule"
    assert pipeline["smoother"].current() == keys.EXPR_UNKNOWN
    assert isinstance(pipeline["target_lock_manager"], TargetLockManager)


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", " TRUE "])
def test_compare_recognizers_env_true_values_enable_comparison(monkeypatch, value):
    monkeypatch.setenv(visual_demo.COMPARE_RECOGNIZERS_ENV_VAR, value)

    assert visual_demo.is_env_flag_enabled(visual_demo.COMPARE_RECOGNIZERS_ENV_VAR)
    assert visual_demo.build_visual_expression_pipeline()["recognizer_mode"] == (
        "compare"
    )


def test_compare_recognizers_env_false_by_default(monkeypatch):
    monkeypatch.delenv(visual_demo.COMPARE_RECOGNIZERS_ENV_VAR, raising=False)
    assert not visual_demo.is_env_flag_enabled(visual_demo.COMPARE_RECOGNIZERS_ENV_VAR)

    monkeypatch.setenv(visual_demo.COMPARE_RECOGNIZERS_ENV_VAR, "false")
    assert not visual_demo.is_env_flag_enabled(visual_demo.COMPARE_RECOGNIZERS_ENV_VAR)


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", " YES "])
def test_prefer_classifier_env_true_values_enable_preference(monkeypatch, value):
    monkeypatch.setenv(visual_demo.PREFER_CLASSIFIER_ENV_VAR, value)

    assert visual_demo.is_env_flag_enabled(visual_demo.PREFER_CLASSIFIER_ENV_VAR)
    assert visual_demo.build_visual_expression_pipeline()["prefer_classifier"] is True


def test_select_final_expression_uses_rule_when_classifier_unavailable():
    assert visual_demo.select_final_expression(
        rule_expression=keys.EXPR_HAPPY,
        classifier_expression=keys.EXPR_ANGRY,
        classifier_available=False,
    ) == keys.EXPR_HAPPY


def test_select_final_expression_uses_rule_when_preference_is_false():
    assert visual_demo.select_final_expression(
        rule_expression=keys.EXPR_HAPPY,
        classifier_expression=keys.EXPR_ANGRY,
        classifier_available=True,
        prefer_classifier=False,
    ) == keys.EXPR_HAPPY


def test_select_final_expression_prefers_classifier_when_enabled():
    assert visual_demo.select_final_expression(
        rule_expression=keys.EXPR_HAPPY,
        classifier_expression=keys.EXPR_ANGRY,
        classifier_available=True,
        prefer_classifier=True,
    ) == keys.EXPR_ANGRY


def test_select_final_expression_does_not_prefer_unknown_classifier():
    assert visual_demo.select_final_expression(
        rule_expression=keys.EXPR_HAPPY,
        classifier_expression=keys.EXPR_UNKNOWN,
        classifier_available=True,
        prefer_classifier=True,
    ) == keys.EXPR_HAPPY


def test_select_final_expression_uses_classifier_when_rule_is_unknown():
    assert visual_demo.select_final_expression(
        rule_expression=keys.EXPR_UNKNOWN,
        classifier_expression=keys.EXPR_BORED,
        classifier_available=True,
        prefer_classifier=False,
    ) == keys.EXPR_BORED


def test_build_recognition_debug_info_contains_comparison_fields():
    debug_info = visual_demo.build_recognition_debug_info(
        recognizer_mode="compare",
        rule_expression=keys.EXPR_HAPPY,
        classifier_expression=keys.EXPR_ANGRY,
        final_expression=keys.EXPR_HAPPY,
        smoothed_expression=keys.EXPR_HAPPY,
        classifier_available=True,
        target_mode="manual",
        target_locked=True,
        target_id="operator",
        target_backend_index=3,
        candidate_count=4,
    )

    assert debug_info["recognizer_mode"] == "compare"
    assert debug_info["target_mode"] == "manual"
    assert debug_info["target_locked"] is True
    assert debug_info["target_id"] == "operator"
    assert debug_info["target_backend_index"] == 3
    assert debug_info["candidate_count"] == 4
    assert debug_info["target_candidate_count"] == 4
    assert debug_info["rule_expression"] == keys.EXPR_HAPPY
    assert debug_info["classifier_expression"] == keys.EXPR_ANGRY
    assert debug_info["final_expression"] == keys.EXPR_HAPPY
    assert debug_info["raw_expression"] == keys.EXPR_HAPPY
    assert debug_info["smoothed_expression"] == keys.EXPR_HAPPY
    assert debug_info["classifier_available"] is True
    assert debug_info["recognizers_disagree"] is True


def test_build_recognition_debug_info_uses_backend_index_as_target_id_fallback():
    debug_info = visual_demo.build_recognition_debug_info(
        recognizer_mode="compare",
        rule_expression=keys.EXPR_HAPPY,
        classifier_expression=keys.EXPR_HAPPY,
        final_expression=keys.EXPR_HAPPY,
        smoothed_expression=keys.EXPR_HAPPY,
        classifier_available=True,
        target_mode="auto",
        target_locked=True,
        target_backend_index=5,
        candidate_count=2,
    )

    assert debug_info["target_id"] == 5
    assert debug_info["candidate_count"] == 2


def test_build_recognition_debug_info_reports_agreement():
    debug_info = visual_demo.build_recognition_debug_info(
        recognizer_mode="compare",
        rule_expression=keys.EXPR_HAPPY,
        classifier_expression=keys.EXPR_HAPPY,
        final_expression=keys.EXPR_HAPPY,
        smoothed_expression=keys.EXPR_HAPPY,
        classifier_available=True,
    )

    assert debug_info["recognizers_disagree"] is False


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
        "target_locked": True,
        "target_visible": True,
        "target_id": 2,
        "target_confidence": 0.95,
        "target_bbox": (100, 80, 200, 220),
        "lost_frames": 0,
        "target_candidate_count": 2,
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
    assert "target_locked: yes" in texts
    assert "target_status: tracking" in texts
    assert "target_id: 2" in texts
    assert "target_confidence: 0.95" in texts
    assert "target_bbox: 100,80,200,220" in texts
    assert "lost_frames: 0" in texts
    assert "target_mode: auto" in texts
    assert "candidate_count: 2" in texts
    assert (
        "controls: q quit | u unlock | n/p cycle | l lock | a auto"
        in texts
    )
    assert "press q to quit" in texts
    assert fake_cv2.rectangle_calls == [
        {
            "frame": frame,
            "start": (100, 80),
            "end": (300, 300),
            "color": (0, 255, 255),
            "thickness": 3,
        }
    ]


def test_comparison_overlay_writes_recognizer_comparison_lines():
    fake_cv2 = FakeCv2()
    frame = {"fake": "frame"}
    debug_info = {
        "recognizer_mode": "compare",
        "rule_expression": keys.EXPR_HAPPY,
        "classifier_expression": keys.EXPR_ANGRY,
        "final_expression": keys.EXPR_HAPPY,
        "smoothed_expression": keys.EXPR_HAPPY,
        "recognizers_disagree": True,
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

    visual_demo.overlay_debug_info(frame, debug_info, cv2_module=fake_cv2)

    texts = [call["text"] for call in fake_cv2.text_calls]
    assert "recognizer_mode: compare" in texts
    assert "rule_expression: EXPR_HAPPY" in texts
    assert "classifier_expression: EXPR_ANGRY" in texts
    assert "final_expression: EXPR_HAPPY" in texts
    assert "smoothed_expression: EXPR_HAPPY" in texts
    assert "recognizers_disagree: yes" in texts


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
    assert first_result["target_locked"] is True
    assert first_result["target_id"] == 0


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


def test_process_frame_comparison_mode_computes_both_recognizers():
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
        compare_recognizers=True,
    )

    assert result["recognizer_mode"] == "compare"
    assert result["rule_expression"] == keys.EXPR_HAPPY
    assert result["classifier_expression"] == keys.EXPR_ANGRY
    assert result["final_expression"] == keys.EXPR_HAPPY
    assert result["raw_expression"] == keys.EXPR_HAPPY
    assert result["smoothed_expression"] == keys.EXPR_HAPPY
    assert result["recognizers_disagree"] is True
    assert result["target_mode"] == "auto"
    assert result["target_locked"] is True
    assert result["target_id"] == 0
    assert result["candidate_count"] == 1
    assert recognizer.features == [result["extracted_features"]]
    assert classifier.features == [result["extracted_features"]]
    assert smoother.expressions == [keys.EXPR_HAPPY]


def test_process_frame_comparison_mode_can_prefer_classifier():
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
        compare_recognizers=True,
        prefer_classifier=True,
    )

    assert result["final_expression"] == keys.EXPR_ANGRY
    assert result["smoothed_expression"] == keys.EXPR_ANGRY
    assert smoother.expressions == [keys.EXPR_ANGRY]


def test_process_frame_comparison_mode_without_classifier_uses_rule():
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
        compare_recognizers=True,
    )

    assert result["recognizer_mode"] == "compare"
    assert result["classifier_expression"] == keys.EXPR_UNKNOWN
    assert result["classifier_available"] is False
    assert result["final_expression"] == keys.EXPR_HAPPY
    assert result["recognizers_disagree"] is False


def test_comparison_mode_uses_same_manually_locked_target_for_both_recognizers():
    candidates = [
        {
            "candidate_id": "background",
            "raw_backend_index": 0,
            "bbox": (260, 150, 120, 120),
            "confidence": 0.95,
            "features": {
                "smile_score": 0.95,
                "face_confidence": 0.95,
            },
        },
        {
            "candidate_id": "operator",
            "raw_backend_index": 1,
            "bbox": (20, 100, 120, 120),
            "confidence": 0.95,
            "features": {
                "smile_score": 0.1,
                "brow_down_score": 0.9,
                "face_confidence": 0.95,
            },
        },
    ]
    backend = FakeCandidateBackend(candidates)
    target_manager = TargetLockManager()
    target_manager.manual_lock("operator", candidates)
    recognizer = FakeRecognizer(keys.EXPR_ANGRY)
    classifier = FakeClassifier(keys.EXPR_CONFUSED)
    smoother = FakeSmoother()

    result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "frame"},
        extractor=visual_demo.FaceFeatureExtractor(),
        recognizer=recognizer,
        smoother=smoother,
        backend=backend,
        expression_classifier=classifier,
        compare_recognizers=True,
        target_lock_manager=target_manager,
    )

    assert result["target_mode"] == "manual"
    assert result["target_id"] == "operator"
    assert result["candidate_count"] == 2
    assert result["rule_expression"] == keys.EXPR_ANGRY
    assert result["classifier_expression"] == keys.EXPR_CONFUSED
    assert result["extracted_features"]["brow_down_score"] == 0.9
    assert result["extracted_features"]["smile_score"] == 0.1
    assert recognizer.features == [result["extracted_features"]]
    assert classifier.features == [result["extracted_features"]]
    assert all(
        features["smile_score"] != 0.95
        for features in recognizer.features + classifier.features
    )


def test_comparison_mode_without_locked_target_returns_unknown_debug_contract():
    backend = FakeCandidateBackend([])
    recognizer = FakeRecognizer(keys.EXPR_HAPPY)
    classifier = FakeClassifier(keys.EXPR_ANGRY)
    smoother = FakeSmoother()

    result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "frame"},
        extractor=visual_demo.FaceFeatureExtractor(),
        recognizer=recognizer,
        smoother=smoother,
        backend=backend,
        expression_classifier=classifier,
        compare_recognizers=True,
        target_lock_manager=TargetLockManager(),
    )

    assert result["recognizer_mode"] == "compare"
    assert result["target_mode"] == "auto"
    assert result["target_locked"] is False
    assert result["target_id"] is None
    assert result["candidate_count"] == 0
    assert result["rule_expression"] == keys.EXPR_UNKNOWN
    assert result["classifier_expression"] == keys.EXPR_UNKNOWN
    assert result["final_expression"] == keys.EXPR_UNKNOWN
    assert result["smoothed_expression"] == keys.EXPR_UNKNOWN
    assert result["recognizers_disagree"] is False
    assert recognizer.features == []
    assert classifier.features == []
    assert smoother.expressions == []


def test_process_frame_selects_centered_candidate_and_uses_only_its_features():
    backend = FakeCandidateBackend(
        [
            {
                "candidate_id": "left",
                "bbox": (20, 100, 120, 120),
                "confidence": 0.95,
                "features": {
                    "smile_score": 0.1,
                    "brow_down_score": 0.9,
                    "face_confidence": 0.95,
                },
            },
            {
                "candidate_id": "center",
                "bbox": (260, 150, 120, 120),
                "confidence": 0.95,
                "features": {
                    "smile_score": 0.9,
                    "face_confidence": 0.95,
                },
            },
        ]
    )
    recognizer = FakeRecognizer(keys.EXPR_HAPPY)
    smoother = FakeSmoother()

    result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "frame"},
        extractor=visual_demo.FaceFeatureExtractor(),
        recognizer=recognizer,
        smoother=smoother,
        backend=backend,
        target_lock_manager=TargetLockManager(),
    )

    assert result["target_id"] == "center"
    assert result["target_candidate_count"] == 2
    assert result["raw_expression"] == keys.EXPR_HAPPY
    assert recognizer.features == [result["extracted_features"]]
    assert result["extracted_features"]["smile_score"] == 0.9
    assert result["extracted_features"]["brow_down_score"] == 0.0


def test_process_frame_without_locked_target_returns_unknown():
    backend = FakeCandidateBackend([])
    recognizer = FakeRecognizer(keys.EXPR_HAPPY)
    smoother = FakeSmoother()

    result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "frame"},
        extractor=visual_demo.FaceFeatureExtractor(),
        recognizer=recognizer,
        smoother=smoother,
        backend=backend,
        target_lock_manager=TargetLockManager(),
    )

    assert result["target_locked"] is False
    assert result["target_visible"] is False
    assert result["raw_expression"] == keys.EXPR_UNKNOWN
    assert result["smoothed_expression"] == keys.EXPR_UNKNOWN
    assert recognizer.features == []
    assert smoother.expressions == []


def test_overlay_reports_no_locked_target_without_drawing_box():
    fake_cv2 = FakeCv2()
    debug_info = {
        "recognizer_mode": "rule",
        "raw_expression": keys.EXPR_UNKNOWN,
        "smoothed_expression": keys.EXPR_UNKNOWN,
        "target_locked": False,
        "target_visible": False,
        "target_id": None,
        "target_confidence": 0.0,
        "target_bbox": None,
        "lost_frames": 0,
        "target_candidate_count": 0,
        "extracted_features": {},
    }

    visual_demo.overlay_debug_info(
        {"fake": "frame"},
        debug_info,
        cv2_module=fake_cv2,
    )

    texts = [call["text"] for call in fake_cv2.text_calls]
    assert "target_locked: no" in texts
    assert "target_status: no locked target" in texts
    assert fake_cv2.rectangle_calls == []


def test_find_candidate_at_point_returns_matching_candidate():
    candidates = [
        {
            "candidate_id": "left",
            "bbox": (10, 20, 40, 40),
            "confidence": 0.9,
            "features": {},
        },
        {
            "candidate_id": "right",
            "bbox": (100, 20, 40, 40),
            "confidence": 0.9,
            "features": {},
        },
    ]

    selected = visual_demo.find_candidate_at_point(candidates, 115, 35)

    assert selected.candidate_id == "right"
    assert visual_demo.find_candidate_at_point(candidates, 80, 80) is None


def test_find_candidate_at_point_prefers_smallest_overlapping_box():
    candidates = [
        {
            "candidate_id": "large",
            "bbox": (0, 0, 100, 100),
            "confidence": 0.99,
            "features": {},
        },
        {
            "candidate_id": "small",
            "bbox": (20, 20, 20, 20),
            "confidence": 0.8,
            "features": {},
        },
    ]

    selected = visual_demo.find_candidate_at_point(candidates, 25, 25)

    assert selected.candidate_id == "small"


def test_handle_target_click_manually_locks_clicked_candidate():
    target_manager = TargetLockManager(min_area=1)
    candidates = [
        {
            "candidate_id": "left",
            "bbox": (10, 20, 40, 40),
            "confidence": 0.9,
            "features": {},
        },
        {
            "candidate_id": "right",
            "bbox": (100, 20, 40, 40),
            "confidence": 0.9,
            "features": {},
        },
    ]

    selected = visual_demo.handle_target_click(
        target_manager,
        candidates,
        115,
        35,
    )

    assert selected.candidate_id == "right"
    assert target_manager.is_manual_lock_active()
    assert target_manager.get_locked_target().candidate_id == "right"


def test_handle_target_key_controls_manual_lock_and_cycle():
    target_manager = TargetLockManager(
        min_area=1,
        prefer_center=False,
    )
    candidates = [
        {
            "candidate_id": 0,
            "raw_backend_index": 0,
            "bbox": (10, 20, 40, 40),
            "confidence": 0.9,
            "features": {},
        },
        {
            "candidate_id": 1,
            "raw_backend_index": 1,
            "bbox": (100, 20, 40, 40),
            "confidence": 0.9,
            "features": {},
        },
    ]
    target_manager.update(candidates)

    assert visual_demo.handle_target_key(
        "l",
        target_manager,
        candidates,
    ) == "locked"
    assert target_manager.is_manual_lock_active()
    assert visual_demo.handle_target_key(
        ord("n"),
        target_manager,
        candidates,
    ) == "next"
    assert target_manager.get_locked_target().raw_backend_index == 1
    assert visual_demo.handle_target_key(
        "p",
        target_manager,
        candidates,
    ) == "previous"
    assert target_manager.get_locked_target().raw_backend_index == 0
    assert visual_demo.handle_target_key(
        "u",
        target_manager,
        candidates,
    ) == "auto"
    assert not target_manager.is_manual_lock_active()

    target_manager.update(candidates)
    target_manager.manual_lock(1)
    assert visual_demo.handle_target_key(
        "a",
        target_manager,
        candidates,
    ) == "auto"
    assert not target_manager.is_manual_lock_active()
    assert visual_demo.handle_target_key(
        "x",
        target_manager,
        candidates,
    ) is None
    assert visual_demo.handle_target_key(
        "n",
        target_manager,
        [],
    ) is None
    assert visual_demo.handle_target_key(
        "q",
        target_manager,
        candidates,
    ) == "quit"


def test_process_frame_uses_manually_selected_candidate_only():
    candidates = [
        {
            "candidate_id": "left",
            "bbox": (20, 100, 120, 120),
            "confidence": 0.95,
            "features": {
                "smile_score": 0.1,
                "brow_down_score": 0.9,
                "face_confidence": 0.95,
            },
        },
        {
            "candidate_id": "center",
            "bbox": (260, 150, 120, 120),
            "confidence": 0.95,
            "features": {
                "smile_score": 0.9,
                "face_confidence": 0.95,
            },
        },
    ]
    backend = FakeCandidateBackend(candidates)
    target_manager = TargetLockManager()
    target_manager.manual_lock("left", candidates)
    recognizer = FakeRecognizer(keys.EXPR_ANGRY)
    smoother = FakeSmoother()

    result = visual_demo.process_frame_with_optional_backend(
        frame={"fake": "frame"},
        extractor=visual_demo.FaceFeatureExtractor(),
        recognizer=recognizer,
        smoother=smoother,
        backend=backend,
        target_lock_manager=target_manager,
    )

    assert result["target_mode"] == "manual"
    assert result["target_id"] == "left"
    assert result["raw_expression"] == keys.EXPR_ANGRY
    assert result["extracted_features"]["brow_down_score"] == 0.9
    assert result["extracted_features"]["smile_score"] == 0.1
    assert recognizer.features == [result["extracted_features"]]


def test_overlay_draws_candidate_labels_and_manual_target_style():
    fake_cv2 = FakeCv2()
    frame = {"fake": "frame"}
    candidates = [
        {
            "candidate_id": 0,
            "raw_backend_index": 0,
            "bbox": (10, 20, 40, 40),
            "confidence": 0.9,
            "features": {},
        },
        {
            "candidate_id": 1,
            "raw_backend_index": 1,
            "bbox": (100, 20, 40, 40),
            "confidence": 0.95,
            "features": {},
        },
    ]
    debug_info = {
        "recognizer_mode": "rule",
        "raw_expression": keys.EXPR_HAPPY,
        "smoothed_expression": keys.EXPR_HAPPY,
        "target_mode": "manual",
        "target_locked": True,
        "target_visible": True,
        "target_id": 1,
        "target_confidence": 0.95,
        "target_bbox": (100, 20, 40, 40),
        "lost_frames": 0,
        "target_candidate_count": 2,
        "target_candidates": candidates,
        "extracted_features": {},
    }

    visual_demo.overlay_debug_info(
        frame,
        debug_info,
        cv2_module=fake_cv2,
    )

    texts = [call["text"] for call in fake_cv2.text_calls]
    assert "target_mode: manual" in texts
    assert "candidate_count: 2" in texts
    assert "candidate 0" in texts
    assert "candidate 1" in texts
    assert "MANUAL TARGET" in texts
    assert fake_cv2.rectangle_calls[-1] == {
        "frame": frame,
        "start": (100, 20),
        "end": (140, 60),
        "color": (255, 0, 255),
        "thickness": 3,
    }


def test_overlay_reports_manual_lost_mode():
    lines = visual_demo._debug_overlay_lines(
        {
            "target_mode": "manual-lost",
            "target_locked": False,
            "target_visible": False,
            "target_id": 1,
            "target_candidate_count": 0,
            "recognizer_mode": "rule",
            "raw_expression": keys.EXPR_UNKNOWN,
            "smoothed_expression": keys.EXPR_UNKNOWN,
            "extracted_features": {},
        }
    )

    assert "target_mode: manual-lost" in lines
    assert "target_status: manual target lost" in lines


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


def test_tasks_result_builds_ordered_per_face_candidates():
    first_landmarks = _fake_face_landmarks(0.1, 0.2)
    second_landmarks = _fake_face_landmarks(0.6, 0.3)
    result = SimpleNamespace(
        face_blendshapes=[
            [
                SimpleNamespace(category_name="mouthSmileLeft", score=0.2),
            ],
            [
                SimpleNamespace(category_name="mouthSmileLeft", score=0.9),
            ],
        ],
        face_landmarks=[first_landmarks, second_landmarks],
    )

    candidates = visual_demo._candidates_from_tasks_result(
        result,
        frame_width=640,
        frame_height=480,
    )

    assert [item["raw_backend_index"] for item in candidates] == [0, 1]
    assert candidates[0]["features"]["smile_score"] == 0.2
    assert candidates[1]["features"]["smile_score"] == 0.9
    assert candidates[0]["bbox"] != candidates[1]["bbox"]
    assert candidates[0]["bbox"][2] > 0
    assert candidates[0]["bbox"][3] > 0


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


def _fake_face_landmarks(center_x, center_y):
    landmarks = [
        SimpleNamespace(x=center_x, y=center_y)
        for _ in range(478)
    ]
    landmarks[0] = SimpleNamespace(x=center_x - 0.05, y=center_y - 0.08)
    landmarks[1] = SimpleNamespace(x=center_x + 0.05, y=center_y + 0.08)
    return landmarks

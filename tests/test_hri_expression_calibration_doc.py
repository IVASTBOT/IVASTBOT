from pathlib import Path


DOC_PATH = Path("docs/hri_expression_calibration.md")


def test_expression_calibration_doc_exists():
    assert DOC_PATH.exists()


def test_expression_calibration_doc_mentions_all_labels():
    content = DOC_PATH.read_text(encoding="utf-8")

    for label in (
        "neutral",
        "happy",
        "surprise",
        "confused",
        "angry",
        "bored",
        "unknown",
    ):
        assert label in content


def test_expression_calibration_doc_mentions_not_committing_runtime_data():
    content = DOC_PATH.read_text(encoding="utf-8").lower()

    assert "do not commit" in content
    assert "calibration json" in content
    assert "face_landmarker.task" in content


def test_expression_calibration_doc_mentions_sample_count_guidance():
    content = DOC_PATH.read_text(encoding="utf-8")

    assert "20-30 samples per label" in content

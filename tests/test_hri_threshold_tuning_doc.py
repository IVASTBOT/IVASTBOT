from pathlib import Path


DOC_PATH = Path("docs/hri_threshold_tuning.md")


def test_threshold_tuning_doc_exists():
    assert DOC_PATH.exists()


def test_threshold_tuning_doc_mentions_phase_14_collection():
    content = DOC_PATH.read_text(encoding="utf-8")

    assert "expression_calibration_collector" in content
    assert "collect_from_image_folder" in content


def test_threshold_tuning_doc_mentions_analyzer_command():
    content = DOC_PATH.read_text(encoding="utf-8")

    assert "ivastbot_hri.demos.calibration_analyzer" in content
    assert "--output" in content


def test_threshold_tuning_doc_mentions_accuracy_and_thresholds():
    content = DOC_PATH.read_text(encoding="utf-8")

    assert "per-label" in content
    assert "accuracy" in content
    assert "happy_smile_threshold" in content
    assert "angry_brow_down_threshold" in content


def test_threshold_tuning_doc_says_this_is_not_training():
    content = DOC_PATH.read_text(encoding="utf-8").lower()

    assert "not classifier training" in content
    assert "does not" in content
    assert "train a model" in content

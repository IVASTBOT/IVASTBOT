from pathlib import Path


DOC_PATH = Path("docs/hri_expression_classifier.md")


def test_expression_classifier_doc_exists():
    assert DOC_PATH.exists()


def test_expression_classifier_doc_mentions_feature_scores_not_raw_images():
    content = DOC_PATH.read_text(encoding="utf-8").lower()

    assert "feature-score" in content
    assert "not raw images" in content


def test_expression_classifier_doc_mentions_nearest_centroid_and_no_heavy_deps():
    content = DOC_PATH.read_text(encoding="utf-8").lower()
    normalized_content = " ".join(content.split())

    assert "nearest-centroid" in content
    assert "does not require sklearn" in normalized_content
    assert "torch" in content
    assert "tensorflow" in content


def test_expression_classifier_doc_mentions_training_command_and_evaluation():
    content = DOC_PATH.read_text(encoding="utf-8")

    assert "ivastbot_hri.demos.train_expression_classifier" in content
    assert "--input" in content
    assert "--output" in content
    assert "per-label accuracy" in content
    assert "confusion summary" in content


def test_expression_classifier_doc_mentions_future_integration_not_default():
    content = DOC_PATH.read_text(encoding="utf-8")

    assert "does not replace the rule-based `ExpressionRecognizer`" in content
    assert "does not change the visual webcam demo by default" in content

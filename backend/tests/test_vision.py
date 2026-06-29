from pathlib import Path

from vision.recognizer import VisionRecognizer


def test_vision_unknown_without_enrollment(tmp_path: Path):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"not a real face")
    recognizer = VisionRecognizer(embeddings_dir=tmp_path / "embeddings")
    result = recognizer.recognize(image)
    assert result["status"] == "unknown"
    assert result["reason"] == "no_enrolled_members"


def test_vision_requires_consent(tmp_path: Path):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"not a real face")
    recognizer = VisionRecognizer(embeddings_dir=tmp_path / "embeddings")
    result = recognizer.enroll("theor-tran-minh-tien", image)
    assert result["status"] == "consent_required"


def test_vision_consent_gate(tmp_path: Path):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"not a real face")
    recognizer = VisionRecognizer(embeddings_dir=tmp_path / "embeddings")
    result = recognizer.enroll("iop-dinh-van-trung", image)
    assert result["status"] == "consent_required"

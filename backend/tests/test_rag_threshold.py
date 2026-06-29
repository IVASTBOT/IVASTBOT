from rag.generator import UNKNOWN_ANSWER, generate
from rag.retriever import has_enough_confidence


def test_threshold_rejects_high_distance():
    chunks = [{"text": "irrelevant", "distance": 0.9, "confidence": 0.1, "metadata": {}}]
    assert not has_enough_confidence(chunks, threshold=0.55)
    assert generate("unknown", chunks) == UNKNOWN_ANSWER


def test_threshold_accepts_low_distance():
    chunks = [{"text": "context", "distance": 0.2, "confidence": 0.8, "metadata": {"title": "T"}}]
    assert has_enough_confidence(chunks, threshold=0.55)


def test_rag_low_confidence_refuses():
    chunks = [{"text": "low", "distance": 0.56, "confidence": 0.44, "metadata": {"title": "T"}}]
    assert generate("câu hỏi ngoài dữ liệu", chunks) == UNKNOWN_ANSWER

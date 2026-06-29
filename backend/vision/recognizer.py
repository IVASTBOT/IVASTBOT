import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from config import VISION_CONFIDENCE_THRESHOLD, VISION_EMBEDDINGS_DIR
from members.resolver import load_members


class VisionRecognizer:
    def __init__(self, embeddings_dir: Path = VISION_EMBEDDINGS_DIR, threshold: float = VISION_CONFIDENCE_THRESHOLD):
        self.embeddings_dir = Path(embeddings_dir)
        self.threshold = threshold
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)

    def enroll(self, member_id: str, image_path: str | Path, dev_allow_without_consent: bool | None = None) -> dict[str, Any]:
        member = self._get_member(member_id)
        if not member:
            return {"status": "unknown_member", "member_id": member_id}
        if dev_allow_without_consent is None:
            dev_allow_without_consent = os.getenv("IVASTBOT_VISION_DEV_ALLOW_NO_CONSENT", "0") == "1"
        if not member.get("consent_for_vision") and not dev_allow_without_consent:
            return {"status": "consent_required", "member_id": member_id}
        image_path = Path(image_path)
        if not image_path.exists():
            return {"status": "image_not_found", "member_id": member_id, "image_path": str(image_path)}
        embedding = self._image_embedding(image_path)
        out = self.embeddings_dir / f"{member_id}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"member_id": member_id, "embedding": embedding, "image_path": str(image_path)}, f, indent=2)
        return {
            "status": "enrolled",
            "member_id": member_id,
            "embedding_path": str(out),
            "warning": "Placeholder fingerprint enrollment, not production face recognition.",
        }

    def recognize(self, image_path: str | Path) -> dict[str, Any]:
        image_path = Path(image_path)
        if not image_path.exists():
            return {"status": "unknown", "confidence": 0.0, "reason": "image_not_found"}
        enrolled = self._load_enrolled()
        if not enrolled:
            return {"status": "unknown", "confidence": 0.0, "reason": "no_enrolled_members"}
        query = self._image_embedding(image_path)
        best: tuple[float, dict[str, Any]] | None = None
        for item in enrolled:
            score = self._cosine(query, item["embedding"])
            if best is None or score > best[0]:
                best = (score, item)
        assert best is not None
        score, item = best
        if score < self.threshold:
            return {"status": "unknown", "confidence": round(score, 3)}
        member = self._get_member(item["member_id"])
        if not member or not member.get("consent_for_vision"):
            return {"status": "unknown", "confidence": 0.0, "reason": "member_not_consented"}
        return {"status": "recognized", "confidence": round(score, 3), "member": member}

    def _get_member(self, member_id: str) -> dict[str, Any] | None:
        for member in load_members():
            if member.get("member_id") == member_id:
                return member
        return None

    def _load_enrolled(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in self.embeddings_dir.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                item = json.load(f)
            member = self._get_member(item.get("member_id", ""))
            if member and member.get("consent_for_vision"):
                items.append(item)
        return items

    def _image_embedding(self, image_path: Path) -> list[float]:
        data = image_path.read_bytes()
        digest = hashlib.sha256(data).digest()
        values = [(byte / 255.0) for byte in digest]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def _cosine(self, a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

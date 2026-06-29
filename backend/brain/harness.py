from datetime import datetime
from pathlib import Path
from typing import Any

from config import DISTANCE_THRESHOLD, LOG_PATH, get_model_health
from members.resolver import lookup_member
from rag.generator import UNKNOWN_ANSWER, generate
from rag.retriever import has_enough_confidence, retrieve
from vision.cv_service import recognize_image

from .response import BrainRequest, BrainResponse
from .router import route_query, time_answer

class BrainHarness:
    def __init__(self, log_path: Path = LOG_PATH):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def handle(self, request: BrainRequest | dict[str, Any] | str) -> BrainResponse:
        req = BrainRequest.from_any(request)
        route = req.mode if req.mode != "auto" else route_query(req.query, req.image_path)
        if route == "time":
            response = BrainResponse(answer=time_answer(req.query), route="time", confidence=1.0, confidence_type="rule")
        elif route == "fixed":
            response = BrainResponse(
                answer="Xin chào. Tôi là trợ lý local của Viện Vật lý IOP-VAST.",
                route="fixed",
                confidence=1.0,
                confidence_type="rule",
            )
        elif route == "member":
            response = self._member_response(req.query)
            if response.route == "unknown":
                response = self._rag_response(req.query, warnings=response.warnings)
        elif route == "vision":
            response = self._vision_response(req)
        else:
            response = self._rag_response(req.query)
        self._log(req, response)
        return response

    def _member_response(self, query: str) -> BrainResponse:
        result = lookup_member(query)
        if result["status"] == "ambiguous":
            return BrainResponse(
                answer="Tôi chưa xác định chắc chắn thành viên được hỏi. Vui lòng nêu rõ họ tên hoặc đơn vị.",
                route="unknown",
                confidence=result["confidence"],
                confidence_type="member_fuzzy",
                metadata={"member_lookup": result},
                warnings=["Member lookup ambiguous; falling back to RAG in auto mode."],
            )
        if result["status"] != "found":
            return BrainResponse(
                answer=UNKNOWN_ANSWER,
                route="unknown",
                confidence=result["confidence"],
                confidence_type="member_fuzzy",
                metadata={"member_lookup": result},
                warnings=["Member lookup confidence below threshold; falling back to RAG in auto mode."],
            )
        member = result["member"]
        return BrainResponse(
            answer=result["answer"],
            route="member",
            confidence=result["confidence"],
            confidence_type=result.get("confidence_type", "member_fuzzy"),
            sources=[member.get("source", "")],
            metadata={"member": member, "candidates": result.get("candidates", [])},
        )

    def _vision_response(self, req: BrainRequest) -> BrainResponse:
        if not req.image_path:
            return BrainResponse(answer="Không có ảnh để nhận diện.", route="vision", confidence=0.0, confidence_type="vision")
        result = recognize_image(req.image_path)
        if result.get("status") != "recognized":
            return BrainResponse(
                answer="Không nhận diện được thành viên IOP đã enroll hoặc confidence thấp.",
                route="vision",
                confidence=float(result.get("confidence", 0.0)),
                confidence_type="vision_placeholder",
                metadata=result,
                warnings=["Vision harness is a placeholder, not production face recognition."],
            )
        member = result["member"]
        return BrainResponse(
            answer=f"Ảnh khớp với {member.get('display_name')}.",
            route="vision",
            confidence=float(result["confidence"]),
            confidence_type="vision_placeholder",
            sources=[member.get("source", "")],
            metadata=result,
            warnings=["Vision harness is a placeholder, not production face recognition."],
        )

    def _rag_response(self, query: str, warnings: list[str] | None = None) -> BrainResponse:
        chunks = retrieve(query)
        model_health = get_model_health()
        all_warnings = list(warnings or []) + model_health["warnings"]
        retrieval_metadata = {
            "top_k": [
                {
                    "distance": c.get("distance"),
                    "confidence": c.get("confidence"),
                    "metadata": c.get("metadata", {}),
                }
                for c in chunks
            ],
            "model": model_health,
        }
        if not has_enough_confidence(chunks, DISTANCE_THRESHOLD):
            best = chunks[0]["distance"] if chunks else 1.0
            return BrainResponse(
                answer=UNKNOWN_ANSWER,
                route="unknown",
                confidence=max(0.0, 1.0 - float(best)),
                confidence_type="rag_distance",
                metadata={**retrieval_metadata, "chunks": chunks},
                warnings=all_warnings,
            )
        answer = generate(query, chunks)
        sources = _source_objects(chunks)
        return BrainResponse(
            answer=answer,
            route="rag",
            confidence=chunks[0]["confidence"],
            confidence_type="rag_distance",
            sources=sources,
            metadata={**retrieval_metadata, "chunks": chunks},
            warnings=all_warnings,
        )

    def _log(self, req: BrainRequest, response: BrainResponse) -> None:
        event = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "query": req.query,
            "mode": req.mode,
            "image_path": req.image_path,
            "route": response.route,
            "status": response.status,
            "confidence": response.confidence,
            "confidence_type": response.confidence_type,
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            import json

            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _source_objects(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        key = (
            str(metadata.get("url", "")),
            str(metadata.get("title", "")),
            str(metadata.get("section", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "title": metadata.get("title", ""),
                "section": metadata.get("section", ""),
                "url": metadata.get("url", ""),
                "content_type": metadata.get("content_type", ""),
            }
        )
    return sources

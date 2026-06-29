import json
from datetime import datetime
from typing import Any

from config import DISTANCE_THRESHOLD, RAG_RETRIEVAL_LOG_PATH, TOP_K
from .store import get_collection, get_embedder


def distance_to_confidence(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - float(distance)))


def retrieve(query: str, top_k: int = TOP_K) -> list[dict[str, Any]]:
    embedder = get_embedder()
    collection = get_collection()
    query_vec = embedder.encode([query])[0].tolist()
    candidate_k = max(top_k, min(60, top_k * 12))
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=candidate_k,
        include=["documents", "metadatas", "distances"],
    )
    chunks: list[dict[str, Any]] = []
    for i, cid in enumerate(results.get("ids", [[]])[0]):
        distance = float(results.get("distances", [[0]])[0][i])
        metadata = dict(results.get("metadatas", [[{}]])[0][i] or {})
        metadata.setdefault("chunk_id", cid)
        chunks.append(
            {
                "text": results.get("documents", [[""]])[0][i],
                "distance": distance,
                "confidence": distance_to_confidence(distance),
                "metadata": metadata,
                "meta": metadata,
            }
        )
    chunks = augment_lexical_candidates(query, collection, chunks)
    chunks = rerank_chunks(query, chunks)[:top_k]
    log_retrieval(query, chunks)
    return chunks


def has_enough_confidence(chunks: list[dict[str, Any]], threshold: float = DISTANCE_THRESHOLD) -> bool:
    return bool(chunks) and float(chunks[0]["distance"]) <= threshold


def filter_context_chunks(chunks: list[dict[str, Any]], threshold: float = DISTANCE_THRESHOLD) -> list[dict[str, Any]]:
    return [chunk for chunk in chunks if float(chunk.get("distance", 1.0)) <= threshold]


def rerank_chunks(query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    q = query.lower()

    def score(chunk: dict[str, Any]) -> float:
        metadata = chunk.get("metadata", {})
        title = str(metadata.get("title", "")).lower()
        content_type = str(metadata.get("content_type", "")).lower()
        text = str(chunk.get("text", "")).lower()
        value = float(chunk.get("confidence", 0.0))

        asks_research = any(token in q for token in ["nghiên cứu", "nghien cuu", "làm gì", "lam gi", "hướng", "huong"])
        asks_publication = any(token in q for token in ["công bố", "cong bo", "sách", "sach", "sáng chế", "sang che"])
        asks_cooperation = any(token in q for token in ["hợp tác", "hop tac", "quốc tế", "quoc te"])
        asks_people = any(token in q for token in ["nhân lực", "nhan luc", "nhân sự", "nhan su", "ai", "giám đốc", "truong", "trưởng"])
        asks_seminar = "seminar" in q or "hội thảo" in q or "hoi thao" in q

        if asks_research:
            if "đề tài" in title or "de tai" in title or "giới thiệu" in title or "gioi thieu" in title:
                value += 0.18
            if "nghiên cứu" in title or "nghien cuu" in title:
                value += 0.12
            if content_type == "nhan_su" and not asks_people:
                value -= 0.12
            if "seminar" in title and not asks_seminar:
                value -= 0.08
        if asks_publication:
            if "công bố" in title or "cong bo" in title or "sách" in title or "sach" in title or "sáng chế" in title:
                value += 0.2
            if content_type == "nhan_su":
                value -= 0.1
        if asks_cooperation and ("hợp tác" in title or "hop tac" in title):
            value += 0.2
        if asks_people and content_type == "nhan_su":
            value += 0.08
        if asks_seminar and "seminar" in title:
            value += 0.2

        center_phrases = [
            "vật lý lý thuyết",
            "vat ly ly thuyet",
            "vật lý tính toán",
            "vat ly tinh toan",
            "điện tử lượng tử",
            "dien tu luong tu",
            "vật lý kỹ thuật",
            "vat ly ky thuat",
            "vật lý ứng dụng",
            "vat ly ung dung",
            "tự động hóa",
            "tu dong hoa",
        ]
        for phrase in center_phrases:
            if phrase in q:
                if phrase in title:
                    value += 0.12
                else:
                    value -= 0.2

        query_terms = [term for term in q.split() if len(term) >= 4]
        lexical_hits = sum(1 for term in query_terms if term in title or term in text)
        value += min(0.08, lexical_hits * 0.01)
        chunk["rerank_score"] = round(value, 4)
        return value

    return sorted(chunks, key=score, reverse=True)


def augment_lexical_candidates(query: str, collection: Any, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    q = query.lower()
    lexical_terms = []
    if "bằng sáng chế" in q or "bang sang che" in q or "sáng chế" in q or "sang che" in q:
        lexical_terms.extend(["bằng sáng chế", "sáng chế"])
    if "sách" in q or "sach" in q:
        lexical_terms.append("sách")
    if "công bố" in q or "cong bo" in q:
        lexical_terms.append("công bố")
    if not lexical_terms:
        return chunks

    seen_ids = {chunk.get("metadata", {}).get("chunk_id") for chunk in chunks}
    try:
        all_docs = collection.get(include=["documents", "metadatas"])
    except Exception:
        return chunks

    for cid, doc, metadata in zip(all_docs.get("ids", []), all_docs.get("documents", []), all_docs.get("metadatas", [])):
        metadata = dict(metadata or {})
        metadata.setdefault("chunk_id", cid)
        if metadata.get("chunk_id") in seen_ids:
            continue
        searchable = f"{metadata.get('title', '')}\n{doc}".lower()
        if not any(term in searchable for term in lexical_terms):
            continue
        chunks.append(
            {
                "text": doc,
                "distance": 0.35,
                "confidence": 0.65,
                "metadata": metadata,
                "meta": metadata,
                "retrieval_mode": "lexical_augment",
            }
        )
        seen_ids.add(metadata.get("chunk_id"))
    return chunks


def log_retrieval(query: str, chunks: list[dict[str, Any]]) -> None:
    try:
        RAG_RETRIEVAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "query": query,
            "top_k": [
                {
                    "distance": chunk.get("distance"),
                    "confidence": chunk.get("confidence"),
                    "metadata": chunk.get("metadata", {}),
                }
                for chunk in chunks
            ],
        }
        with open(RAG_RETRIEVAL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass

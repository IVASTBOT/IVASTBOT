from config import get_model_health
from .retriever import filter_context_chunks, has_enough_confidence
from .store import get_ollama

UNKNOWN_ANSWER = "Chưa có đủ thông tin trong dữ liệu hiện tại để trả lời câu hỏi này."


def build_prompt(query: str, context_chunks: list[dict]) -> str:
    context = "\n\n---\n\n".join(
        "\n".join(
            [
                f"Nguồn: {c['metadata'].get('title', 'Không rõ')}",
                f"Section: {c['metadata'].get('section', 'unknown')}",
                f"URL: {c['metadata'].get('url', '')}",
                f"Độ liên quan: {c['confidence']:.2f}",
                "Nội dung:",
                c["text"],
            ]
        )
        for c in context_chunks
    )
    return f"""Bạn là trợ lý AI của Viện Vật lý IOP-VAST.
Chỉ trả lời dựa trên CONTEXT được cung cấp bên dưới.
Không tự suy diễn, không bổ sung kiến thức ngoài context, không bịa tên người/email/số liệu.
Nếu context không đủ để trả lời chắc chắn, hãy nói đúng: "{UNKNOWN_ANSWER}"
Trả lời bằng tiếng Việt tự nhiên, ngắn gọn, ưu tiên 2-5 câu.
Nếu có nguồn phù hợp, nêu ngắn gọn tên nguồn hoặc section ở cuối câu trả lời.

=== CONTEXT ===
{context}

=== CÂU HỎI ===
{query}

=== TRẢ LỜI ==="""


def generate(query: str, context_chunks: list[dict]) -> str:
    if not has_enough_confidence(context_chunks):
        return UNKNOWN_ANSWER
    filtered_chunks = filter_context_chunks(context_chunks)
    if not filtered_chunks:
        return UNKNOWN_ANSWER
    prompt = build_prompt(query, filtered_chunks)
    model_health = get_model_health()
    model = model_health["active_model"]
    try:
        response = get_ollama().chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )
        return response["message"]["content"].strip()
    except Exception as exc:
        warnings = "; ".join(model_health["warnings"])
        detail = f"{warnings}; " if warnings else ""
        return f"{UNKNOWN_ANSWER} ({detail}Không gọi được Ollama local model '{model}': {exc})"

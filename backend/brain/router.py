import re
from datetime import datetime

from members.resolver import has_member_intent, lookup_member

TIME_PATTERNS = [
    r"\bmấy giờ\b",
    r"\bgiờ hiện tại\b",
    r"\bthời gian hiện tại\b",
    r"\bbây giờ là mấy giờ\b",
    r"\bwhat time\b",
    r"\bngày mấy\b",
    r"\bhôm nay ngày\b",
    r"\bngày hiện tại\b",
    r"\bcurrent date\b",
    r"\bthứ mấy\b",
    r"\bhôm nay là thứ\b",
    r"\bhôm nay thứ mấy\b",
    r"\bwhat day is today\b",
]

GREETING_PATTERNS = [r"^hello$", r"^hi$", r"^xin chào$", r"^chào$", r"^bạn là ai\??$"]
RAG_INTENT_PATTERNS = [
    r"\bnghiên cứu\b",
    r"\bcông bố\b",
    r"\bphòng thí nghiệm\b",
    r"\bhoạt động\b",
    r"\blịch sử\b",
    r"\bnhiệm vụ\b",
    r"\bchức năng\b",
    r"\bđề tài\b",
]


def route_query(query: str, image_path: str | None = None) -> str:
    q = query.lower().strip()
    if "thứ trưởng" not in q and any(re.search(pattern, q) for pattern in TIME_PATTERNS):
        return "time"
    if any(re.search(pattern, q) for pattern in GREETING_PATTERNS):
        return "fixed"
    if image_path:
        return "vision"
    if any(re.search(pattern, q) for pattern in RAG_INTENT_PATTERNS):
        return "rag"
    if has_member_intent(query):
        member_hit = lookup_member(query)
        if member_hit.get("status") == "found":
            return "member"
    return "rag"


def time_answer(query: str) -> str:
    q = query.lower().strip()
    now = datetime.now()
    weekdays = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    if any(kw in q for kw in ["thứ mấy", "hôm nay là thứ", "hôm nay thứ mấy", "what day is today"]):
        return f"Hôm nay là {weekdays[now.weekday()]}."
    if any(kw in q for kw in ["ngày mấy", "hôm nay ngày", "ngày hiện tại", "date"]):
        return f"Hôm nay là {weekdays[now.weekday()]}, ngày {now.day} tháng {now.month} năm {now.year}."
    return now.strftime("Bây giờ là %H giờ %M phút %S giây, ngày %d/%m/%Y.")

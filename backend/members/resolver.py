import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from config import MEMBER_AMBIGUITY_MARGIN, MEMBER_NAME_THRESHOLD, MEMBER_ROLE_THRESHOLD, MEMBERS_PATH

_members_cache: list[dict[str, Any]] | None = None


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


MEMBER_INTENT_PATTERNS = [
    r"\bai la\b",
    r"\bla ai\b",
    r"\bgiam doc\b",
    r"\btruong\b",
    r"\bpho\b",
    r"\bthanh vien\b",
    r"\bemail\b",
    r"\blien he\b",
    r"\bcan bo\b",
    r"\bnhan su\b",
]


def load_members(path: Path = MEMBERS_PATH) -> list[dict[str, Any]]:
    global _members_cache
    if _members_cache is None:
        members: list[dict[str, Any]] = []
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        members.append(json.loads(line))
        _members_cache = members
    return _members_cache


def has_member_intent(query: str) -> bool:
    query_norm = normalize_text(query)
    if any(re.search(pattern, query_norm) for pattern in MEMBER_INTENT_PATTERNS):
        return True
    for member in load_members():
        names = [member.get("full_name", ""), *member.get("aliases", [])]
        if any(_field_match(query_norm, name) >= MEMBER_NAME_THRESHOLD for name in names if name):
            return True
    return False


def _field_match(query_norm: str, field: str) -> float:
    field_norm = normalize_text(field)
    if not field_norm:
        return 0.0
    if field_norm in query_norm:
        return 1.0
    return SequenceMatcher(None, query_norm, field_norm).ratio()


def _score_member(query_norm: str, member: dict[str, Any]) -> tuple[float, str]:
    names = [member.get("full_name", ""), member.get("display_name", ""), *member.get("aliases", [])]
    roles = member.get("roles", [])
    unit = member.get("unit", "")

    name_score = max((_field_match(query_norm, field) for field in names if field), default=0.0)
    role_score = max((_field_match(query_norm, role) for role in roles if role), default=0.0)
    unit_score = _field_match(query_norm, unit)

    role_unit_score = min(1.0, role_score * 0.55 + unit_score * 0.45)
    if role_score >= 0.95 and unit_score >= 0.75:
        role_unit_score = max(role_unit_score, MEMBER_ROLE_THRESHOLD + 0.15)

    if name_score >= MEMBER_NAME_THRESHOLD:
        return name_score, "member_name"
    if role_unit_score >= MEMBER_ROLE_THRESHOLD:
        return role_unit_score, "member_role"

    query_tokens = set(query_norm.split())
    partial_name_bonus = 0.0
    for name in names:
        name_tokens = set(normalize_text(name).split())
        overlap = query_tokens & name_tokens
        if len(query_tokens) <= 3 and overlap and not {"ts", "pgs", "gs"}.issuperset(overlap):
            partial_name_bonus = max(partial_name_bonus, 0.35 + 0.15 * min(len(overlap), 2))

    combined = max(name_score, role_unit_score, partial_name_bonus)
    confidence_type = "member_partial_name" if combined == partial_name_bonus else "member_fuzzy"
    return min(1.0, combined), confidence_type


def lookup_member(query: str) -> dict[str, Any]:
    members = load_members()
    query_norm = normalize_text(query)
    if not query_norm or not members:
        return {"status": "unknown", "confidence": 0.0, "member": None}
    ranked = sorted(
        ((*_score_member(query_norm, member), member) for member in members),
        reverse=True,
        key=lambda x: x[0],
    )
    confidence, confidence_type, member = ranked[0]
    if confidence_type == "member_role":
        threshold = MEMBER_ROLE_THRESHOLD
    elif confidence_type == "member_partial_name":
        threshold = 0.5
    else:
        threshold = MEMBER_NAME_THRESHOLD
    candidates = [
        {
            "member_id": cand.get("member_id"),
            "display_name": cand.get("display_name"),
            "unit": cand.get("unit"),
            "roles": cand.get("roles", []),
            "confidence": round(score, 3),
            "confidence_type": ctype,
        }
        for score, ctype, cand in ranked[:5]
        if score >= min(threshold, confidence - MEMBER_AMBIGUITY_MARGIN)
    ]
    if confidence < threshold:
        return {"status": "unknown", "confidence": round(confidence, 3), "member": None, "candidates": candidates}
    if len(candidates) > 1 and candidates[1]["confidence"] >= confidence - MEMBER_AMBIGUITY_MARGIN:
        return {
            "status": "ambiguous",
            "confidence": round(confidence, 3),
            "member": None,
            "candidates": candidates,
            "answer": "Tôi tìm thấy nhiều thành viên có thể khớp. Vui lòng nêu rõ họ tên hoặc đơn vị.",
        }
    return {
        "status": "found",
        "confidence": round(confidence, 3),
        "confidence_type": confidence_type,
        "member": member,
        "candidates": candidates,
        "answer": _format_member_answer(member),
    }


def _format_member_answer(member: dict[str, Any]) -> str:
    roles = ", ".join(member.get("roles", []))
    unit = member.get("unit", "")
    email = member.get("email")
    answer = f"{roles} {unit} là {member.get('display_name')}".strip()
    if email:
        answer += f" ({email})"
    return answer + "."

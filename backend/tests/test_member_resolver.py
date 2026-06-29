from members.resolver import lookup_member, normalize_text


def test_normalize_vietnamese():
    assert normalize_text("Đỗ Hoàng Tùng") == "do hoang tung"


def test_lookup_current_theoretical_physics_director():
    result = lookup_member("giám đốc trung tâm vật lý lý thuyết là ai")
    assert result["status"] == "found"
    assert result["member"]["full_name"] == "Trần Minh Tiến"


def test_lookup_unknown_does_not_hallucinate():
    result = lookup_member("nhân vật không tồn tại xyzabc")
    assert result["status"] == "unknown"
    assert result["member"] is None


def test_member_unknown_does_not_hallucinate():
    result = lookup_member("ai là Nguyễn Không Có Trong Dữ Liệu")
    assert result["status"] == "unknown"
    assert result["member"] is None


def test_member_ambiguous_returns_candidates_or_fallback():
    result = lookup_member("Tiến")
    assert result["status"] == "ambiguous"
    assert result["member"] is None
    assert len(result["candidates"]) >= 2

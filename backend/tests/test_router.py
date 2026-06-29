from brain.router import route_query


def test_router_time():
    assert route_query("hôm nay thứ mấy") == "time"


def test_router_fixed():
    assert route_query("hello") == "fixed"


def test_router_member():
    assert route_query("giám đốc trung tâm vật lý lý thuyết là ai") == "member"


def test_router_member_director_question():
    assert route_query("giám đốc trung tâm vật lý lý thuyết là ai") == "member"


def test_router_research_question_goes_rag():
    assert route_query("trung tâm vật lý lý thuyết nghiên cứu gì") == "rag"


def test_router_thu_truong_false_positive():
    assert route_query("Thứ trưởng Bộ Khoa học là ai") == "rag"


def test_router_vision_with_image_after_non_member():
    assert route_query("ảnh này là ai", image_path="/tmp/no-image.jpg") == "vision"

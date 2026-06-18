from ivastbot_hri.adapters.fake_face_adapter import FakeFaceAdapter
from ivastbot_hri.adapters.fake_gesture_adapter import FakeGestureAdapter
from ivastbot_hri.adapters.fake_navigation_adapter import FakeNavigationAdapter


def test_fake_face_adapter_records_commands():
    adapter = FakeFaceAdapter()

    adapter.send("SHOW_HAPPY_FACE")
    adapter.send("SHOW_THINKING_FACE", {"duration_ms": 500})

    assert adapter.commands == [
        ("SHOW_HAPPY_FACE", {}),
        ("SHOW_THINKING_FACE", {"duration_ms": 500}),
    ]


def test_fake_gesture_adapter_records_commands():
    adapter = FakeGestureAdapter()

    adapter.send("WAVE_HAND")
    adapter.send("POINT_LEFT", {"direction": "left"})

    assert adapter.commands == [
        ("WAVE_HAND", {}),
        ("POINT_LEFT", {"direction": "left"}),
    ]


def test_fake_navigation_adapter_records_commands():
    adapter = FakeNavigationAdapter()

    adapter.send("GUIDE_TO_TARGET", {"target": "front_desk"})

    assert adapter.commands == [("GUIDE_TO_TARGET", {"target": "front_desk"})]


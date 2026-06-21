from pathlib import Path


DOC_PATH = Path("docs/hri_ros2_mapping.md")


def read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_hri_ros2_mapping_doc_exists():
    assert DOC_PATH.exists()


def test_hri_ros2_mapping_doc_mentions_all_logical_channels():
    content = read_doc()

    for channel in (
        "hri.face.command",
        "hri.gesture.command",
        "hri.navigation.command",
        "hri.stop.command",
        "hri.status.event",
    ):
        assert channel in content


def test_hri_ros2_mapping_doc_mentions_core_has_no_rclpy_dependency():
    content = read_doc().lower()

    assert "core logic must not import `rclpy`" in content
    assert "only adapter files may depend on ros 2" in content


def test_hri_ros2_mapping_doc_mentions_future_ubuntu_ros2_integration():
    content = read_doc()

    assert "Ubuntu/ROS 2" in content
    assert "ROS 2 Humble" in content


def test_hri_ros2_mapping_doc_mentions_future_mapping_targets():
    content = read_doc()

    for target in (
        "/ivastbot/hri/face_command",
        "/ivastbot/hri/gesture_command",
        "/ivastbot/hri/guide_to_target",
        "/ivastbot/hri/stop",
        "/ivastbot/hri/status_event",
    ):
        assert target in content

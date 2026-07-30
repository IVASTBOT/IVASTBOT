from pathlib import Path


DOC_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "hri_uart_gesture_adapter.md"
)


def test_uart_gesture_documentation_covers_build_and_runtime_contract():
    content = DOC_PATH.read_text(encoding="utf-8")

    assert "HRI_GESTURE_BACKEND=fake" in content
    assert "HRI_GESTURE_BACKEND=uart" in content
    assert "HRI_GESTURE_PORT=/dev/ttyUSB0" in content
    assert "HRI_GESTURE_LIBRARY=" in content
    assert "make -B" in content
    assert "python -m ivastbot_hri.demos.uart_gesture_demo" in content
    assert "robot_send_raw" in content

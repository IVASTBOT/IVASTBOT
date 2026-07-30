import pytest

from ivastbot_hri.adapters.fake_gesture_adapter import FakeGestureAdapter
from ivastbot_hri.adapters.gesture_adapter_factory import create_gesture_adapter
from ivastbot_hri.adapters.linux_uart_gesture_adapter import (
    DEFAULT_POSE,
    LinuxUARTGestureAdapter,
)
from ivastbot_hri.core import keys
from ivastbot_hri.core.action_library import ActionLibrary


class FakeUARTClient:
    def __init__(self):
        self.connected = False
        self.poses = []

    def connect(self):
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False

    def send_pose(self, pose, speed):
        self.poses.append((tuple(pose), speed))
        return True


def test_fake_gesture_adapter_remains_default_backend():
    adapter = create_gesture_adapter(environ={})

    assert isinstance(adapter, FakeGestureAdapter)
    adapter.send(keys.WAVE_HAND)
    assert adapter.commands == [(keys.WAVE_HAND, {})]


def test_uart_backend_uses_environment_configuration_without_connecting():
    client = FakeUARTClient()

    adapter = create_gesture_adapter(
        environ={
            "HRI_GESTURE_BACKEND": "uart",
            "HRI_GESTURE_PORT": "/dev/ttyUSB7",
            "HRI_GESTURE_LIBRARY": "/opt/ivastbot/librobot_uart.so",
        },
        client=client,
        sleep_fn=lambda _seconds: None,
    )

    assert isinstance(adapter, LinuxUARTGestureAdapter)
    assert adapter.port == "/dev/ttyUSB7"
    assert adapter.library_path == "/opt/ivastbot/librobot_uart.so"
    assert not adapter.connected


def test_explicit_backend_overrides_environment():
    adapter = create_gesture_adapter(
        backend="fake",
        environ={"HRI_GESTURE_BACKEND": "uart"},
    )

    assert isinstance(adapter, FakeGestureAdapter)


def test_unknown_backend_raises_clear_error():
    with pytest.raises(ValueError, match="Expected 'fake' or 'uart'"):
        create_gesture_adapter(environ={"HRI_GESTURE_BACKEND": "serial"})


def test_action_library_executes_wave_through_factory_uart_adapter():
    client = FakeUARTClient()
    adapter = create_gesture_adapter(
        backend="uart",
        environ={},
        client=client,
        dwell=0.0,
        transition_dwell=0.0,
        sleep_fn=lambda _seconds: None,
    )
    adapter.connect()
    library = ActionLibrary(gesture_adapter=adapter)

    result = library.execute(keys.WAVE_HAND)

    assert result.executed
    assert result.reason == "executed"
    assert client.poses[0][0] == DEFAULT_POSE
    assert client.poses[-1][0] == DEFAULT_POSE

import importlib
import sys

import pytest

from ivastbot_hri.adapters.linux_uart_gesture_adapter import (
    ANGLE_COMMAND,
    CMD_ANGLE,
    DEFAULT_POSE,
    DEFAULT_SPEED,
    UART_LINUX_REQUIRED_MESSAGE,
    WAVING_START_POSE,
    WAVE_MAX,
    WAVE_MIN,
    LinuxUARTGestureAdapter,
    RobotUARTClient,
)
from ivastbot_hri.core import keys


class FakeCFunction:
    def __init__(self, result=None):
        self.result = result
        self.calls = []
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class FakeLibrary:
    def __init__(self):
        self.robot_open = FakeCFunction(17)
        self.robot_close = FakeCFunction()
        self.robot_send_raw = FakeCFunction(1)


class FakeUARTClient:
    def __init__(self):
        self.connected = False
        self.events = []
        self.poses = []

    def connect(self):
        self.connected = True
        self.events.append("connect")
        return True

    def disconnect(self):
        self.connected = False
        self.events.append("disconnect")

    def send_pose(self, pose, speed):
        self.poses.append((tuple(pose), speed))
        return True


def test_module_import_does_not_load_shared_library():
    before = set(sys.modules)

    module = importlib.reload(
        importlib.import_module(
            "ivastbot_hri.adapters.linux_uart_gesture_adapter"
        )
    )

    assert module.LinuxUARTGestureAdapter is not None
    assert set(sys.modules) >= before


def test_robot_uart_library_is_loaded_only_during_connect():
    loaded_paths = []
    fake_library = FakeLibrary()
    client = RobotUARTClient(
        library_path="/tmp/librobot_uart.so",
        library_loader=lambda path: loaded_paths.append(path) or fake_library,
        platform_provider=lambda: "Linux",
    )

    assert loaded_paths == []
    assert not client.library_loaded

    assert client.connect()

    assert loaded_paths == ["/tmp/librobot_uart.so"]
    assert client.library_loaded
    assert fake_library.robot_open.calls == [(b"/dev/ttyUSB0",)]


def test_robot_uart_connect_disconnect_and_raw_pose_packet():
    fake_library = FakeLibrary()
    client = RobotUARTClient(
        port="/dev/ttyUSB9",
        library_path="/tmp/librobot_uart.so",
        library_loader=lambda _path: fake_library,
        platform_provider=lambda: "Linux",
    )

    assert client.connect()
    assert client.connected
    assert client.send_pose(DEFAULT_POSE, DEFAULT_SPEED)

    raw_args = fake_library.robot_send_raw.calls[0]
    assert raw_args[0] == 17
    assert raw_args[1:3] == (CMD_ANGLE, ANGLE_COMMAND)
    assert raw_args[3:12] == DEFAULT_POSE
    assert raw_args[12] == DEFAULT_SPEED

    client.disconnect()

    assert not client.connected
    assert not client.library_loaded
    assert fake_library.robot_close.calls == [(17,)]


def test_real_uart_connect_on_windows_raises_clear_error_without_loading_library():
    loader_calls = []
    client = RobotUARTClient(
        library_loader=lambda path: loader_calls.append(path),
        platform_provider=lambda: "Windows",
    )

    with pytest.raises(RuntimeError, match="requires Linux") as error_info:
        client.connect()

    assert str(error_info.value) == UART_LINUX_REQUIRED_MESSAGE
    assert loader_calls == []


def test_adapter_connect_and_disconnect_use_injected_client():
    client = FakeUARTClient()
    adapter = LinuxUARTGestureAdapter(client=client)

    assert not adapter.connected
    assert adapter.connect()
    assert adapter.connected

    adapter.disconnect()

    assert not adapter.connected
    assert client.events == ["connect", "disconnect"]


def test_wave_sends_verified_pose_sequence_and_uses_injected_sleep():
    client = FakeUARTClient()
    sleep_calls = []
    adapter = LinuxUARTGestureAdapter(
        client=client,
        dwell=0.25,
        transition_dwell=0.5,
        sleep_fn=sleep_calls.append,
    )
    adapter.connect()

    assert adapter.send(keys.WAVE_HAND)

    expected_start = tuple(WAVING_START_POSE)
    expected_max = expected_start[:2] + (WAVE_MAX,) + expected_start[3:]
    expected_min = expected_start[:2] + (WAVE_MIN,) + expected_start[3:]
    assert [pose for pose, _speed in client.poses] == [
        DEFAULT_POSE,
        expected_start,
        expected_max,
        expected_min,
        DEFAULT_POSE,
    ]
    assert client.poses[-1][0] == DEFAULT_POSE
    assert all(speed == DEFAULT_SPEED for _pose, speed in client.poses)
    assert sleep_calls == [0.5, 0.5, 0.25, 0.25, 0.5]


def test_wave_payload_duration_overrides_endpoint_dwell_without_real_sleep():
    client = FakeUARTClient()
    sleep_calls = []
    adapter = LinuxUARTGestureAdapter(
        client=client,
        transition_dwell=0.0,
        sleep_fn=sleep_calls.append,
    )
    adapter.connect()

    adapter.send(keys.WAVE_HAND, {"duration_ms": 125})

    assert sleep_calls == [0.0, 0.0, 0.125, 0.125, 0.0]


def test_stop_action_returns_to_verified_default_pose():
    client = FakeUARTClient()
    adapter = LinuxUARTGestureAdapter(client=client)
    adapter.connect()

    assert adapter.send(keys.STOP_ACTION)

    assert client.poses == [(DEFAULT_POSE, DEFAULT_SPEED)]


def test_unverified_gesture_raises_clear_unsupported_error():
    adapter = LinuxUARTGestureAdapter(client=FakeUARTClient())

    with pytest.raises(NotImplementedError, match="no verified robot pose"):
        adapter.send(keys.POINT_LEFT)

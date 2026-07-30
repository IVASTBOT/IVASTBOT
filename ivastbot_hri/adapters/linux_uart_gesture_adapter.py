"""Linux UART gesture adapter for the IVASTBOT arm controller."""

from __future__ import annotations

import ctypes
import platform
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from ivastbot_hri.core import keys

CMD_ANGLE = ord("G")
ANGLE_COMMAND = 1
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_SPEED = 15
WAVE_DWELL = 3.2
TRANSITION_DWELL = 2.0

DEFAULT_POSE = (20, 30, 13, 15, 90, 15, 13, 30, 20)
WAVING_START_POSE = (40, 40, 120, 20, 90, 15, 13, 30, 20)
WAVE_MIN = 120
WAVE_MAX = 180

DEFAULT_LIBRARY_PATH = (
    Path(__file__).resolve().parents[1]
    / "native"
    / "robot_uart"
    / "librobot_uart.so"
)

UART_LINUX_REQUIRED_MESSAGE = (
    "The UART gesture backend requires Linux and librobot_uart.so. "
    "Use HRI_GESTURE_BACKEND=fake on Windows."
)


class RobotUARTClient:
    """Lazy ctypes wrapper around the native robot UART library."""

    def __init__(
        self,
        port: str = DEFAULT_PORT,
        library_path: str | Path = DEFAULT_LIBRARY_PATH,
        library_loader: Callable[[str], object] | None = None,
        platform_provider: Callable[[], str] = platform.system,
    ):
        self.port = str(port)
        self.library_path = str(library_path)
        self._library_loader = library_loader
        self._platform_provider = platform_provider
        self._library = None
        self._fd = -1

    @property
    def connected(self) -> bool:
        return self._fd >= 0

    @property
    def library_loaded(self) -> bool:
        return self._library is not None

    def connect(self) -> bool:
        """Load the Linux library and open the configured serial port."""
        if self.connected:
            return True

        if self._platform_provider().lower() != "linux":
            raise RuntimeError(UART_LINUX_REQUIRED_MESSAGE)

        loader = self._library_loader or ctypes.CDLL
        try:
            library = loader(self.library_path)
        except OSError as error:
            raise RuntimeError(
                f"Could not load UART library {self.library_path!r}. "
                "Build it on the Linux robot with 'make -B'."
            ) from error

        self._configure_library(library)
        fd = library.robot_open(self.port.encode("utf-8"))
        if fd < 0:
            raise RuntimeError(f"Could not open UART serial port {self.port!r}.")

        self._library = library
        self._fd = fd
        return True

    def disconnect(self) -> None:
        """Close the serial port and release the loaded library reference."""
        library = self._library
        fd = self._fd
        try:
            if library is not None and fd >= 0:
                library.robot_close(fd)
        finally:
            self._fd = -1
            self._library = None

    def send_pose(self, pose: Sequence[int], speed: int) -> bool:
        """Send one nine-joint pose through the 12-byte angle packet."""
        if not self.connected or self._library is None:
            raise RuntimeError("UART gesture adapter is not connected.")

        normalized_pose = _validate_pose(pose)
        normalized_speed = _validate_byte_value(speed, "speed")
        sent = self._library.robot_send_raw(
            self._fd,
            CMD_ANGLE,
            ANGLE_COMMAND,
            *normalized_pose,
            normalized_speed,
        )
        if not sent:
            raise RuntimeError("Failed to send an arm pose over UART.")
        return True

    @staticmethod
    def _configure_library(library) -> None:
        library.robot_open.argtypes = [ctypes.c_char_p]
        library.robot_open.restype = ctypes.c_int
        library.robot_close.argtypes = [ctypes.c_int]
        library.robot_close.restype = None
        library.robot_send_raw.argtypes = [
            ctypes.c_int,
            ctypes.c_uint8,
            ctypes.c_uint8,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        library.robot_send_raw.restype = ctypes.c_int


class LinuxUARTGestureAdapter:
    """Execute verified arm gestures through a Linux RobotUARTClient."""

    def __init__(
        self,
        port: str = DEFAULT_PORT,
        library_path: str | Path = DEFAULT_LIBRARY_PATH,
        speed: int = DEFAULT_SPEED,
        dwell: float = WAVE_DWELL,
        transition_dwell: float = TRANSITION_DWELL,
        sleep_fn: Callable[[float], None] = time.sleep,
        client: RobotUARTClient | None = None,
    ):
        self.port = str(port)
        self.library_path = str(library_path)
        self.speed = _validate_byte_value(speed, "speed")
        self.dwell = _validate_duration(dwell, "dwell")
        self.transition_dwell = _validate_duration(
            transition_dwell,
            "transition_dwell",
        )
        self._sleep = sleep_fn
        self._client = client or RobotUARTClient(
            port=self.port,
            library_path=self.library_path,
        )

    @property
    def connected(self) -> bool:
        return bool(self._client.connected)

    def connect(self) -> bool:
        return self._client.connect()

    def disconnect(self) -> None:
        self._client.disconnect()

    def send(self, command: str, payload: dict | None = None) -> bool:
        """Execute a verified gesture command from ActionLibrary."""
        command_payload = dict(payload or {})
        if command == keys.WAVE_HAND:
            dwell = _duration_from_payload(command_payload, self.dwell)
            return self.wave(dwell=dwell)
        if command == keys.STOP_ACTION:
            return self.home()
        raise NotImplementedError(
            f"UART gesture command {command!r} has no verified robot pose."
        )

    def home(self, speed: int | None = None) -> bool:
        """Move the arm to the verified default/neutral pose."""
        return self._send_pose(DEFAULT_POSE, speed)

    neutral = home

    def wave(
        self,
        *,
        speed: int | None = None,
        dwell: float | None = None,
        transition_dwell: float | None = None,
    ) -> bool:
        """Run the verified default-to-wave-to-default pose sequence."""
        active_speed = self.speed if speed is None else _validate_byte_value(speed, "speed")
        active_dwell = self.dwell if dwell is None else _validate_duration(dwell, "dwell")
        active_transition = (
            self.transition_dwell
            if transition_dwell is None
            else _validate_duration(transition_dwell, "transition_dwell")
        )

        self.home(active_speed)
        self._sleep(active_transition)
        try:
            wave_pose = list(WAVING_START_POSE)
            self._send_pose(wave_pose, active_speed)
            self._sleep(active_transition)

            wave_pose[2] = WAVE_MAX
            self._send_pose(wave_pose, active_speed)
            self._sleep(active_dwell)

            wave_pose[2] = WAVE_MIN
            self._send_pose(wave_pose, active_speed)
            self._sleep(active_dwell)
        finally:
            self.home(active_speed)
            self._sleep(active_transition)

        return True

    def _send_pose(self, pose: Sequence[int], speed: int | None = None) -> bool:
        active_speed = self.speed if speed is None else _validate_byte_value(speed, "speed")
        return self._client.send_pose(pose, active_speed)


def _duration_from_payload(payload: dict, default: float) -> float:
    if "duration" in payload:
        return _validate_duration(payload["duration"], "duration")
    if "duration_ms" in payload:
        milliseconds = _validate_duration(payload["duration_ms"], "duration_ms")
        return milliseconds / 1000.0
    return default


def _validate_pose(pose: Sequence[int]) -> tuple[int, ...]:
    if len(pose) != 9:
        raise ValueError("Arm pose must contain exactly nine joint values.")
    return tuple(
        _validate_byte_value(value, f"joint_{index}")
        for index, value in enumerate(pose, start=1)
    )


def _validate_byte_value(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if not 0 <= value <= 255:
        raise ValueError(f"{name} must be between 0 and 255.")
    return value


def _validate_duration(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric.")
    if value < 0:
        raise ValueError(f"{name} must be non-negative.")
    return float(value)


__all__ = (
    "ANGLE_COMMAND",
    "CMD_ANGLE",
    "DEFAULT_LIBRARY_PATH",
    "DEFAULT_PORT",
    "DEFAULT_POSE",
    "DEFAULT_SPEED",
    "LinuxUARTGestureAdapter",
    "RobotUARTClient",
    "TRANSITION_DWELL",
    "UART_LINUX_REQUIRED_MESSAGE",
    "WAVE_DWELL",
    "WAVE_MAX",
    "WAVE_MIN",
    "WAVING_START_POSE",
)

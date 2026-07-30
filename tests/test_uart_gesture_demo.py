import importlib

from ivastbot_hri.demos.uart_gesture_demo import (
    build_argument_parser,
    run_hardware_demo,
)


class FakeHardwareAdapter:
    def __init__(self):
        self.events = []

    def connect(self):
        self.events.append("connect")
        return True

    def disconnect(self):
        self.events.append("disconnect")

    def home(self):
        self.events.append("home")
        return True

    def wave(self):
        self.events.append("wave")
        return True


def test_uart_demo_import_has_no_hardware_side_effects():
    module = importlib.reload(
        importlib.import_module("ivastbot_hri.demos.uart_gesture_demo")
    )

    assert module.run_hardware_demo is not None


def test_wave_demo_confirms_action_and_disconnects_in_finally():
    adapter = FakeHardwareAdapter()
    prompts = []
    output = []

    result = run_hardware_demo(
        adapter,
        action="wave",
        confirm_fn=lambda prompt: prompts.append(prompt) or "wave",
        output_fn=output.append,
    )

    assert result == 0
    assert adapter.events == ["connect", "home", "wave", "home", "disconnect"]
    assert len(prompts) == 1
    assert output[-1] == "Wave complete. Robot returned to neutral."


def test_cancelled_wave_returns_to_neutral_and_disconnects():
    adapter = FakeHardwareAdapter()

    result = run_hardware_demo(
        adapter,
        action="wave",
        confirm_fn=lambda _prompt: "no",
        output_fn=lambda _message: None,
    )

    assert result == 2
    assert adapter.events == ["connect", "home", "disconnect"]


def test_demo_disconnects_when_action_fails():
    adapter = FakeHardwareAdapter()

    def failing_wave():
        adapter.events.append("wave")
        raise RuntimeError("simulated UART failure")

    adapter.wave = failing_wave

    try:
        run_hardware_demo(
            adapter,
            action="wave",
            confirm_fn=lambda _prompt: "wave",
            output_fn=lambda _message: None,
        )
    except RuntimeError as error:
        assert str(error) == "simulated UART failure"
    else:
        raise AssertionError("Expected simulated UART failure")

    assert adapter.events[-1] == "disconnect"


def test_home_demo_does_not_request_wave_confirmation():
    adapter = FakeHardwareAdapter()

    result = run_hardware_demo(
        adapter,
        action="home",
        confirm_fn=lambda _prompt: (_ for _ in ()).throw(
            AssertionError("confirmation should not be requested")
        ),
        output_fn=lambda _message: None,
    )

    assert result == 0
    assert adapter.events == ["connect", "home", "disconnect"]


def test_demo_parser_supports_required_hardware_arguments():
    args = build_argument_parser().parse_args(
        [
            "--port",
            "/dev/ttyUSB4",
            "--lib",
            "/opt/robot/librobot_uart.so",
            "--action",
            "home",
            "--speed",
            "12",
        ]
    )

    assert args.port == "/dev/ttyUSB4"
    assert args.library_path == "/opt/robot/librobot_uart.so"
    assert args.action == "home"
    assert args.speed == 12

"""Operator-confirmed Linux UART gesture demo."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from ivastbot_hri.adapters.linux_uart_gesture_adapter import (
    DEFAULT_LIBRARY_PATH,
    DEFAULT_PORT,
    DEFAULT_SPEED,
    TRANSITION_DWELL,
    WAVE_DWELL,
    LinuxUARTGestureAdapter,
)


def run_hardware_demo(
    adapter: LinuxUARTGestureAdapter,
    action: str = "wave",
    *,
    confirm_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> int:
    """Run one operator-controlled action and always disconnect."""
    try:
        adapter.connect()
        output_fn("Connected. Moving to the verified neutral pose.")
        adapter.home()

        if action == "home":
            output_fn("Neutral pose command sent.")
            return 0

        confirmation = confirm_fn(
            "Robot is neutral. Type 'wave' to execute the verified wave: "
        )
        if confirmation.strip().lower() != "wave":
            output_fn("Wave cancelled by operator.")
            return 2

        adapter.wave()
        adapter.home()
        output_fn("Wave complete. Robot returned to neutral.")
        return 0
    finally:
        adapter.disconnect()


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--lib", dest="library_path", default=str(DEFAULT_LIBRARY_PATH))
    parser.add_argument("--action", choices=("wave", "home"), default="wave")
    parser.add_argument("--speed", type=int, default=DEFAULT_SPEED)
    parser.add_argument("--dwell", type=float, default=WAVE_DWELL)
    parser.add_argument(
        "--transition-dwell",
        type=float,
        default=TRANSITION_DWELL,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    adapter = LinuxUARTGestureAdapter(
        port=args.port,
        library_path=args.library_path,
        speed=args.speed,
        dwell=args.dwell,
        transition_dwell=args.transition_dwell,
    )
    try:
        return run_hardware_demo(adapter, action=args.action)
    except (RuntimeError, ValueError) as error:
        print(f"UART gesture demo failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

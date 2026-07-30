"""Configuration factory for local and real gesture adapters."""

from __future__ import annotations

import os
from collections.abc import Mapping

from ivastbot_hri.adapters.fake_gesture_adapter import FakeGestureAdapter
from ivastbot_hri.adapters.linux_uart_gesture_adapter import (
    DEFAULT_PORT,
    LinuxUARTGestureAdapter,
)

GESTURE_BACKEND_ENV_VAR = "HRI_GESTURE_BACKEND"
GESTURE_PORT_ENV_VAR = "HRI_GESTURE_PORT"
GESTURE_LIBRARY_ENV_VAR = "HRI_GESTURE_LIBRARY"


def create_gesture_adapter(
    backend: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    **uart_options,
):
    """Create the configured gesture adapter without connecting hardware."""
    environment = os.environ if environ is None else environ
    selected_backend = (
        backend
        if backend is not None
        else environment.get(GESTURE_BACKEND_ENV_VAR, "fake")
    )
    selected_backend = selected_backend.strip().lower()

    if selected_backend == "fake":
        return FakeGestureAdapter()

    if selected_backend == "uart":
        options = dict(uart_options)
        options.setdefault(
            "port",
            environment.get(GESTURE_PORT_ENV_VAR, DEFAULT_PORT),
        )
        configured_library = environment.get(GESTURE_LIBRARY_ENV_VAR)
        if configured_library:
            options.setdefault("library_path", configured_library)
        return LinuxUARTGestureAdapter(**options)

    raise ValueError(
        f"Unsupported gesture backend {selected_backend!r}. "
        "Expected 'fake' or 'uart'."
    )


__all__ = (
    "GESTURE_BACKEND_ENV_VAR",
    "GESTURE_LIBRARY_ENV_VAR",
    "GESTURE_PORT_ENV_VAR",
    "create_gesture_adapter",
)

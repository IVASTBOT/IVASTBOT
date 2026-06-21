"""Dependency-free adapter interfaces for HRI actions."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class FaceAdapter(Protocol):
    """Interface for adapters that handle robot face commands."""

    def send(self, command: str, payload: dict | None = None):
        """Send a face command."""


@runtime_checkable
class GestureAdapter(Protocol):
    """Interface for adapters that handle robot gesture commands."""

    def send(self, command: str, payload: dict | None = None):
        """Send a gesture command."""


@runtime_checkable
class NavigationAdapter(Protocol):
    """Interface for adapters that handle high-level navigation commands."""

    def send(self, command: str, payload: dict | None = None):
        """Send a navigation command."""


__all__ = (
    "FaceAdapter",
    "GestureAdapter",
    "NavigationAdapter",
)

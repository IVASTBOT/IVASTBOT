"""Local debug demo for FaceBridgeAdapter command mapping."""

from ivastbot_hri.adapters.face_bridge_adapter import FaceBridgeAdapter
from ivastbot_hri.core import keys


DEMO_ACTION_SEQUENCE = (
    keys.SHOW_NEUTRAL_FACE,
    keys.SHOW_HAPPY_FACE,
    keys.SHOW_THINKING_FACE,
    keys.SHOW_GUIDING_FACE,
    keys.LOOK_LEFT,
    keys.LOOK_RIGHT,
    keys.LOOK_CENTER,
)


def generate_demo_commands(adapter: FaceBridgeAdapter | None = None) -> list[dict]:
    """Generate local UI command dictionaries for the face bridge demo."""
    face_adapter = adapter or FaceBridgeAdapter()
    return [face_adapter.send(action_key) for action_key in DEMO_ACTION_SEQUENCE]


def main() -> int:
    """Print demo UI commands for quick local inspection."""
    for ui_command in generate_demo_commands():
        print(ui_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
face_controller.py
==================
Robot Face Emotion Controller
──────────────────────────────
Simple WebSocket server that bridges Python → robot_face.html

USAGE:
    1. Open robot_face.html in Chromium / browser.
    2. Start this server:  python face_controller.py
    3. Call emotion functions from your code:

        from face_controller import RobotFaceController
        face = RobotFaceController()
        face.happy()
        face.sad(duration_ms=3000)   # auto-return to neutral after 3s

REQUIREMENTS:
    pip install websockets

Phuong's integration example:
──────────────────────────────
    from face_controller import RobotFaceController
    face = RobotFaceController()

    if detected_face:
        face.happy()
    elif recognition_failed:
        face.sad()
    else:
        face.neutral()
"""

import asyncio
import json
import logging
import threading
import time
import webbrowser
from pathlib import Path

try:
    import websockets
except ImportError:
    raise SystemExit("Please install: pip install websockets")

logging.basicConfig(
    level=logging.INFO,
    format="[RobotFace] %(levelname)s %(message)s"
)
log = logging.getLogger("RobotFace")

# ──────────────────────────────────────────────────────────────
# WebSocket server (runs in a background thread)
# ──────────────────────────────────────────────────────────────
HOST = "localhost"
PORT = 9000
EMOTIONS = {"neutral", "bored", "happy", "sad", "annoyed"}


class _FaceServer:
    """Internal async WebSocket server – keeps track of connected clients."""

    def __init__(self):
        self._clients: set = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    # ── Lifecycle ──────────────────────────────────────────────
    def start(self):
        """Start the server in a background daemon thread."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="FaceServerLoop"
        )
        self._thread.start()
        # Give the server a moment to bind
        time.sleep(0.4)
        log.info(f"WebSocket server listening on ws://{HOST}:{PORT}")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        async with websockets.serve(self._handler, HOST, PORT):
            await asyncio.Future()  # run forever

    async def _handler(self, ws):
        self._clients.add(ws)
        log.info(f"Browser connected  ({len(self._clients)} client(s))")
        try:
            async for _ in ws:
                pass  # we don't need messages from the browser
        finally:
            self._clients.discard(ws)
            log.info(f"Browser disconnected ({len(self._clients)} client(s))")

    # ── Send ───────────────────────────────────────────────────
    def send(self, payload: dict):
        """Thread-safe send to all connected browsers."""
        if not self._loop:
            log.warning("Server not started – call .start() first")
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)

    async def _broadcast(self, payload: dict):
        if not self._clients:
            log.warning("No browser connected – message dropped")
            return
        msg = json.dumps(payload)
        dead = set()
        for ws in self._clients:
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        self._clients -= dead


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────
class RobotFaceController:
    """
    High-level controller for the robot face display.

    Example
    -------
    face = RobotFaceController()        # starts server automatically
    face.happy()
    face.bored()
    face.sad(duration_ms=4000)          # shows sad, then returns neutral
    face.set_emotion("annoyed")
    """

    def __init__(self, auto_start: bool = True, open_browser: bool = False):
        self._server = _FaceServer()
        if auto_start:
            self._server.start()
        if open_browser:
            html_path = Path(__file__).parent / "robot_face.html"
            webbrowser.open(html_path.as_uri())
            log.info(f"Opened: {html_path}")

    # ── Core method ────────────────────────────────────────────
    def set_emotion(self, emotion: str, duration_ms: int = 0):
        """
        Set the robot's face emotion.

        Parameters
        ----------
        emotion    : 'neutral' | 'bored' | 'happy' | 'sad' | 'annoyed'
        duration_ms: If > 0, auto-revert to neutral after this many ms.
        """
        emotion = emotion.lower().strip()
        if emotion not in EMOTIONS:
            raise ValueError(
                f"Unknown emotion '{emotion}'. Valid: {sorted(EMOTIONS)}"
            )
        payload = {"emotion": emotion}
        if duration_ms > 0:
            payload["duration"] = duration_ms
        self._server.send(payload)
        log.info(f"→ {emotion}" + (f" for {duration_ms}ms" if duration_ms else ""))

    # ── Convenience shortcuts ──────────────────────────────────
    def neutral(self):
        """Neutral/resting face – eyes open, gentle smile."""
        self.set_emotion("neutral")

    def bored(self):
        """Sleepy/bored face – heavy eyelids, Z Z Z floating."""
        self.set_emotion("bored")

    def happy(self, duration_ms: int = 0):
        """Happy face – curved eyes, big smile, floating hearts."""
        self.set_emotion("happy", duration_ms)

    def sad(self, duration_ms: int = 0):
        """Sad face – drooping eyes, tears, frown."""
        self.set_emotion("sad", duration_ms)

    def annoyed(self, duration_ms: int = 0):
        """Annoyed face – furrowed brows, squinting, grimace."""
        self.set_emotion("annoyed", duration_ms)


# ──────────────────────────────────────────────────────────────
# Stand-alone demo  (python face_controller.py)
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    face = RobotFaceController(open_browser=True)

    if len(sys.argv) > 1:
        # Quick CLI:  python face_controller.py happy
        face.set_emotion(sys.argv[1])
        time.sleep(1)
        sys.exit(0)

    # Interactive demo loop
    print("\n╔══════════════════════════════════════╗")
    print("║       Robot Face Controller          ║")
    print("╠══════════════════════════════════════╣")
    print("║  Commands: neutral bored happy       ║")
    print("║            sad     annoyed  quit     ║")
    print("╚══════════════════════════════════════╝\n")

    while True:
        try:
            cmd = input("emotion> ").strip().lower()
            if cmd in ("quit", "q", "exit"):
                print("Bye!")
                break
            elif cmd == "demo":
                for e in ["happy", "sad", "annoyed", "bored", "neutral"]:
                    face.set_emotion(e)
                    time.sleep(2.5)
            elif cmd:
                try:
                    face.set_emotion(cmd)
                except ValueError as err:
                    print(f"  ✗ {err}")
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

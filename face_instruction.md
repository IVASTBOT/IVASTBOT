# Robot Face UI — Walkthrough

## Files

| File | Purpose |
|------|---------|
| [`robot_face.html`](file:///C:/Users/tuant/.gemini/antigravity/scratch/robot-face/robot_face.html) | The face UI — open in Chromium fullscreen |
| [`face_controller.py`](file:///C:/Users/tuant/.gemini/antigravity/scratch/robot-face/face_controller.py) | Python WebSocket server + controller API |

---

## How It Works

```
robot_face.html  ←──WebSocket (ws://localhost:9000)──→  face_controller.py
   (Chromium)                                             (Python / ROS)
```

The HTML page auto-connects to the Python WebSocket server and reconnects if it drops. Python sends `{ "emotion": "happy" }` JSON messages.

---

## Setup

### 1. Install Python dependency
```bash
pip install websockets
```

### 2. Open the face on the robot screen
Open `robot_face.html` in Chromium. For the robot screen:
```bash
chromium-browser --kiosk --window-size=1024,600 /path/to/robot_face.html
```

### 3. Start the Python server
```bash
python face_controller.py
```

---

## Phuong's Integration API

```python
from face_controller import RobotFaceController

face = RobotFaceController()   # starts WebSocket server on port 9000

# ── 5 emotion functions ──────────────────────────────
face.neutral()                 # Resting face, gentle smile, blinking eyes
face.bored()                   # Heavy eyelids + floating Z z Z
face.happy()                   # Curved squint eyes + big smile + hearts
face.sad()                     # Drooping eyes, tears, frown
face.annoyed()                 # Angled angry brows, squint, grimace

# ── Generic setter ───────────────────────────────────
face.set_emotion("happy")
face.set_emotion("sad", duration_ms=3000)   # auto-return to neutral after 3s

# ── Example: face recognition flow ──────────────────
if face_detected and recognized:
    face.happy(duration_ms=4000)
elif face_detected and not recognized:
    face.sad(duration_ms=3000)
else:
    face.neutral()
```

---

## Emotion Reference

| Emotion | Eyes | Mouth | Special Effect |
|---------|------|-------|----------------|
| **Neutral** | Full rounded squares, slow blink | Gentle smile | Glow pulse, pupil follows cursor |
| **Bored** | Heavy top eyelid (62% closed) | Flat line | Floating Z z Z text |
| **Happy** | Squinted crescents (scaleY) | Wide smile | Floating ♡ hearts burst |
| **Sad** | Slight inward tilt, pupils down | Frown | Tear drops |
| **Annoyed** | Asymmetric angled eyelids (angry V) | Slight grimace | Face shakes on touch×4 |

---

## Built-in Behaviors

- **Auto-blink** every ~5s in neutral state
- **Pupil tracking** follows mouse/touch position (disabled in bored/annoyed)
- **Touch annoy** — tapping the screen 4+ times triggers annoyed state, auto-returns to neutral after 5s
- **Smooth transitions** — short white flash between emotion changes
- **WebSocket reconnect** — automatically reconnects to Python if connection drops

---

## Debug Mode

On the deployed robot, a hidden debug panel sits at the bottom (nearly invisible at 8% opacity). **Hover** over the bottom center of the screen to reveal 5 emotion buttons for quick manual testing. This won't show in normal robot operation.

---

## Running the Interactive CLI

```
$ python face_controller.py

╔══════════════════════════════════════╗
║       Robot Face Controller          ║
╠══════════════════════════════════════╣
║  Commands: neutral bored happy       ║
║            sad     annoyed  quit     ║
╚══════════════════════════════════════╝

emotion> happy
emotion> bored
emotion> demo      ← cycles all emotions
emotion> quit
```

You can also pass an emotion as a CLI argument:
```bash
python face_controller.py happy
```

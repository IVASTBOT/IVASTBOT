# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

iVASTBot is a ROS2 reception robot for the Vietnam Academy of Science and Technology (VAST). It combines autonomous navigation (SLAM + Nav2) with a real-time Vietnamese speech conversation pipeline (STT → LLM → TTS).

## Build commands

```bash
# Source ROS2 (required before any colcon/ros2 command)
source /opt/ros/humble/setup.bash

# Build entire workspace (run from ~/ivastbot_ws)
colcon build --symlink-install

# Build a single package
colcon build --symlink-install --packages-select <package_name>

# Source the workspace after building
source install/setup.bash
```

`--symlink-install` is important for Python packages — it means edits to `.py` files take effect without rebuilding.

## Launch commands

**Robot base** (motors + TF + lidar):
```bash
ros2 launch bringup bringup.launch.py [lidar_serial_port:=/dev/ttyUSB0]
```

**SLAM mapping** (adds scan_filter, slam_toolbox, gamepad teleop):
```bash
ros2 launch bringup slam_bringup.launch.py [lidar_serial_port:=/dev/ttyUSB0] [rviz:=false] [teleop:=false]
# Save map when done:
ros2 run nav2_map_server map_saver_cli -f ~/ivastbot_map
```

**Autonomous navigation** (requires saved map; run after bringup.launch.py):
```bash
ros2 launch navigation navigation.launch.py map:=/path/to/map.yaml \
    [initial_pose_x:=0.0] [initial_pose_y:=0.0] [initial_pose_yaw:=0.0]
```

**Conversation pipeline** (each node in its own terminal, after sourcing):
```bash
ros2 run conversation_workers stt_worker
ros2 run conversation_workers llm_worker
ros2 run conversation_workers tts_worker
ros2 run conversation_pipeline session_node
```

## Environment setup

The LLM worker requires an `.env` file with `OPENAI_API_KEY` (the TTS worker is fully local — see VieNeu below). It looks for it at `$WS_ROOT/.env` (default: `~/Documents/conversation_ws/.env`). Override with:
```bash
export WS_ROOT=~/ivastbot_ws
```

## Architecture

### Navigation stack

```
RPLidar A2M8 (/dev/ttyUSB0)
  → /scan_raw
  → scan_filter_node (removes self-scan using lidar-frame footprint box transform)
  → /scan
  → SLAM Toolbox (/map) | Nav2 AMCL (localization)

Gamepad / Nav2 goal
  → /cmd_vel
  → diff_drive_controller (ros2_control)
  → IDS830HW hardware interface (SLCAN/CAN bus via /dev/ttyACM0)
  → IDS830 motors (left CAN_ID=1, right CAN_ID=2)
  ← encoder feedback (registers 0xE8/0xE9) → odometry
```

The `ids830_hw` package (`src/ids830_hw/`) is a C++ `ros2_control` `SystemInterface`. It speaks IDS830 proprietary CAN protocol (not CANopen) over SLCAN serial. Key detail: motors must have PC mode unlocked (clear bit 5 of register 0x36) on every startup — this was discovered by reverse engineering and is not in the manual. Speed formula: `value = (RPM / 3000) * 8192`. Encoder reads are throttled to every 2nd control cycle (50 Hz effective) to reduce CAN bus congestion.

Robot URDF: 2 rear drive wheels + 2 front casters. Odometry calibration: actual odom reads ~1.83× the true distance, corrected by `left/right_wheel_radius_multiplier: 0.545` in `bringup/config/controllers.yaml`.

### Conversation pipeline

```
ReSpeaker mic array
  → VAD (/vad: Bool) + DOA (/doa_raw: Int32)
  → speech audio (/speech_audio: AudioData)
  → stt_worker (PhoWhisper vinai/PhoWhisper-base, HuggingFace pipeline)
  → /conversation/stt/final (SttFinal: text + audio_path + doa_deg)

session_node (conversation_pipeline)
  ← /conversation/stt/final
  → intercepts greetings ("xin chào") and exit phrases ("tạm biệt") without hitting LLM
  → /conversation/stt/filtered_final (normal utterances only)
  → /conversation/session/state (TRANSIENT_LOCAL, active/inactive)
  → /status_led (ColorRGBA: green=listening, blue=thinking, magenta=speaking, red=off)

llm_worker (conversation_workers)
  ← /conversation/stt/filtered_final
  → OpenAI GPT-4o streaming (Vietnamese, plain text — only . and , punctuation)
  → /conversation/llm/tokens (LlmToken: seq + delta + is_first + is_last)
  → /conversation/llm/final (LlmFinal: full round-trip text)
  (ConversationMemory keeps last 10 turns in-process; not persisted)

tts_worker (conversation_workers)
  ← /conversation/llm/tokens
  → accumulates tokens into sentence chunks (flush at "." ≥40 chars, or is_last)
  → VieNeu-TTS (vieneu.Vieneu, mode=turbo, CPU-only via GGUF/ONNX, 24 kHz mono)
  → sounddevice playback (blocking — runs in dedicated daemon thread, never in ROS callback)
  → /conversation/tts/status (state: speaking/idle)
```

Sessions are started/stopped via `/conversation/session/start` and `/conversation/session/stop` services. The session node uses `TRANSIENT_LOCAL` QoS for state so late-joining workers receive the current state immediately.

### Custom message types (`conversation_msgs`)

| Message | Fields |
|---|---|
| `SttFinal` | stamp, text, duration_s, audio_path, doa_deg |
| `SttPartial` | stamp, speaking, status_vi |
| `LlmToken` | stamp, seq, delta, is_first, is_last |
| `LlmFinal` | stamp, user_text, bot_text |
| `TtsStatus` | stamp, state, chunk_text |
| `SessionState` | active, reason |

Services: `StartSession`, `StopSession` (response: ok + message), `SpeakChunk`.

### Package map

| Package | Type | Purpose |
|---|---|---|
| `bringup` | Python | URDF, launch files, controller config |
| `ids830_hw` | C++ | ros2_control hardware plugin for IDS830 motors |
| `scan_filter` | Python | Self-scan removal: /scan_raw → /scan |
| `slam` | CMake | SLAM Toolbox config + launch wrapper |
| `navigation` | CMake | Nav2 config + launch with AMCL + initial pose |
| `gamepad` | C++ | Joystick → /cmd_vel teleop node |
| `conversation_msgs` | CMake | Custom msg/srv definitions |
| `conversation_pipeline` | Python | `session_node` — conversation state machine |
| `conversation_workers` | Python | `stt_worker`, `llm_worker`, `tts_worker` |
| `flydigi` | Python | Flydigi gamepad driver |
| `respeaker_ros` | Python | ReSpeaker 4-mic array (VAD, DOA, audio) |
| `sllidar_ros2` | C++ | RPLidar SDK + ROS2 node |
| `audio_common` | C++ | Generic audio capture/play |

## Key hardware

| Device | Port | Purpose |
|---|---|---|
| RPLidar A2M8 | `/dev/ttyUSB0` | 2D laser scan |
| SLCAN CAN adapter | `/dev/ttyACM0` | Motor CAN bus bridge |
| ReSpeaker 4-mic | USB | Mic array, VAD, DOA |
| IDS830 motors | CAN ID 1 (left), 2 (right) | Drive wheels |

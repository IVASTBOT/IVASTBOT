# ROS2 Conversation Workspace — `conversation_ws`

## Context

Port the existing Python-only Vietnamese voice-reception pipeline at `/home/duyroscube/Documents/STT/` into a ROS2 multi-worker architecture, mirroring the parallel-worker pattern proven in `/home/duyroscube/Documents/example_code_for_multipleAImodel_ros2` (6D pose estimation: separate worker processes, each with its model preloaded in `__init__`, orchestrator with `MultiThreadedExecutor` + `ReentrantCallbackGroup`).

**Why**: the current `STT/chatbot_ui.py` runs the full mic→STT→LLM→TTS loop in a single Python process with one Qt thread. Reloading models on restart is slow, scaling is hard, and there's no clean way to add other ROS2 modules (navigation, perception, the existing 6D pose system) into the same robot. Splitting into ROS2 nodes means each AI model is loaded once at boot, kept warm, and triggered via topics/services — the same pattern the user already validated for 6D pose.

**Goals**: low-latency conversation (token-streaming LLM → chunked TTS), keep the PyQt5 kiosk UI, use the **already-installed `respeaker_ros` driver** as the audio source (hardware VAD + beamforming + per-utterance buffering on `/speech_audio`), defer robot-arm gestures (out of scope for now), build inside the existing `/home/duyroscube/Documents/conversation_ws` workspace alongside `respeaker_ros`, leaving `STT/` untouched.

## Pre-existing in the workspace

`/home/duyroscube/Documents/conversation_ws/src/respeaker_ros/` is already built. Key facts to design against:

- **Node**: `ros2 run respeaker_ros respeaker_node` (single node, ament_python).
- **Publishes** (all 16 kHz, int16 mono in `audio_common_msgs/AudioData`):
  - `/audio` — continuous main-channel stream (~1024 frames / 64 ms per msg)
  - `/audio/channel0`..`/audio/channel5` — per-mic streams (rarely needed)
  - **`/speech_audio`** — *buffered per-utterance* audio, only emitted when hardware speech detector says an utterance has ended. This is exactly what `STT/stt_whisper.py:record_with_vad()` does manually.
  - `/vad` (`std_msgs/Bool`, TRANSIENT_LOCAL) — hardware voice-activity flag
  - `/doa_raw` (`std_msgs/Int32`), `/doa` (`geometry_msgs/PoseStamped`) — direction of arrival, useful later for head-look gestures
- **Subscribes**: `/status_led` (`geometry_msgs/ColorRGBA`) — LED ring control, great for kiosk visual feedback.
- **Tunable params**: `speech_prefetch=0.5`, `speech_continuation=0.5`, `speech_min_duration=0.1`, `speech_max_duration=7.0`, `update_period_s=0.1`, `main_channel=0`.
- **Onboard processing**: AEC, AGC, stationary + non-stationary noise suppression are all already enabled in firmware via the `RespeakerInterface` class — software denoise (`STT/denoise_audio.py`) is therefore **not needed** by default.

## Architecture overview

```
   respeaker_node (already built, 3rd-party)
   ┌──────────────────────────────────┐
   │ /speech_audio (per-utterance buf)│
   │ /vad (hw VAD bool)               │
   │ /doa_raw, /doa                   │
   │ ← /status_led (LED ring control) │
   └──────┬───────────────────────────┘
          │ audio_common_msgs/AudioData
          ▼
                  ┌─────────────────────────┐
                  │   chatbot_ui_node       │  PyQt5 + rclpy (side-thread spin)
                  │   (kiosk, 2 buttons)    │
                  └──────┬──────────────┬───┘
            services ↓                   ↑ topics (status, partials, finals, tokens)
                  ┌─────────────────────────┐
                  │   session_node          │  Owns session bool, greeting/exit
                  │  (orchestrator, thin)   │  shortcuts, drives /status_led
                  └─┬───────┬───────┬───────┘
   /session/state ↓   ↓       ↓       ↓ (TRANSIENT_LOCAL, late-join safe)
       ┌──────────┴┐ ┌┴────────┐ ┌┴─────────┐
       │stt_worker │ │llm_worker│ │tts_worker│  ← each is its own OS process,
       │ PhoWhisper│ │ gpt-4o   │ │ gpt-4o   │    model loaded once in __init__,
       │ (ROS audio│ │ stream   │ │ -mini-tts│    warmed up before service ready
       │   input)  │ │          │ │          │
       └────┬──────┘ └────┬─────┘ └────┬─────┘
            │ stt/final   │ llm/tokens │ tts/status
            └────────►────┴───►────────┘
```

Streaming semantics: PhoWhisper is seq2seq (no streaming decode), so STT only re-publishes the hardware VAD as *partials* (UI indicator) plus a single final transcript. LLM streams tokens to TTS, which buffers per sentence (`.` or ≥40 chars) and synthesises chunk-by-chunk so audio starts before the LLM finishes.

## Package layout

```
/home/duyroscube/Documents/conversation_ws/src/
├── respeaker_ros/                              # ALREADY EXISTS — do not modify
├── conversation_msgs/                          # NEW — CMake / rosidl
│   ├── CMakeLists.txt, package.xml
│   ├── msg/  SttPartial, SttFinal, LlmToken, LlmFinal, TtsStatus, SessionState
│   ├── srv/  StartSession, StopSession, SpeakChunk
│   └── action/ Converse.action  (defined, reserved for future programmatic clients)
├── conversation_workers/                       # NEW — ament_python
│   ├── package.xml, setup.py, setup.cfg, resource/conversation_workers
│   └── conversation_workers/
│       ├── stt_worker_node.py                  # subscribes /speech_audio + /vad
│       ├── llm_worker_node.py
│       ├── tts_worker_node.py
│       └── conversation_memory.py              # verbatim port of STT/conversation_memory.py
└── conversation_pipeline/                      # NEW — ament_python
    ├── package.xml, setup.py, setup.cfg, resource/conversation_pipeline
    ├── launch/bringup.launch.py                # launches respeaker_node + 3 workers + session
    ├── config/params.yaml
    └── conversation_pipeline/
        ├── session_node.py
        ├── chatbot_ui_node.py
        └── assets/logo.png                     # copied from STT/logo.png
```

`STT/denoise_audio.py` is **not** ported — respeaker firmware already runs AEC, AGC and noise suppression. Add a software denoise layer later only if recordings still sound bad after a real-environment test.

## ROS2 interfaces

| Interface | Fields |
|---|---|
| `msg/SttPartial` | `Time stamp`, `bool speaking`, `string status_vi` (RMS dropped — respeaker `/vad` is the source of truth) |
| `msg/SttFinal` | `Time stamp`, `string text`, `float32 duration_s`, `string audio_path`, `int32 doa_deg` (from latest `/doa_raw`, -1 if unknown) |
| `msg/LlmToken` | `Time stamp`, `uint32 seq`, `string delta`, `bool is_first`, `bool is_last` |
| `msg/LlmFinal` | `Time stamp`, `string user_text`, `string bot_text` |
| `msg/TtsStatus` | `Time stamp`, `string state` (`speaking`\|`idle`\|`error`), `string chunk_text` |
| `msg/SessionState` | `bool active`, `string reason` |
| `srv/StartSession` | `--- bool ok / string message` |
| `srv/StopSession` | `--- bool ok / string message` |
| `srv/SpeakChunk` | `string text --- bool ok / string message` |

## Topic & QoS map

| Topic | Type | Pub | Sub | QoS |
|---|---|---|---|---|
| `/speech_audio` | `audio_common_msgs/AudioData` | respeaker_node | stt | (driver default) |
| `/vad` | `std_msgs/Bool` | respeaker_node | stt, ui | RELIABLE, TRANSIENT_LOCAL, depth 1 |
| `/doa_raw` | `std_msgs/Int32` | respeaker_node | stt | RELIABLE, TRANSIENT_LOCAL, depth 1 |
| `/status_led` | `geometry_msgs/ColorRGBA` | session | respeaker_node | RELIABLE, depth 1 |
| `/conversation/session/state` | SessionState | session | stt, llm, tts, ui | RELIABLE, TRANSIENT_LOCAL, depth 1 |
| `/conversation/stt/partial` | SttPartial | stt | ui | BEST_EFFORT, depth 10 |
| `/conversation/stt/final` | SttFinal | stt | session, llm, ui | RELIABLE, depth 10 |
| `/conversation/stt/filtered_final` | SttFinal | session | llm | RELIABLE, depth 10 |
| `/conversation/llm/tokens` | LlmToken | llm, session* | tts, ui | RELIABLE, depth 100 |
| `/conversation/llm/final` | LlmFinal | llm | session, ui | RELIABLE, depth 10 |
| `/conversation/tts/status` | TtsStatus | tts | session, ui | RELIABLE, depth 10 |

\* `session_node` synthesises a single-token `LlmToken(is_last=True)` for greeting/exit shortcuts so TTS handles them via the same path.

Services hosted on `session_node`: `/conversation/session/start`, `/conversation/session/stop`, `/conversation/session/speak`.

## Workers

### `stt_worker_node.py`
- `__init__`: declare params (`whisper_model="vinai/PhoWhisper-base"`, `sample_rate=16000`, `enable_software_denoise=False`). Load HF pipeline (`transformers.pipeline("automatic-speech-recognition", model=...)`); JIT-warm with a 1-second silent dummy buffer before creating subscriptions. **No PyAudio, no WebRTC VAD, no energy gate** — those duties belong to the respeaker firmware now.
- **Subscribes**:
  - `/speech_audio` (`audio_common_msgs/AudioData`) — one full utterance per message, already VAD-gated by the hardware.
  - `/vad` (`std_msgs/Bool`, TRANSIENT_LOCAL) — re-publishes onto `/conversation/stt/partial` (`speaking=val, status_vi="Đang nghe..."` when true, `"Đang xử lý..."` when transitioning false).
  - `/doa_raw` (`std_msgs/Int32`, TRANSIENT_LOCAL) — caches latest direction; attached to `SttFinal.doa_deg`.
  - `/conversation/session/state` (TRANSIENT_LOCAL) — when inactive, drop incoming `/speech_audio` messages.
- **`/speech_audio` callback**: bytes → `np.frombuffer(..., dtype=np.int16)` → write `${WS_ROOT}/requests/<ts>/utt.wav` (16 kHz mono int16 via `soundfile.write`) → run PhoWhisper on the file → publish `SttFinal(text, duration_s, audio_path, doa_deg)`. Skip if `text.strip()` is empty (shows up as "Bạn nói rõ hơn được không?" partial). Optional software denoise step kept behind a default-off param.
- Executor: `MultiThreadedExecutor(num_threads=2)` + `ReentrantCallbackGroup` (multiple TRANSIENT_LOCAL subs + the heavy `/speech_audio` callback shouldn't block each other).
- Single-flight: a `threading.Lock` ensures one PhoWhisper inference at a time; if a new `/speech_audio` arrives during transcription, drop it and emit a "Đang xử lý..." partial (PhoWhisper-base on GPU is ~0.5-1× realtime so this is rare).

### `llm_worker_node.py`
- `__init__`: load `OPENAI_API_KEY` via `python-dotenv`, instantiate `OpenAI()` client, instantiate the ported `ConversationMemory(max_memory_size=10)`. Hardcode IVASTBOT VAST persona system prompt (copy verbatim from `STT/llm_module.py:40`) plus the punctuation constraint string.
- Subscribes `/conversation/stt/filtered_final` on `ReentrantCallbackGroup`. Single-flight: `threading.Lock` drops new utterances while a response is mid-stream.
- Callback: `chat.completions.create(model="gpt-4o", max_tokens=300, stream=True)`. For each delta apply punctuation filter `re.sub(r"[^\w\sÀ-ỹ.,]", "", delta)`, publish `LlmToken(seq, delta, is_first, is_last)`. After loop, publish `LlmFinal(user_text, bot_text)` and call `memory.add_interaction(user_text, bot_text)`.
- Executor: `MultiThreadedExecutor(num_threads=2)` so token publishing inside the callback doesn't deadlock.

### `tts_worker_node.py`
- `__init__`: instantiate `OpenAI()` client, set `voice="sage"`, `model="gpt-4o-mini-tts"`, store the Vietnamese voice instructions string (copy verbatim from `STT/tts_module.py:87-89`). Query default `sounddevice` device.
- Subscribes `/conversation/llm/tokens` on `ReentrantCallbackGroup`. Maintains a per-response token buffer. Flush rule: when buffer ends with `.` AND `len(buffer) >= tts_min_chunk_chars` (param, default 40) OR `is_last=True` and buffer non-empty → enqueue chunk on an internal `queue.Queue`, reset buffer.
- Dedicated **playback thread** pulls from queue: call OpenAI TTS streaming → wav bytes → `soundfile.read` → publish `TtsStatus("speaking", chunk_text)` → `sd.play(); sd.wait()` → publish `TtsStatus("idle", "")`. **Mandatory** — `sd.wait()` in a ROS callback would starve the executor even with reentrant groups.
- Executor: `MultiThreadedExecutor(num_threads=2)`.

## Orchestrator: `session_node.py`

Thin owner of cross-cutting state. Four responsibilities:
1. **Session boolean**: hosts `StartSession`/`StopSession` services, publishes `SessionState` on `/conversation/session/state` (TRANSIENT_LOCAL so workers joining late see current state immediately).
2. **Greeting shortcut**: subscribes `/conversation/stt/final`; if `text.lower().strip()` ∈ `{"xin chào", "xin chao"}` and a session is just starting → call internal `SpeakChunk("Xin chào, tôi là IVASTBOT…")` (bypass LLM); republish filtered transcript with text cleared.
3. **Exit shortcut**: if text ∈ `{"tạm biệt", "tam biet", "goodbye", "bye"}` → publish `SessionState(active=False, reason="exit_phrase")`, then `SpeakChunk("Tạm biệt.")`.
4. **LED feedback**: publishes `geometry_msgs/ColorRGBA` to `/status_led` based on state — green when idle/listening, blue when LLM streaming, magenta when TTS speaking, red when stopped. Reuses respeaker hardware as a visual indicator.

`SpeakChunk` service implementation: synthesise a single `LlmToken(seq=0, delta=text, is_first=True, is_last=True)` and publish to `/conversation/llm/tokens` so TTS handles it uniformly — no second TTS code path.

**Filtered-final republish (mandatory from day 1)**: `session_node` republishes every `/conversation/stt/final` it sees as `/conversation/stt/filtered_final` *unless* it matched a greeting/exit shortcut. `llm_worker` subscribes to `filtered_final`, never to `final`. This prevents the LLM from also responding when the user said "xin chào" or "tạm biệt".

Executor: `MultiThreadedExecutor(num_threads=4)` + `ReentrantCallbackGroup` on services and the SttFinal subscription.

## UI node: `chatbot_ui_node.py`

The trickiest integration is rclpy + Qt event loop in one process. **Canonical pattern** (do *not* try `spin_once` from a Qt timer):

```python
def main():
    rclpy.init()
    app = QApplication(sys.argv)
    node = ChatbotUiNode()                       # rclpy.Node with pyqtSignal members
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    window = ChatbotWindow(node)                 # connects node.signals → slots
    window.showFullScreen()
    rc = app.exec_()
    executor.shutdown(); rclpy.shutdown(); sys.exit(rc)
```

`ChatbotUiNode` defines `pyqtSignal`s (`partial_signal(str,float)`, `final_signal(str)`, `token_signal(str)`, `bot_final_signal(str)`, `tts_signal(str,str)`) and emits them from each ROS callback. Qt's auto-connect across threads delivers them safely to the GUI thread.

Layout reuses the look-and-feel of `STT/chatbot_ui.py:212-316`: header (logo + title + green/red indicator), chat QTextEdit, status label, two buttons "Bắt đầu trò chuyện" / "Kết thúc trò chuyện" → call `start_client.call_async()` / `stop_client.call_async()`. Logo loaded via `ament_index_python.get_package_share_directory('conversation_pipeline') + '/assets/logo.png'`. ESC closes window.

The `say_hi.py` psutil block from the original UI (`STT/chatbot_ui.py:149-194`) is dropped (out of scope).

## Build files

**`conversation_msgs/CMakeLists.txt`** — `rosidl_generate_interfaces` listing all 6 msg + 3 srv + 1 action files, `DEPENDENCIES builtin_interfaces action_msgs`, `ament_export_dependencies(rosidl_default_runtime)`.

**`conversation_workers/setup.py`** entry_points:
```python
'console_scripts': [
    'stt_worker = conversation_workers.stt_worker_node:main',
    'llm_worker = conversation_workers.llm_worker_node:main',
    'tts_worker = conversation_workers.tts_worker_node:main',
],
```
package.xml depends: `rclpy`, `std_msgs`, `audio_common_msgs`, `conversation_msgs`. Python deps installed via pip (system or venv): `openai`, `transformers`, `torch`, `sounddevice`, `soundfile`, `numpy`, `python-dotenv`. (PyAudio / webrtcvad / scipy are no longer needed — respeaker firmware replaces them.)

**`conversation_pipeline/setup.py`** entry_points: `session_node`, `chatbot_ui`. data_files: `launch/`, `config/`, `assets/`. Depends: `rclpy`, `std_msgs`, `geometry_msgs`, `conversation_msgs`, `python3-pyqt5`.

## Launch / bringup

`launch/bringup.launch.py` brings up **`respeaker_node` + `session_node` + 3 workers** as 5 OS processes, all with `parameters=[config/params.yaml]`. The respeaker `Node(package='respeaker_ros', executable='respeaker_node', parameters=[{'speech_min_duration': 0.3, 'speech_continuation': 0.6, 'speech_max_duration': 10.0}])` is started first (its hardware init is fast). Order otherwise doesn't matter — TRANSIENT_LOCAL session state handles late join. UI launched separately:

```bash
ros2 launch conversation_pipeline bringup.launch.py     # backend (incl. respeaker)
ros2 run    conversation_pipeline chatbot_ui            # kiosk
```

**Required env**:
- `OPENAI_API_KEY` (mandatory; loaded by llm_worker and tts_worker via dotenv)
- `ROS_DOMAIN_ID=42` (recommended pin)
- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` (better large-payload throughput)
- `WS_ROOT=/home/duyroscube/Documents/conversation_ws` (used for per-request workdirs under `${WS_ROOT}/requests/<ts>/`)

## Critical files to create

1. `src/conversation_workers/conversation_workers/stt_worker_node.py` — subscribes `/speech_audio` + `/vad` + `/doa_raw`, runs PhoWhisper, publishes partials and finals
2. `src/conversation_workers/conversation_workers/llm_worker_node.py` — streaming OpenAI client, ConversationMemory
3. `src/conversation_workers/conversation_workers/tts_worker_node.py` — token buffering, playback thread
4. `src/conversation_pipeline/conversation_pipeline/session_node.py` — session state, shortcuts, services, LED control
5. `src/conversation_pipeline/conversation_pipeline/chatbot_ui_node.py` — PyQt5 + rclpy bridge

## Reused functions (verbatim ports — do not rewrite)

| Source | Destination |
|---|---|
| `STT/conversation_memory.py` | `conversation_workers/conversation_workers/conversation_memory.py` (used inside `llm_worker_node`) |
| IVASTBOT system prompt — `STT/llm_module.py:40` and `VAST_INFO` block lines 14–15 | inlined in `llm_worker_node.py` |
| Vietnamese TTS voice instructions — `STT/tts_module.py:87-89` | inlined in `tts_worker_node.py` |
| Greeting/exit phrase sets — `STT/chatbot.py:63, 70` | inlined as constants in `session_node.py` |

**Not ported**: the entire `record_with_vad()` state machine (`STT/stt_whisper.py:96-169`), `denoise_audio.py`, PyAudio init, WebRTC VAD setup. The respeaker driver supersedes all of them.

## Verification

```bash
cd /home/duyroscube/Documents/conversation_ws
colcon build --symlink-install --packages-skip respeaker_ros   # already built
source install/setup.bash
export OPENAI_API_KEY=...
export ROS_DOMAIN_ID=42

# 1) Sanity-check the mic alone (before adding any of our nodes)
ros2 run respeaker_ros respeaker_node &
ros2 topic echo /vad                              # toggles when you speak
ros2 topic echo /speech_audio --no-arr            # one msg per utterance, large `data`
ros2 topic echo /doa_raw                          # angle in degrees

# 2) Bring up backend
pkill -f respeaker_node                            # bringup launches it itself
ros2 launch conversation_pipeline bringup.launch.py

# 3) Confirm conversation topics
ros2 topic list | grep -E "conversation|speech_audio|vad"
ros2 topic echo /conversation/stt/partial         # mirrors /vad transitions
ros2 topic echo /conversation/stt/final           # one msg per utterance
ros2 topic echo /conversation/llm/tokens          # bursty during response
ros2 topic echo /conversation/tts/status          # speaking/idle transitions
ros2 topic hz   /conversation/llm/tokens          # expect 30–80 Hz mid-response

# 4) Smoke test without UI
ros2 service call /conversation/session/start conversation_msgs/srv/StartSession {}
# speak "xin chào"  → hear greeting (no LLM call), LED green
# speak a question  → tokens stream, TTS speaks per sentence, LED magenta
# speak "tạm biệt"  → goodbye, session goes inactive, LED red

# 5) Full UI
ros2 run conversation_pipeline chatbot_ui
```

Per-stage isolation: replace any one worker with a stub publisher to confirm fan-out. To bypass the mic during dev, manually publish onto `/speech_audio` or `/conversation/stt/final` with `ros2 topic pub --once`.

## Risks & decisions

1. **PhoWhisper is non-streaming** — only the hardware VAD bool is streamed as partials. UI must show "Đang nghe…" → "Đang xử lý…" → final, not progressive text.
2. **TTS chunking by `.` alone sounds choppy** for short sentences. Mitigation: param `tts_min_chunk_chars=40` so short sentences merge.
3. **`sd.wait()` must run on a worker thread**, not in a ROS callback — non-negotiable.
4. **respeaker `speech_min_duration` / `speech_max_duration`** (default 0.1s / 7s) directly controls how short/long an utterance can be. The 7s default cuts off long Vietnamese sentences — bump to 10s in `params.yaml`. Tune on real hardware.
5. **respeaker udev rules**: README requires `respeaker_ros/config/*.rules` copied to `/etc/udev/rules.d/`. Verify (`ls /etc/udev/rules.d/ | grep -i respeaker`) before launch — without this the device opens but `is_voice()` returns garbage.
6. **AudioData payload size**: a 7s utterance = ~224 KB. Default ROS2 message size limit is fine but DDS QoS may need RELIABLE depth 1; CycloneDDS handles this best, hence the `RMW_IMPLEMENTATION` recommendation.
7. **ConversationMemory is no longer cross-process singleton** (unlike `STT/llm_module.py:12`) — only `llm_worker` holds it. Restart the worker to clear, or add a `/conversation/memory/clear` service later.
8. **Greeting/exit race** solved by routing llm_worker through `/conversation/stt/filtered_final` republished by session_node — mandatory, not optional.
9. **TRANSIENT_LOCAL session state and `/vad`** require matching durability on every subscriber — document and replicate.
10. **PyQt5 + rclpy bridge** is the single most error-prone piece — follow §UI node pattern exactly; don't `spin_once` from a Qt timer.
11. **Robot arm gestures are out of scope** — `STT/control.py` and `tts_module.robot_gesture` are intentionally not ported. Add as a 4th worker (`gesture_worker_node`) in a follow-up; subscribe to `/conversation/tts/status` and run gestures while `state == "speaking"`. The respeaker `/doa_raw` topic is a perfect bonus input for "look toward speaker" gestures.

## Out of scope (future work)

- 7-DOF arm gesture worker subscribing to `/conversation/tts/status` and `/doa_raw`.
- RAG over `informations.json` / `chunked_doc.json` (unused in current pipeline).
- A `/conversation/memory/clear` service.
- Programmatic clients via the reserved `Converse.action`.
- Software-side denoise fallback (only add if real-environment recordings still sound bad despite respeaker firmware processing).
</content>
</invoke>
#!/bin/bash
# Launch full iVASTBot pipeline in a tmux session (3x2 grid)
# The chatbot UI window opens automatically as a separate Qt window.

WS=/home/roscube/ivastbot_ws
SESSION=ivastbot

SETUP="cd $WS && source install/setup.bash && export WS_ROOT=$WS && export TRANSFORMERS_OFFLINE=1 && export HF_DATASETS_OFFLINE=1"

tmux kill-session -t $SESSION 2>/dev/null
tmux new-session -d -s $SESSION -x 240 -y 60

# ── Build 3x2 grid ────────────────────────────────────────────────────────────
tmux split-window -h -p 67 -t "$SESSION:0.0"
tmux split-window -h -p 50 -t "$SESSION:0.1"
tmux split-window -v -t "$SESSION:0.0"
tmux split-window -v -t "$SESSION:0.1"
tmux split-window -v -t "$SESSION:0.2"

# ── Pane layout ───────────────────────────────────────────────────────────────
# ┌─────────────┬─────────────┬─────────────┐
# │ 0: blink500 │   1: stt    │  2: session │
# ├─────────────┼─────────────┼─────────────┤
# │   3: llm    │   4: tts    │   5: ui     │
# └─────────────┴─────────────┴─────────────┘

tmux send-keys -t "$SESSION:0.0" "$SETUP && ros2 run blink500_ros blink500_node --ros-args -p capture_rate:=48000 -p device:='Blink500'" Enter
sleep 1
tmux send-keys -t "$SESSION:0.1" "$SETUP && ros2 run conversation_workers stt_worker" Enter
sleep 1
tmux send-keys -t "$SESSION:0.2" "$SETUP && ros2 run conversation_pipeline session_node" Enter
sleep 1
tmux send-keys -t "$SESSION:0.3" "$SETUP && ros2 run conversation_workers llm_worker" Enter
sleep 1
tmux send-keys -t "$SESSION:0.4" "$SETUP && ros2 run conversation_workers tts_worker" Enter
sleep 2

# UI pane: wait for STT to be ready (PhoWhisper warm-up takes ~10s), then open Qt window
tmux send-keys -t "$SESSION:0.5" "$SETUP && echo 'Waiting for STT to warm up...' && sleep 12 && ros2 run conversation_pipeline chatbot_ui" Enter

tmux select-pane -t "$SESSION:0.5"
tmux attach-session -t $SESSION

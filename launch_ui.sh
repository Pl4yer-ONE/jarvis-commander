#!/bin/bash
# Launch Maximus Terminal Dashboard

# Kill all previous UI components
pkill -f "overlay.py" || true
pkill -f "overlay_logs.py" || true
pkill -f "max_dashboard.py" || true
tmux kill-session -t max_dash 2>/dev/null || true

# Wait for process termination
sleep 1

# Create a tmux session with 3 panes
tmux new-session -d -s max_dash -n "Maximus" 'journalctl --user -u jarvis.service -f -o cat'
tmux split-window -h -t max_dash:0 'tail -F /home/dev/.gemini/antigravity/scratch/jarvis/data/chat_log.txt'
tmux split-window -v -t max_dash:0.0 'top'

# Rebalance panels for visual symmetry
tmux select-layout -t max_dash:0 tiled

# Launch a real floating terminal executing the dashboard
alacritty -t "Maximus Dashboard" -e tmux attach-session -t max_dash &

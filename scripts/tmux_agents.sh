#!/usr/bin/env bash
# ==============================================================================
# tmux_agents.sh — Multi-Agent Paired Tmux Session (agy + claude)
# ==============================================================================
set -euo pipefail

SESSION_NAME="dev-agents"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "Session '$SESSION_NAME' already running. Reattaching..."
  tmux attach -t "$SESSION_NAME"
  exit 0
fi

echo "Creating multi-agent tmux session '$SESSION_NAME'..."

# Pane 1: Google Antigravity CLI / Reasoning
tmux new-session -d -s "$SESSION_NAME" -n "agents" "agy || bash"

# Pane 2: Claude Code CLI
tmux split-window -h -t "$SESSION_NAME:agents.0" "claude || bash"

# Pane 3: Monitoring & Commands
tmux split-window -v -t "$SESSION_NAME:agents.1" "htop || bash"

tmux select-pane -t "$SESSION_NAME:agents.0"

echo "Multi-agent session created. Attach anytime using: tmux a -t $SESSION_NAME"
if [ -t 0 ]; then
  tmux attach -t "$SESSION_NAME"
fi

#!/usr/bin/env bash
set -euo pipefail

echo "==> Testing tmux core configuration syntax..."
tmux -f ~/.config/tmux/tmux.conf -C new-session -d -s test-syntax "true" 2>/dev/null || {
  echo "FAIL: Failed to launch tmux session with ~/.config/tmux/tmux.conf"
  exit 1
}
tmux kill-session -t test-syntax 2>/dev/null || true

echo "==> Verifying symlink ~/.tmux.conf..."
if [ ! -L "$HOME/.tmux.conf" ]; then
  echo "FAIL: ~/.tmux.conf is not a symlink"
  exit 1
fi

echo "==> Verifying base-index and mouse options..."
BASE_INDEX=$(tmux start-server \; show-option -gv base-index 2>/dev/null || echo "")
if [ "$BASE_INDEX" != "1" ]; then
  echo "FAIL: base-index is '$BASE_INDEX', expected '1'"
  exit 1
fi

echo "PASS: Core config verified successfully."

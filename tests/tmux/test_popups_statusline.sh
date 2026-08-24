#!/usr/bin/env bash
set -euo pipefail

echo "==> Testing popups and statusline configuration..."
if [ ! -f "$HOME/.config/tmux/conf.d/20-popups.conf" ]; then
  echo "FAIL: 20-popups.conf is missing"
  exit 1
fi

if [ ! -f "$HOME/.config/tmux/conf.d/30-statusline.conf" ]; then
  echo "FAIL: 30-statusline.conf is missing"
  exit 1
fi

if [ ! -f "$HOME/.config/tmux/cheatsheet.txt" ]; then
  echo "FAIL: cheatsheet.txt is missing"
  exit 1
fi

TEST_SOCK="tmux_test_popups_$$"
cleanup() {
  tmux -L "$TEST_SOCK" kill-server 2>/dev/null || true
}
trap cleanup EXIT

# Launch session in background to keep server alive during checks
tmux -L "$TEST_SOCK" -f ~/.config/tmux/tmux.conf new-session -d -s test-popups "sleep 30" 2>/dev/null || {
  echo "FAIL: Failed to parse updated config"
  exit 1
}

echo "==> Checking statusline options..."
POS=$(tmux -L "$TEST_SOCK" show-option -gv status-position 2>/dev/null || echo "")
if [ "$POS" != "bottom" ]; then
  echo "FAIL: status-position is '$POS', expected 'bottom'"
  exit 1
fi

STATUS_STYLE=$(tmux -L "$TEST_SOCK" show-option -gv status-style 2>/dev/null || echo "")
if [[ "$STATUS_STYLE" != *"bg=#1e1e2e"* ]]; then
  echo "FAIL: status-style is '$STATUS_STYLE', expected Catppuccin Dark Mocha '#1e1e2e'"
  exit 1
fi

echo "==> Verifying popup keybindings..."
KEYS=$(tmux -L "$TEST_SOCK" list-keys 2>/dev/null)
if ! echo "$KEYS" | grep -q "display-popup.*scratchpad"; then
  echo "FAIL: Scratchpad popup binding missing"
  exit 1
fi

if ! echo "$KEYS" | grep -q "cheatsheet.txt"; then
  echo "FAIL: Cheatsheet popup binding missing"
  exit 1
fi

if ! echo "$KEYS" | grep -q "display-popup.*lazygit"; then
  echo "FAIL: LazyGit popup binding missing"
  exit 1
fi

echo "PASS: Popups and statusline verified successfully."

#!/usr/bin/env bash
set -euo pipefail

echo "==> Testing TPM configuration and bootstrap..."

if [ ! -f "$HOME/.config/tmux/conf.d/90-plugins.conf" ]; then
  echo "FAIL: 90-plugins.conf is missing"
  exit 1
fi

if [ ! -f "$HOME/.config/tmux/tmux.conf" ]; then
  echo "FAIL: tmux.conf is missing"
  exit 1
fi

if [ ! -d "$HOME/.config/tmux/plugins/tpm" ]; then
  echo "Installing TPM for test..."
  git clone --depth 1 https://github.com/tmux-plugins/tpm "$HOME/.config/tmux/plugins/tpm" < /dev/null
fi

TEST_SOCK="tmux_test_tpm_$$"
cleanup() {
  tmux -L "$TEST_SOCK" kill-server 2>/dev/null || true
}
trap cleanup EXIT

# Test syntax and configuration parsing with isolated socket
tmux -L "$TEST_SOCK" -f ~/.config/tmux/tmux.conf new-session -d -s test-tpm "sleep 30" 2>/dev/null || {
  echo "FAIL: Failed to initialize tmux with TPM plugins"
  exit 1
}

echo "==> Verifying 15-plugin TPM suite in 90-plugins.conf..."
EXPECTED_PLUGINS=(
  "tmux-plugins/tpm"
  "tmux-plugins/tmux-sensible"
  "tmux-plugins/tmux-resurrect"
  "tmux-plugins/tmux-continuum"
  "tmux-plugins/tmux-sessionist"
  "christoomey/vim-tmux-navigator"
  "tmux-plugins/tmux-pain-control"
  "tmux-plugins/tmux-yank"
  "tmux-plugins/tmux-copycat"
  "tmux-plugins/tmux-open"
  "wfxr/tmux-fzf-url"
  "sainnhe/tmux-fzf"
  "tmux-plugins/tmux-logging"
  "tmux-plugins/tmux-prefix-highlight"
  "tmux-plugins/tmux-cpu"
)

for plugin in "${EXPECTED_PLUGINS[@]}"; do
  if ! grep -q "set -g @plugin '$plugin'" "$HOME/.config/tmux/conf.d/90-plugins.conf"; then
    echo "FAIL: Plugin '$plugin' missing in 90-plugins.conf"
    exit 1
  fi
done

echo "==> Verifying plugin options..."
RESURRECT_PANE=$(tmux -L "$TEST_SOCK" show-option -gv @resurrect-capture-pane-contents 2>/dev/null || echo "")
if [ "$RESURRECT_PANE" != "on" ]; then
  echo "FAIL: @resurrect-capture-pane-contents is '$RESURRECT_PANE', expected 'on'"
  exit 1
fi

CONTINUUM_RESTORE=$(tmux -L "$TEST_SOCK" show-option -gv @continuum-restore 2>/dev/null || echo "")
if [ "$CONTINUUM_RESTORE" != "on" ]; then
  echo "FAIL: @continuum-restore is '$CONTINUUM_RESTORE', expected 'on'"
  exit 1
fi

PREFIX_FG=$(tmux -L "$TEST_SOCK" show-option -gv @prefix_highlight_fg 2>/dev/null || echo "")
if [ "$PREFIX_FG" != "#11111b" ]; then
  echo "FAIL: @prefix_highlight_fg is '$PREFIX_FG', expected '#11111b'"
  exit 1
fi

echo "==> Verifying TPM keybindings..."
KEYS=$(tmux -L "$TEST_SOCK" list-keys 2>/dev/null)
if ! echo "$KEYS" | grep -q "install_plugins"; then
  echo "FAIL: TPM install_plugins keybinding missing"
  exit 1
fi

if ! echo "$KEYS" | grep -q "update_plugins"; then
  echo "FAIL: TPM update_plugins keybinding missing"
  exit 1
fi

if ! echo "$KEYS" | grep -q "clean_plugins"; then
  echo "FAIL: TPM clean_plugins keybinding missing"
  exit 1
fi

echo "PASS: TPM plugin suite initialized without error."

#!/usr/bin/env bash
# ==============================================================================
# test_agents_orchestrator.sh — Validation for Multi-Agent Orchestrator CLI
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ORCHESTRATOR="$SCRIPT_DIR/scripts/tmux_agents.sh"
TEST_ID="test-$$"
PAIR_SESSION="test-pair-$TEST_ID"
COMPANY_SESSION="test-company-$TEST_ID"
WT_BRANCH="test-wt-$TEST_ID"

cleanup() {
  echo "==> Cleaning up test artifacts..."
  tmux kill-session -t "$PAIR_SESSION" 2>/dev/null || true
  tmux kill-session -t "agent-company" 2>/dev/null || true
  tmux kill-session -t "$COMPANY_SESSION" 2>/dev/null || true
  "$ORCHESTRATOR" worktree clean "$WT_BRANCH" 2>/dev/null || true
  git branch -D "$WT_BRANCH" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Step 1: Checking script executable..."
if [ ! -x "$ORCHESTRATOR" ]; then
  echo "FAIL: Orchestrator script is not executable"
  exit 1
fi

echo "==> Step 2: Testing help/usage output..."
HELP_OUT=$("$ORCHESTRATOR" help)
if ! echo "$HELP_OUT" | grep -q "pair" || ! echo "$HELP_OUT" | grep -q "company" || ! echo "$HELP_OUT" | grep -q "worktree"; then
  echo "FAIL: Help output missing expected subcommands"
  exit 1
fi

echo "==> Step 3: Testing pair mode session creation..."
"$ORCHESTRATOR" pair "$PAIR_SESSION"
if ! tmux has-session -t "$PAIR_SESSION" 2>/dev/null; then
  echo "FAIL: Session '$PAIR_SESSION' was not created"
  exit 1
fi

PANE_COUNT=$(tmux list-panes -t "$PAIR_SESSION:agents" | wc -l)
if [ "$PANE_COUNT" -ne 3 ]; then
  echo "FAIL: Expected 3 panes in pair session, got $PANE_COUNT"
  exit 1
fi

echo "==> Step 4: Testing capture subcommand..."
CAPTURE_OUT=$("$ORCHESTRATOR" capture "$PAIR_SESSION:agents.0" 5)
echo "Capture output received (length: ${#CAPTURE_OUT})"

echo "==> Step 5: Testing clear-all subcommand..."
"$ORCHESTRATOR" clear-all "$PAIR_SESSION"

echo "==> Step 6: Testing status subcommand..."
STATUS_OUT=$("$ORCHESTRATOR" status)
if ! echo "$STATUS_OUT" | grep -q "$PAIR_SESSION"; then
  echo "FAIL: Status output does not list active test session"
  exit 1
fi

echo "==> Step 7: Testing kill subcommand..."
"$ORCHESTRATOR" kill "$PAIR_SESSION"
if tmux has-session -t "$PAIR_SESSION" 2>/dev/null; then
  echo "FAIL: Session '$PAIR_SESSION' was not terminated"
  exit 1
fi

echo "==> Step 8: Testing company mode session creation..."
"$ORCHESTRATOR" company 3
if ! tmux has-session -t "agent-company" 2>/dev/null; then
  echo "FAIL: Session 'agent-company' was not created"
  exit 1
fi

COMPANY_PANES=$(tmux list-panes -t "agent-company:company" | wc -l)
if [ "$COMPANY_PANES" -ne 4 ]; then
  echo "FAIL: Expected 4 panes (1 boss + 3 workers) in company session, got $COMPANY_PANES"
  exit 1
fi
"$ORCHESTRATOR" kill "agent-company"

echo "==> Step 9: Testing worktree add, list, and clean..."
"$ORCHESTRATOR" worktree add "$WT_BRANCH"
WT_LIST=$("$ORCHESTRATOR" worktree list)
if ! echo "$WT_LIST" | grep -q "$WT_BRANCH"; then
  echo "FAIL: Worktree '$WT_BRANCH' not listed in git worktree list"
  exit 1
fi

"$ORCHESTRATOR" worktree clean "$WT_BRANCH"
WT_LIST_AFTER=$("$ORCHESTRATOR" worktree list)
if echo "$WT_LIST_AFTER" | grep -q "$WT_BRANCH"; then
  echo "FAIL: Worktree '$WT_BRANCH' still present after clean"
  exit 1
fi

echo "==> Step 10: Verifying Prefix + A popup keybinding in 20-popups.conf..."
TEST_SOCK="tmux_test_orchestrator_$$"
cleanup_test_sock() {
  tmux -L "$TEST_SOCK" kill-server 2>/dev/null || true
}
tmux -L "$TEST_SOCK" -f ~/.config/tmux/tmux.conf new-session -d -s test-orch "sleep 10" 2>/dev/null || {
  echo "FAIL: Failed to parse tmux configuration"
  exit 1
}

KEYS=$(tmux -L "$TEST_SOCK" list-keys 2>/dev/null)
cleanup_test_sock

if ! echo "$KEYS" | grep -q "bind-key.*A.*tmux_agents.sh"; then
  echo "FAIL: Prefix + A popup binding for tmux_agents.sh menu is missing in tmux configuration"
  exit 1
fi

echo "PASS: Multi-Agent orchestrator suite passed all tests."

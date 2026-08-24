#!/usr/bin/env bash
# ==============================================================================
# tmux_agents.sh — Comprehensive Multi-Agent Orchestration Suite
# Supports: Dual-Agent Pairing, Boss-Worker Matrix, Worktrees, Telemetry
# ==============================================================================
set -euo pipefail

DEFAULT_SESSION="dev-agents"

usage() {
  cat << EOF
Usage: $(basename "$0") [command] [options]

Commands:
  pair [session_name]      Launch dual-agent pairing (agy + claude + monitor)
  company [n_workers]      Launch Boss-Worker matrix (1 Boss + N Workers)
  worktree add <branch>    Create isolated Git worktree and spawn agent window
  worktree list            List active agent worktrees
  worktree clean <branch>  Remove worktree directory and branch
  capture <target> [lines] Capture silent snapshot of agent pane buffer
  clear-all [session_name] Broadcast /clear to all worker panes
  status                   Show running agent sessions and panes
  kill [session_name]      Gracefully terminate agent session
  menu                     Interactive agent launcher menu (for popups)
  help                     Show this help message

EOF
  exit 0
}

cmd_pair() {
  local session="${1:-$DEFAULT_SESSION}"
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "==> Session '$session' already running. Reattaching..."
    if [ -t 0 ] && [ -t 1 ] && [ "${TERM:-}" != "dumb" ]; then
      tmux attach -t "$session" 2>/dev/null || true
    fi
    return 0
  fi

  echo "==> Creating dual-agent pairing session '$session'..."
  # Pane 1: Google Antigravity (Reasoning / Controller)
  tmux new-session -d -s "$session" -n "agents" "agy 2>/dev/null || bash"

  # Pane 2: Claude Code (Executor / Coder)
  tmux split-window -h -t "$session:agents" "claude 2>/dev/null || bash"

  # Pane 3: System & Process Telemetry
  tmux split-window -v -t "$session:agents" "btop 2>/dev/null || htop 2>/dev/null || top"

  # Focus reasoning controller pane (left pane)
  tmux select-pane -t "$session:agents.{top-left}"

  echo "✨ Pairing session created. Attach with: tmux a -t $session"
  if [ -t 0 ] && [ -t 1 ] && [ "${TERM:-}" != "dumb" ]; then
    tmux attach -t "$session" 2>/dev/null || true
  fi
}

cmd_company() {
  local n_workers="${1:-3}"
  local session="agent-company"
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "==> Company session '$session' already exists. Reattaching..."
    if [ -t 0 ] && [ -t 1 ] && [ "${TERM:-}" != "dumb" ]; then
      tmux attach -t "$session" 2>/dev/null || true
    fi
    return 0
  fi

  echo "==> Spawning Boss-Worker company matrix with $n_workers workers..."
  tmux new-session -d -s "$session" -n "company" "agy 2>/dev/null || bash"
  
  for ((i=1; i<=n_workers; i++)); do
    tmux split-window -v -t "$session:company" "claude 2>/dev/null || bash"
  done

  tmux select-layout -t "$session:company" tiled
  tmux select-pane -t "$session:company.{top-left}"

  echo "✨ Company session initialized with $n_workers workers."
  if [ -t 0 ] && [ -t 1 ] && [ "${TERM:-}" != "dumb" ]; then
    tmux attach -t "$session" 2>/dev/null || true
  fi
}

cmd_worktree() {
  local action="${1:-list}"
  local branch="${2:-}"
  local root_dir
  root_dir="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

  case "$action" in
    add|create)
      if [ -z "$branch" ]; then
        echo "Error: Branch name required. Example: $0 worktree add feature-auth"
        exit 1
      fi
      local wt_dir="$root_dir/.worktrees/$branch"
      echo "==> Creating isolated Git Worktree at '$wt_dir'..."
      mkdir -p "$root_dir/.worktrees"
      git worktree add -b "$branch" "$wt_dir" HEAD < /dev/null
      
      # Spawn window in current tmux session if attached
      if [ -n "${TMUX:-}" ]; then
        tmux new-window -n "wt:$branch" -c "$wt_dir" "claude 2>/dev/null || bash"
        echo "✨ Opened new tmux window 'wt:$branch' in worktree."
      else
        echo "✨ Worktree ready at $wt_dir. Start agent inside: cd $wt_dir && claude"
      fi
      ;;
    list)
      echo "==> Active Git Worktrees:"
      git worktree list
      ;;
    clean|remove)
      if [ -z "$branch" ]; then
        echo "Error: Branch name required to remove."
        exit 1
      fi
      local wt_dir="$root_dir/.worktrees/$branch"
      echo "==> Removing worktree '$wt_dir'..."
      git worktree remove "$wt_dir" --force 2>/dev/null || rm -rf "$wt_dir"
      git worktree prune < /dev/null
      echo "✨ Worktree cleaned."
      ;;
    *)
      echo "Unknown worktree action: $action"
      exit 1
      ;;
  esac
}

cmd_capture() {
  local target="${1:-$DEFAULT_SESSION:agents}"
  local lines="${2:-50}"
  if ! tmux capture-pane -t "$target" -p 2>/dev/null | tail -n "$lines"; then
    local fallback_target="${target%.0}"
    if [ "$fallback_target" != "$target" ]; then
      tmux capture-pane -t "$fallback_target" -p 2>/dev/null | tail -n "$lines" || true
    fi
  fi
}

cmd_clear_all() {
  local session="${1:-$DEFAULT_SESSION}"
  echo "==> Broadcasting /clear to all panes in '$session'..."
  local panes
  panes=$(tmux list-panes -t "$session" -F '#{pane_id}' 2>/dev/null || echo "")
  for p in $panes; do
    tmux send-keys -t "$p" "/clear" Enter 2>/dev/null || true
  done
  echo "✨ All panes cleared."
}

cmd_status() {
  echo "==> Active tmux sessions:"
  tmux list-sessions 2>/dev/null || echo "No active sessions."
}

cmd_kill() {
  local session="${1:-$DEFAULT_SESSION}"
  echo "==> Terminating session '$session'..."
  tmux kill-session -t "$session" 2>/dev/null || echo "Session '$session' not running."
}

cmd_menu() {
  cat << 'EOF'
=====================================================
          🤖 MULTI-AGENT WORKSPACE DASHBOARD
=====================================================
  [1] Launch Dual-Agent Pairing (agy + claude)
  [2] Launch Company Matrix (Boss + 3 Workers)
  [3] Create Isolated Git Worktree for Agent
  [4] Broadcast /clear to All Agent Panes
  [5] View System Telemetry (btop/htop)
  [6] Gracefully Terminate Workspace
  [q] Quit
=====================================================
EOF
  read -r -p "Select option [1-6]: " choice
  case "$choice" in
    1) cmd_pair ;;
    2) cmd_company 3 ;;
    3)
       read -r -p "Enter feature branch name: " fbranch
       if [ -n "$fbranch" ]; then cmd_worktree add "$fbranch"; fi
       ;;
    4) cmd_clear_all ;;
    5) btop 2>/dev/null || htop 2>/dev/null || top ;;
    6) cmd_kill ;;
    *) exit 0 ;;
  esac
}

# CLI Router
COMMAND="${1:-pair}"
shift || true

case "$COMMAND" in
  start|pair)       cmd_pair "${1:-}" ;;
  company)          cmd_company "${1:-3}" ;;
  worktree)         cmd_worktree "${1:-list}" "${2:-}" ;;
  capture)          cmd_capture "${1:-$DEFAULT_SESSION:agents}" "${2:-50}" ;;
  clear-all)        cmd_clear_all "${1:-$DEFAULT_SESSION}" ;;
  status)           cmd_status ;;
  kill)             cmd_kill "${1:-$DEFAULT_SESSION}" ;;
  menu)             cmd_menu ;;
  help|--help|-h)   usage ;;
  *)                usage ;;
esac

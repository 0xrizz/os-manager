---
name: tmux-agents
description: Use when launching a multi-agent terminal workspace, pairing Claude Code with Google Antigravity (agy), managing Boss-Worker matrices, orchestrating Git worktrees, or capturing agent telemetry in tmux
---

# Multi-Agent Tmux Session & Orchestration Skill

Orchestrates multi-pane terminal workflows pairing Claude Code with Google Antigravity (`agy`), Boss-Worker hierarchies, isolated Git Worktrees, and real-time telemetry in `tmux 3.5a`.

## Trigger Scenarios
- Initializing collaborative dual-agent pairing (`agy` + `claude` + telemetry)
- Launching scalable Boss-Worker agent companies (`company` mode)
- Creating isolated Git Worktrees for concurrent agent coding without file collision
- Capturing background buffer logs (`capture`) for silent audits
- Resetting context windows across all worker panes simultaneously (`clear-all`)
- Interactive agent workspace dashboard via floating popup (`prefix + A`)

## Invocation
```bash
${PROJECT_DIR:-.}/scripts/tmux_agents.sh [subcommand] [args]
```

## Subcommands & Options
| Subcommand | Arguments | Description |
| :--- | :--- | :--- |
| `start` / `pair` | `[session_name]` | Initializes 3-pane paired agent session (`agy`, `claude`, `btop`/`htop`) or reattaches |
| `company` | `[n_workers]` | Launches 1 Boss + N Worker panes in balanced tiled layout |
| `worktree add` | `<branch_name>` | Spawns isolated Git worktree in `.worktrees/<branch>` with dedicated agent window |
| `worktree list` | *(none)* | Lists all active agent worktrees |
| `worktree clean`| `<branch_name>` | Safely removes worktree directory and branch |
| `capture` | `<target> [lines]`| Silently grabs output buffer from target pane without terminal interruption |
| `clear-all` | `[session_name]` | Sends `/clear` to all panes to reset token context |
| `status` | *(none)* | Displays list of active agent sessions and panes |
| `kill` | `[session_name]` | Gracefully terminates target agent session |
| `menu` | *(none)* | Opens interactive TUI dashboard (bound to `prefix + A`) |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Authorized terminal workspace orchestrator managing user tmux sessions and sandboxed worktrees.

---
name: tmux-agents
description: Use when launching a multi-agent terminal workspace, pairing Claude Code with Google Antigravity (agy), or reattaching to an active multi-pane agent session
---

# Multi-Agent Tmux Session Skill

Orchestrates multi-pane terminal workflows pairing Claude Code with Google Antigravity (`agy`) and real-time resource telemetry in tmux.

## Trigger Scenarios
- Initializing a collaborative dual-agent pairing environment with Claude and Antigravity
- Attaching to an existing multi-agent development session (`dev-agents`)
- Checking status or gracefully terminating running agent workspaces
- Real-time system monitoring alongside active agent execution

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/tmux_agents.sh [subcommand]
```

## Subcommands & Options
| Subcommand | Description |
| :--- | :--- |
| *(none)* / `start` | Initializes the 3-pane paired agent session (`agy`, `claude`, `htop`) or reattaches if already running |
| `attach` | Attaches to an active multi-agent session |
| `status` | Checks status and lists running agent sessions |
| `kill` | Gracefully terminates the multi-agent session |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Authorized terminal workspace orchestrator managing user tmux sessions.

# /pair: Multi-Agent Tmux Session Orchestrator Command

Orchestrates multi-pane terminal workflows pairing Claude Code with Google Antigravity (`agy`) and real-time telemetry.

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/tmux_agents.sh "$@"
```

## Description
Manages tmux multi-agent workspaces:
- Layout configuration:
  - Main Left Pane: Claude Code interactive CLI session
  - Upper Right Pane: Google Antigravity (`agy`) interactive CLI session
  - Lower Right Pane: System diagnostics and resource monitoring (`htop` / `btop` / `vmstat`)
- Automates session creation, window splitting, and socket attachment

## Usage & Subcommands
- `start`: Initializes the 3-pane paired agent session
- `attach`: Attaches to an existing multi-agent session
- `status`: Checks status of active agent sessions
- `kill`: Gracefully terminates the multi-agent session

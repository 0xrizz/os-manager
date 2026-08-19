# /diag: System Diagnostics Command

Run full system health, resource consumption, systemd unit status, and runtime validation.

## Invocation
```bash
${CLAUDE_PROJECT_DIR}/scripts/sys_diag.sh "$@"
```

## Description
Executes comprehensive diagnostics on Debian WSL2 environment:
- Kernel, OS version, and uptime checks
- Memory (RAM/Swap) utilization and allocation
- Disk usage across ext4 root `/` and 9P Windows mounts (`/mnt/c`, `/mnt/d`)
- Active and failed systemd service units
- Installed runtime versions (Node.js, PNPM, Bun, Python UV, Tmux, AI CLIs)

## Flags & Arguments
- `--full`: Includes detailed network sockets and 9P filesystem latency checks
- `--json`: Outputs structured JSON telemetry for programmatic consumption

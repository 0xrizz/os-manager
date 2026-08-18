---
name: sys-diag
description: Use when diagnosing system health issues, checking RAM/swap pressure, inspecting storage utilization, verifying systemd service failures, or analyzing WSL2 kernel metrics
---

# System Diagnostics Skill

Comprehensive diagnostic engine for inspecting Debian WSL2 system health, resource headroom, running processes, and active systemd units.

## Trigger Scenarios
- High memory pressure or sluggish terminal response
- Investigating systemd unit degradation or crashed services
- Verifying WSL2 kernel, uptime, or network connectivity
- Periodic or pre-maintenance health baseline inspection

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/sys_diag.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Standard diagnostic output (kernel, memory, ext4 disk, top CPU/RAM processes, failed systemd units) |
| `--full` | Extended diagnostics including network listening sockets and 9P mount inspection |
| `--json` | Machine-readable JSON output for automated telemetry and tooling |

## Safety Classification
- **Tier 0 (Autonomous Read-Only)**: Non-destructive execution with zero side effects.

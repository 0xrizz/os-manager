# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment & Architecture Overview

`os-manager` is a workspace containing automation scripts and Claude skills for managing a Debian 13 (Trixie) WSL2 environment on Windows 11.

- **OS / Platform**: Debian GNU/Linux 13 (Trixie), WSL2 (Kernel 6.18.x) on Windows 11
- **Filesystem Mounts**: `/` (ext4 WSL root), `/mnt/c/` (Windows C:), `/mnt/d/` (Windows D: / Backups)
- **Runtimes & CLIs**: Node.js, PNPM, Bun, Python UV, Tmux, Cloudflare Wrangler, Claude Code, Antigravity (`agy`)

## Repository Structure

- `scripts/`: Modular Bash automation scripts for system maintenance, diagnostics, runtime updates, and backup helpers.
- `.claude/skills/`: Custom Claude Code skill definitions mapping to local maintenance scripts and the [obra/superpowers](https://github.com/obra/superpowers) agent methodology suite.
- `playbooks/`: Markdown runbooks and procedures for system recovery and service management.
- `backups/`: Local directory target for state and configuration backups.

## Installed Agent Skills (Superpowers & System)

### System Operations & Utilities
- **Diagnostics**: `./scripts/sys_diag.sh` (or `/sys-diag` skill)
- **Safe Cleanup**: `./scripts/clean_system.sh` (or `/clean-system` skill)
- **Update Runtimes**: `./scripts/update_runtimes.sh` (or `/update-runtimes` skill)
- **Multi-Agent Session**: `./scripts/tmux_agents.sh` (or `/tmux-agents` skill)
- **WSL Backup Snapshot**: `./scripts/wsl_snapshot.sh` (or `/wsl-snapshot` skill)

### Superpowers Methodology Skills
- `/brainstorming`: Requirements exploration, design refinement, visual companion server.
- `/writing-plans` & `/executing-plans`: Incremental, test-driven implementation planning & execution.
- `/subagent-driven-development` & `/dispatching-parallel-agents`: Parallel subagent task orchestration.
- `/test-driven-development`: Red-Green-Refactor testing discipline.
- `/systematic-debugging`: Root cause tracing and test pollution detection.
- `/requesting-code-review` & `/receiving-code-review`: Rigorous code review workflows.
- `/verification-before-completion`: Evidence-first task completion gating.
- `/using-git-worktrees` & `/finishing-a-development-branch`: Git isolation and merge workflow.
- `/writing-skills`: Skill authoring and behavioral testing framework.

## Safety & Execution Rules

1. **Safe / Autonomous Operations**:
   - Read-only diagnostics (`free`, `df`, `systemctl status`, `uname`, network checks).
   - Standard cache cleanups (`uv cache clean`, `pnpm store prune`, `sudo apt clean`).
   - Repository metadata updates (`sudo apt update`).
2. **Explicit Confirmation Required**:
   - Destructive commands (`rm -rf` on root directories, `sudo apt purge`).
   - Stopping/restarting core systemd services.
   - WSL instance lifecycle operations (shutdown, unregister).
   - Overwriting configuration dotfiles (`~/.bashrc`, `~/.tmux.conf`).
3. **Cross-Mount I/O Rules**:
   - Heavy I/O workloads (e.g. `node_modules`, python virtualenvs) should reside on native ext4 (`/home/rizz/`) rather than 9P mounts (`/mnt/c/`, `/mnt/d/`).
   - All shell scripts must maintain LF line endings and executable permissions (`chmod +x`).

# Specification: os-manager Vision, Mission, and Responsibilities Blueprint

- **Date:** 2026-08-18
- **Scope:** Workspace Architecture & System Governance (`/home/rizz/dev/os-manager`)
- **Status:** Approved

---

## 1. Executive Summary & Philosophy

`os-manager` is the unified control plane and automation hub for managing a Debian 13 (Trixie) WSL2 environment hosted on Windows 11. It bridges bare-metal Linux OS maintenance with AI-assisted software engineering workflows (Claude Code, Google Antigravity `agy`, and the Superpowers agentic framework).

---

## 2. Vision & Mission

### Vision
> To make the Debian 13 WSL2 environment a self-maintaining, high-performance, and resilient AI-assisted development operating system that seamlessly orchestrates multi-agent engineering workflows.

### Mission
1. **Autonomous System Health & Resource Optimization**: Continuously monitor and preserve system health, RAM allocation, and ext4 storage efficiency without human friction.
2. **Unified AI Agent Control Plane**: Serve as the orchestration hub for multi-agent pairing, custom skills, and engineering methodology enforcement.
3. **Reproducible Runtime Management**: Standardize and automate rolling updates across core developer runtimes (Node.js, PNPM, Bun, Python UV, Cloudflare, AI CLIs).
4. **Resilient Disaster Recovery**: Provide reliable, point-in-time snapshot strategies and dotfile synchronization between WSL and host mounts.

---

## 3. Four Core Architectural Pillars

```text
               ┌──────────────────────────────────────────────┐
               │         os-manager: Unified Hub              │
               └──────────────────────┬───────────────────────┘
                                      │
       ┌──────────────────┬───────────┴──────────┬──────────────────┐
       ▼                  ▼                      ▼                  ▼
┌──────────────┐   ┌──────────────┐       ┌──────────────┐   ┌──────────────┐
│  Pillar 1:   │   │  Pillar 2:   │       │  Pillar 3:   │   │  Pillar 4:   │
│  OS Health   │   │  AI Agent    │       │  Runtimes    │   │  Backup &    │
│  & Cleanups  │   │  Hub & Skills│       │  & Tooling   │   │  Disaster Rec│
└──────────────┘   └──────────────┘       └──────────────┘   └──────────────┘
```

### Pillar 1: OS Health & Storage Lifecycle
- **Autonomous & Scheduled Maintenance**: Automated periodic cache pruning (`apt autoremove/clean`, `uv cache clean`, `pnpm store prune`) via cron / systemd user timers.
- **On-Demand Diagnostics**: Comprehensive inspection (`scripts/sys_diag.sh`, `/sys-diag` skill, `/diag` command) covering kernel, memory, disk, network, and systemd units.
- **Resource Reclaim**: Memory compaction and temporary file eviction (`scripts/clean_system.sh`, `/clean-system` skill, `/clean` command) to maintain lightweight WSL2 performance.

### Pillar 2: AI Multi-Agent & Superpowers Orchestration Hub
- **Paired Development Sessions**: Launch coordinated tmux layouts (`scripts/tmux_agents.sh`, `/tmux-agents` skill, `/pair` command) pairing Claude Code with Antigravity (`agy`) and telemetry monitoring.
- **Claude Code Agent Harness & Security Engine**: Governed by `docs/superpowers/specs/2026-08-18-claude-harness-architecture.md` featuring 4-Tier Security Guardrails (Exit 2 blocks), closed-loop auto-healing quality gates, and zero-copy SSOT symlink synchronization (`scripts/sync_agent_skills.sh`).
- **Superpowers Methodology Suite**: Host and enforce the Superpowers development lifecycle under `.claude/skills/`:
  - Requirements & Design: `/brainstorming`
  - Planning & Execution: `/writing-plans`, `/executing-plans`, `/subagent-driven-development`, `/dispatching-parallel-agents`
  - Quality Discipline: `/test-driven-development`, `/systematic-debugging`
  - Verification & Delivery: `/verification-before-completion`, `/requesting-code-review`, `/receiving-code-review`, `/using-git-worktrees`, `/finishing-a-development-branch`

### Pillar 3: Runtime & Toolchain Maintenance
- **Coordinated Upgrades**: Single-command orchestrator (`scripts/update_runtimes.sh`, `/update-runtimes` skill, `/upgrade` command) updating:
  - System packages (`apt`)
  - Node / NVM & PNPM (Corepack)
  - Bun runtime
  - Astral Python UV
  - Global AI & Cloud tooling (`@anthropic-ai/claude-code`, `wrangler`, `agy`)
- **Version Integrity**: Ensure all tools are accessible in `$PATH` across interactive and subagent shells.

### Pillar 4: State Protection & Disaster Recovery
- **Dotfiles Sync & Backup**: Safeguard user configurations (`~/.bashrc`, `~/.tmux.conf`, `~/.gitconfig`) into `backups/dotfiles/` via `scripts/dotfiles_sync.sh` (`/dotfiles` command) with diff checks prior to applying modifications.
- **WSL2 Snapshot Protocol**: Facilitate safe, full-distro tarball exports (`scripts/wsl_snapshot.sh`, `/wsl-snapshot` skill, `/snapshot` command) targeting Windows storage (`/mnt/d/wsl_backup`).
- **Recovery Playbooks**: Maintain actionable markdown playbooks under `playbooks/` for environment bootstrapping and systemd recovery.

---

## 4. Execution Guardrails & Boundary Rules

1. **Safety Separation**:
   - **Autonomous (Safe)**: Non-destructive diagnostics, cache cleaning, package metadata updates.
   - **Explicit Confirmation (Gated)**: Systemd service stops/restarts, package purges, WSL shutdown/unregister, dotfile overwrites.
2. **Filesystem Isolation**:
   - High-throughput developer workloads (virtualenvs, node_modules) remain on native ext4 (`/home/rizz/`).
   - Backups and exports reside on NTFS mounts (`/mnt/d/`).
   - Application project source code outside `os-manager` is never modified unless requested.

---

## 5. Roadmap & Next Evolutions

- **Phase 1 [Completed]**: Implement Claude Code Agent Harness (`docs/superpowers/specs/2026-08-18-claude-harness-architecture.md`), dotfiles sync script (`scripts/dotfiles_sync.sh`), custom commands palette (`/diag`, `/clean`, `/upgrade`, `/snapshot`, `/dotfiles`, `/pair`, `/harness-check`), and Multi-Agent SSOT bridge (`scripts/sync_agent_skills.sh`).
- **Phase 2**: Add systemd / cron timer definitions for background safe maintenance and create recovery playbook (`playbooks/dotfiles_sync.md`).
- **Phase 3**: Create performance tuning utility (`scripts/perf_tune.sh`) for measuring I/O latency between ext4 and 9P mounts.

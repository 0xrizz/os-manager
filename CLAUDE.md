# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment and Architecture Overview

`os-manager` is the control plane and automation hub for managing a Debian 13 (Trixie) WSL2 environment on Windows 11.

- **OS / Platform**: Debian GNU/Linux 13 (Trixie), WSL2 (Kernel 6.18.x) on Windows 11 Host
- **Filesystem Mounts**:
  - `/` (Native ext4 WSL root): Primary high-performance domain for repositories, virtual environments, and builds.
  - `/mnt/c/` (Windows Host C:): Read-only host inspection. Direct writes to Windows system directories are hard-blocked.
  - `/mnt/d/` (Windows Host D:): Dedicated disaster recovery and backup storage (`/mnt/d/wsl_backup`).
- **Runtimes and CLIs**: Node.js, PNPM, Bun, Python UV, Tmux, Cloudflare Wrangler, Claude Code CLI, Google Antigravity (`agy`), Agent-Style CLI (`agent-style`).

---

## Common Development and Operational Commands

### Testing and Validation
- Run master harness test suite (50 assertions): `./tests/test_harness.sh`
- Run individual test suites:
  - Inter-Agent Message Bus unit tests: `python3 -m unittest tests/test_agent_bus.py`
  - Disaster Recovery Provisioning tests: `./tests/test_bootstrap.sh`
  - Prometheus metrics exporter tests: `python3 -m unittest tests/test_metrics_exporter.py`
  - Desktop notification bridge tests: `./tests/test_notify_host.sh`
  - Host disk compaction tests: `./tests/test_disk_compaction.sh`
  - Agent workspace virtualization sandbox tests: `./tests/test_sandbox.sh`
  - Cross-distribution abstraction tests: `./tests/test_distro.sh`
  - Hook latency monotonic tracing tests: `./tests/test_hook_tracing.sh`
- Run full harness self-check and symlink validation: `./scripts/harness_check.sh`
- Audit Markdown prose against writing rules: `agent-style review --audit-only <file.md>`
- Sync multi-agent skills to Universal Agent and Antigravity: `./scripts/sync_agent_skills.sh`

### Pillar Automation Scripts
- Inter-Agent Message Bus daemon: `python3 ./scripts/agent_bus.py [--socket-path <path>]`
- Inter-Agent message publisher client: `./scripts/bus_send.sh [--topic <topic>|--to <agent>] --payload '<json>'`
- Automated WSL2 disaster recovery provisioner: `powershell.exe -ExecutionPolicy Bypass -File ./scripts/bootstrap_wsl.ps1 [-SnapshotPath <path>] [-DryRun]`
- Linux post-bootstrap verification agent: `./scripts/post_bootstrap.sh [--audit-only]`
- System diagnostics and resource metrics: `./scripts/sys_diag.sh [--full|--json]`
- Zero-dependency Prometheus metrics exporter: `python3 ./scripts/metrics_exporter.py [--port 9100]`
- Windows desktop toast notification bridge: `./scripts/notify_host.sh --title "..." --message "..." [--type info|warning|error]`
- Automated host VHDX disk compaction: `./scripts/compact_host_disk.sh [--dry-run|--threshold-gb 10]`
- Rootless Podman agent workspace sandbox: `./scripts/sandbox_exec.sh --workdir <dir> -- <cmd>`
- Hook latency benchmark analyzer: `./scripts/hook_benchmark.sh [--samples N|--hook <name>|--json|--assert-p99]`
- Safe cache and package cleanup: `./scripts/clean_system.sh [--dry-run|--all|--compact]`
- Runtime and toolchain updates: `./scripts/update_runtimes.sh [--check]`
- Disaster recovery snapshot to `/mnt/d/`: `./scripts/wsl_snapshot.sh [--verify|--prune]`
- Dotfiles backup, diff, and restore: `./scripts/dotfiles_sync.sh [backup|diff|restore]`
- Multi-agent paired Tmux workspace: `./scripts/tmux_agents.sh [start|attach]`
- Filesystem I/O performance benchmark: `./scripts/perf_tune.sh [--quick|--json]`
- Systemd user timer manager: `./scripts/manage_timers.sh [status|install|uninstall|enable|disable]`
- Repository batch migration to ext4: `./scripts/migrate_repos.sh`

---

## Repository Structure

```text
os-manager/
├── .agents/
│   └── skills/                  # Relative symlinks to .claude/skills/ (Universal Agent standard)
├── .claude/
│   ├── agents/                  # Custom subagent definitions (security-auditor, system-operator)
│   ├── commands/                # Custom slash command definitions (/diag, /clean, /perf, etc.)
│   ├── rules/                   # Modular prompt rules (WSL boundaries, safety tiers, error recovery)
│   ├── skills/                  # Master Single Source of Truth (SSOT) skill definitions (22 skills)
│   └── settings.json            # Master harness configuration (permissions, hooks, env)
├── backups/
│   ├── dotfiles/                # Backed-up dotfiles managed via /dotfiles
│   └── logs/                    # Audit logs, error telemetry, and compact snapshots
├── playbooks/                   # Markdown runbooks and disaster recovery procedures
├── scripts/
│   ├── hooks/                   # Deterministic lifecycle hooks (PreToolUse, PostToolUse, etc.)
│   │   └── lib/
│   │       └── trace_helper.sh  # Nanosecond hook execution monotonic tracing library
│   ├── lib/
│   │   └── distro.sh            # Zero-dependency cross-distro detection & package abstraction
│   ├── agent_bus.py             # Asynchronous JSON-RPC 2.0 Unix socket message broker
│   ├── bootstrap_wsl.ps1        # Windows host PowerShell WSL2 disaster recovery provisioner
│   ├── bus_send.sh              # Non-blocking fail-safe CLI publisher for agent bus
│   ├── clean_system.sh          # Safe cache & package cleanup script
│   ├── compact_host_disk.sh     # Host VHDX slack space compaction utility
│   ├── dotfiles_sync.sh         # Dotfiles backup, diff, and restore script
│   ├── harness_check.sh         # Harness end-to-end self-check runner
│   ├── hook_benchmark.sh        # Hook performance & latency percentile analyzer
│   ├── manage_timers.sh         # Systemd user timer & service manager
│   ├── metrics_exporter.py      # Prometheus 0.0.4 metrics daemon (127.0.0.1:9100)
│   ├── migrate_repos.sh         # Batch repository migration utility (NTFS -> ext4)
│   ├── notify_host.sh           # Windows WinRT desktop toast notification dispatcher
│   ├── perf_tune.sh             # Filesystem I/O performance benchmark script
│   ├── post_bootstrap.sh        # Linux first-boot verification and self-healing agent
│   ├── sandbox_exec.sh          # Rootless Podman agent isolation wrapper
│   ├── sync_agent_skills.sh     # Multi-agent SSOT symlink synchronization script
│   ├── sys_diag.sh              # System diagnostic & health inspection script
│   ├── tmux_agents.sh           # Multi-agent paired tmux workspace manager
│   ├── update_runtimes.sh       # Runtimes & toolchains update coordinator
│   └── wsl_snapshot.sh          # WSL disaster recovery snapshot script
├── systemd/
│   ├── agent-bus.service        # Systemd user service unit for inter-agent message bus
│   ├── os-maintenance.service   # Systemd user service unit for daily maintenance
│   ├── os-maintenance.timer     # Systemd user timer unit for scheduled maintenance
│   └── os-metrics-exporter.service # Systemd user service unit for metrics exporter
├── tests/
│   ├── test_agent_bus.py        # Unit tests for Inter-Agent Message Bus (10 tests)
│   ├── test_bootstrap.sh        # Unit tests for Automated Disaster Recovery Provisioning (15 assertions)
│   ├── test_disk_compaction.sh  # Unit tests for host disk compaction
│   ├── test_distro.sh           # Mocked cross-distribution unit test suite (13 assertions)
│   ├── test_harness.sh          # Master harness integration test suite (50 assertions)
│   ├── test_hook_tracing.sh     # Hook tracing & latency benchmark test suite (12 assertions)
│   ├── test_metrics_exporter.py # Unit tests for Prometheus metrics exporter (11 tests)
│   ├── test_notify_host.sh      # Unit tests for Windows toast notification bridge (15 tests)
│   └── test_sandbox.sh          # Unit tests for agent workspace virtualization (19 tests)
└── CLAUDE.md                    # Project guidance and governance rules
```

---

## Claude Code Agent Harness Architecture

The repository implements a **Claude-First Single Source of Truth (SSOT)** harness architecture featuring deterministic lifecycle hooks, a 4-tier security matrix, auto-healing static analysis, custom slash commands, and multi-agent interoperability.

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                CLAUDE-FIRST AGENT HARNESS TOPOLOGY                                  
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                               │
 ┌─────────────────────────────────────────────▼──────────────────────────────────────────────────────┐
 │ HARNESS CONFIGURATION & GOVERNANCE LAYER                                                            │
 │ • .claude/settings.json (Permissions, Env, Hook Registrations)                                     │
 │ • CLAUDE.md & .claude/rules/ (WSL Boundaries, Safety Tiers, Error Recovery Protocols)             │
 └─────────────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                               │
        ┌──────────────────────────────────────┼──────────────────────────────────────┐
        ▼                                      ▼                                      ▼
 ┌──────────────┐                       ┌──────────────┐                       ┌──────────────┐
 │  LIFECYCLE   │                       │    CUSTOM    │                       │ MULTI-AGENT  │
 │    HOOKS     │                       │   COMMANDS   │                       │ INTEROP &    │
 │   ENGINE     │                       │  & SKILLS    │                       │ SUBAGENTS    │
 ├──────────────┤                       ├──────────────┤                       ├──────────────┤
 │•SessionStart │                       │• /diag       │                       │•.claude/     │
 │•PreToolUse   │                       │• /clean      │                       │  skills/     │
 │•PostToolUse  │                       │• /upgrade    │                       │•.agents/     │
 │•PostFailure  │                       │• /snapshot   │                       │  skills/     │
 │•PreCompact   │                       │• /dotfiles   │                       │•~/.gemini/   │
 │•SessionEnd   │                       │• /pair       │                       │  config/     │
 │              │                       │• /harness-   │                       │  skills/     │
 │              │                       │  check       │                       │•.claude/     │
 │              │                       │              │                       │  agents/     │
 └──────────────┘                       └──────────────┘                       └──────────────┘
```

### 1. Lifecycle Hooks Engine (`scripts/hooks/`)

Registered in `.claude/settings.json` and executed deterministically using `${CLAUDE_PROJECT_DIR}` variable interpolation:

- **`SessionStart`** (`scripts/hooks/session_preflight.sh`): Checks RAM headroom (>300MB), verifies CLI binaries (`jq`, `python3`, `uv`, `node`), triggers multi-agent symlink sync, and logs to `backups/logs/harness_audit.jsonl`.
- **`PreToolUse`** (`scripts/hooks/pre_tool_guard.sh`): Evaluates all `Bash`, `Edit`, and `Write` invocations against the 4-Tier Security Matrix. Exits with code `2` on invariant violations to block execution deterministically with actionable `stderr` feedback.
- **`PostToolUse`** (`scripts/hooks/post_tool_lint.sh`): Auto-healing quality gate for file modifications (`.sh`, `.json`, `.py`). Validates syntax via `bash -n`, `shellcheck`, `jq empty`, and `python3 -m py_compile`. Returns Exit Code `2` on syntax defects to prompt immediate LLM auto-healing.
- **`PostToolUseFailure`** (`scripts/hooks/post_tool_failure.sh`): Telemetry logger capturing tool failures into `backups/logs/harness_errors.jsonl`.
- **`PreCompact`** (`scripts/hooks/pre_compact_state.sh`): Captures active git status and branch telemetry to `backups/logs/compact_snapshot.json` before context truncation.
- **`SessionEnd`** (`scripts/hooks/session_cleanup.sh`): Flushes session state, logs session completion, and cleans ephemeral test artifacts.

### 2. Four-Tier Security Matrix (`.claude/rules/safety-tiers.md`)

- **Tier 0 (Autonomous / Read-Only - Exit 0)**: Read-only queries (`git status`, `git diff`, `free`, `df`, `systemctl status`, `ps`, read-only diagnostics) run autonomously.
- **Tier 1 (Workspace Contained - Exit 0)**: File reads, writes, and edits bounded within `${CLAUDE_PROJECT_DIR}` proceed autonomously subject to post-tool linting.
- **Tier 2 (Controlled System Operations - Exit 0)**: Whitelisted scripts (`scripts/*.sh`, `scripts/metrics_exporter.py`, `scripts/agent_bus.py`) run with pre-authorized status. Covered utilities include diagnostics, cleanup, updates, snapshots, benchmarks, metrics, notifications, disk compaction, sandboxing, timer management, message bus operations, and recovery provisioning.
- **Tier 3 (Strict Invariant Violations - Hard Blocked with Exit 2)**:
  - Root / Home obliteration: `rm -rf /`, `rm -rf ~`, `rm -rf $HOME`.
  - WSL instance lifecycle destruction: `wsl --unregister`, `wsl.exe --unregister`, `wsl --shutdown`.
  - Package manager wildcard purges: `apt purge *`, `apt remove -y *`, `pacman -Rcs *`, `dnf remove --all`, `zypper remove *`.
  - Privileged container escape vectors: `podman run --privileged`, `docker run --privileged`.
  - Raw disk partitioning / formatting: `mkfs.*`, `fdisk`, `dd if=... of=/dev/sd*`.
  - Windows host intrusions: Modifying `/mnt/c/Windows`, `Program Files`, `AppData`.
  - Linux core system destruction: Modifying `/etc/passwd`, `/etc/shadow`, `/boot/`, `/dev/`.

### 3. WSL2 Filesystem Boundaries and Storage Invariants (`.claude/rules/wsl-boundaries.md`)

- **Native EXT4 Domain (`${HOME}/`)**: Repositories, `node_modules`, `.venv`, and build stores MUST reside on ext4. This avoids 9P virtualization latency and permission churn.
- **NTFS Windows Mounts (`/mnt/c/`, `/mnt/d/`)**:
  - `/mnt/d/`: Designated solely for compressed WSL point-in-time snapshots and offsite archival (`/mnt/d/wsl_backup`).
  - `/mnt/c/`: Read-only host inspection. Direct modifications to Windows host system folders are strictly prohibited.

---

## Custom Slash Commands (`.claude/commands/`)

- **`/diag`**: Comprehensive system diagnostics (`./scripts/sys_diag.sh`).
- **`/clean`**: Disk space reclamation across APT, UV, PNPM, Bun, and `/tmp` (`./scripts/clean_system.sh`).
- **`/upgrade`**: Coordinated toolchain updates (`./scripts/update_runtimes.sh`).
- **`/snapshot`**: Point-in-time tarball backups to `/mnt/d/wsl_backup` (`./scripts/wsl_snapshot.sh`).
- **`/dotfiles`**: Dotfiles backup, diff inspection, and safe restoration (`./scripts/dotfiles_sync.sh`).
- **`/pair`**: Spawns paired Tmux session with Claude Code and Google Antigravity (`./scripts/tmux_agents.sh`).
- **`/perf`**: System performance and filesystem I/O benchmark (`./scripts/perf_tune.sh`).
- **`/harness-check`**: Runs complete harness self-check and diagnostic matrix (`./scripts/harness_check.sh`).

---

## Custom Subagents Registry (`.claude/agents/`)

- **`security-auditor`** (`.claude/agents/security-auditor.md`):
  - **Persona**: Specialized read-only security auditor for vulnerability, secret leakage, and permission analysis.
  - **Tools**: `Read`, `Grep`, `Glob`, `Bash` (read-only diagnostics).
  - **Model & Effort**: `sonnet`, high effort.
- **`system-operator`** (`.claude/agents/system-operator.md`):
  - **Persona**: Systems operations engineer executing automation and refactoring tasks.
  - **Tools**: `Bash`, `Read`, `Grep`, `Glob`, `Edit`, `Write`.
  - **Isolation**: `worktree` (all changes execute in isolated git worktrees).
  - **Model & Effort**: `inherit`, high effort.

---

## Multi-Agent SSOT Symlink Bridge (`scripts/sync_agent_skills.sh`)

`.claude/skills/` is the single source of truth (SSOT) for all skill definitions. The synchronization script creates zero-copy symlinks across downstream agent frameworks:

1. **Universal Agent Standard** (`.agents/skills/`): Populated with relative symlinks (`../../.claude/skills/<name>`) for portable git tracking.
2. **Google Antigravity** (`~/.gemini/config/skills/`): Populated with absolute symlinks for local runtime interop with `agy`.
3. **Automated Sync**: Executed automatically during `SessionStart` preflight and `/harness-check`.

---

## Superpowers Methodology Suite

All tasks in this workspace follow the Superpowers engineering discipline:
- `/brainstorming`: Requirements exploration and design refinement.
- `/writing-plans` & `/executing-plans`: Incremental, test-driven implementation planning & execution.
- `/subagent-driven-development` & `/dispatching-parallel-agents`: Parallel and task-isolated subagent orchestration.
- `/test-driven-development`: Red-Green-Refactor testing discipline.
- `/systematic-debugging`: Root-cause tracing and test pollution detection.
- `/requesting-code-review` & `/receiving-code-review`: Rigorous two-stage code review workflows.
- `/verification-before-completion`: Evidence-first task completion gating.
- `/using-git-worktrees` & `/finishing-a-development-branch`: Git isolation and merge workflow.
- `/writing-skills`: Skill authoring and behavioral testing framework.

---

## Safety and Execution Rules

1. **Deterministic Execution**:
   - Hard blocks (Exit Code 2) override any conversational prompt.
   - All shell scripts must maintain LF line endings, `chmod +x` permissions, and `set -euo pipefail`.
2. **Safe Autonomous Operations**:
   - Read-only diagnostics (`free`, `df`, `systemctl status`, `uname`, network checks).
   - Standard cache cleanups (`uv cache clean`, `pnpm store prune`, `sudo apt clean`).
   - Repository metadata updates (`sudo apt update`).
3. **Explicit Confirmation Required**:
   - Destructive operations outside workspace boundaries.
   - Modifying systemd unit configurations or restarting core system services.
   - WSL instance lifecycle operations (shutdown, terminate, unregister).
   - Restoring dotfiles over active `$HOME` configuration files.

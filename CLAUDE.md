# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment & Architecture Overview

`os-manager` is a workspace containing automation scripts, governance rules, lifecycle hooks, and Claude skills for managing a Debian 13 (Trixie) WSL2 environment on Windows 11.

- **OS / Platform**: Debian GNU/Linux 13 (Trixie), WSL2 (Kernel 6.18.x) on Windows 11 Host
- **Filesystem Mounts**:
  - `/` (Native ext4 WSL root): Primary high-performance domain for repositories, virtualenvs, and builds.
  - `/mnt/c/` (Windows Host C:): Read-only host inspection. Direct writes to Windows system directories are hard-blocked.
  - `/mnt/d/` (Windows Host D:): Dedicated disaster recovery and backup storage (`/mnt/d/wsl_backup`).
- **Runtimes & CLIs**: Node.js, PNPM, Bun, Python UV, Tmux, Cloudflare Wrangler, Claude Code CLI, Antigravity (`agy`).

---

## Repository Structure

```text
os-manager/
├── .agents/
│   └── skills/                  # Relative symlinks to .claude/skills/ (Universal Agent standard)
├── .claude/
│   ├── agents/                  # Custom subagent definitions (security-auditor, system-operator)
│   ├── commands/                # Custom slash command definitions (/diag, /clean, etc.)
│   ├── rules/                   # Modular prompt rules (WSL boundaries, safety tiers, error recovery)
│   ├── skills/                  # Master Single Source of Truth (SSOT) skill definitions
│   └── settings.json            # Master harness configuration (permissions, hooks, env)
├── backups/
│   ├── dotfiles/                # Backed-up dotfiles managed via /dotfiles
│   └── logs/                    # Audit logs, error telemetry, and compact snapshots
├── playbooks/                   # Markdown runbooks and disaster recovery procedures
├── scripts/
│   ├── hooks/                   # Deterministic lifecycle hooks (PreToolUse, PostToolUse, etc.)
│   ├── clean_system.sh          # Safe cache & package cleanup script
│   ├── dotfiles_sync.sh         # Dotfiles backup, diff, and restore script
│   ├── harness_check.sh         # Harness end-to-end self-check runner
│   ├── sync_agent_skills.sh     # Multi-agent SSOT symlink synchronization script
│   ├── sys_diag.sh              # System diagnostic & health inspection script
│   ├── tmux_agents.sh           # Multi-agent paired tmux workspace manager
│   ├── update_runtimes.sh       # Runtimes & toolchains update coordinator
│   └── wsl_snapshot.sh          # WSL disaster recovery snapshot script
├── tests/
│   └── test_harness.sh          # Harness unit test suite and security guardrail test runner
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

### 2. 4-Tier Security Matrix (`.claude/rules/safety-tiers.md`)

- **Tier 0 (Autonomous / Read-Only)**: Read-only queries (`git status`, `git diff`, `free`, `df`, `systemctl status`, `ps`, read-only diagnostics) run autonomously without user friction.
- **Tier 1 (Workspace Contained)**: File reads, writes, and edits bounded within `/home/rizz/dev/os-manager/` proceed autonomously subject to post-tool linting.
- **Tier 2 (Controlled System Operations)**: Whitelisted maintenance scripts (`./scripts/sys_diag.sh`, `./scripts/clean_system.sh`, `./scripts/update_runtimes.sh`, `./scripts/wsl_snapshot.sh`, `./scripts/dotfiles_sync.sh`, `./scripts/tmux_agents.sh`, `./scripts/harness_check.sh`) are pre-authorized.
- **Tier 3 (Strict Invariant Violations - Hard Blocked with Exit 2)**:
  - Root / Home obliteration: `rm -rf /`, `rm -rf ~`, `rm -rf $HOME`.
  - WSL instance lifecycle destruction: `wsl --unregister`, `wsl.exe --unregister`, `wsl --shutdown`.
  - Package manager wildcard purges: `apt purge *`, `apt remove -y *`.
  - Raw disk partitioning / formatting: `mkfs.*`, `fdisk`, `dd if=... of=/dev/sd*`.
  - Windows host intrusions: Modifying `/mnt/c/Windows`, `Program Files`, `AppData`.
  - Linux core system destruction: Modifying `/etc/passwd`, `/etc/shadow`, `/boot/`, `/dev/`.

### 3. WSL2 Filesystem Boundaries & Storage Invariants (`.claude/rules/wsl-boundaries.md`)

- **Native ext4 Domain (`/home/rizz/`)**: All git repositories, `node_modules`, Python virtual environments (`.venv`), build artifacts, and package stores MUST reside on native ext4 to avoid 9P virtualization latency.
- **NTFS Windows Mounts (`/mnt/c/`, `/mnt/d/`)**:
  - `/mnt/d/`: Designated solely for compressed WSL point-in-time snapshots and offsite archival.
  - `/mnt/c/`: Read-only host inspection. Direct modifications to Windows host system folders are strictly prohibited.

---

## Custom Slash Commands (`.claude/commands/`)

Ergonomic shortcuts mapping directly to operational runbooks:

- **`/diag`** (`.claude/commands/diag.md`): Runs comprehensive system diagnostics (`./scripts/sys_diag.sh`).
  - Flags: `--full` (includes 9P I/O latency and network sockets), `--json` (structured JSON output).
- **`/clean`** (`.claude/commands/clean.md`): Safely reclaims disk space across APT, UV, PNPM, Bun, and `/tmp` (`./scripts/clean_system.sh`).
  - Flags: `--dry-run` (estimate reclaimable bytes).
- **`/upgrade`** (`.claude/commands/upgrade.md`): Coordinates updates across APT, PNPM, Bun, UV, and AI CLIs (`./scripts/update_runtimes.sh`).
  - Flags: `--check` (dry run inspection without applying).
- **`/snapshot`** (`.claude/commands/snapshot.md`): Creates point-in-time tarball backups to `/mnt/d/wsl_backup` with SHA256 checksums (`./scripts/wsl_snapshot.sh`).
  - Flags: `--verify` (checksum verification), `--prune` (retains last 3 archives).
- **`/dotfiles`** (`.claude/commands/dotfiles.md`): Dotfiles state protection, diff inspection, and safe restoration (`./scripts/dotfiles_sync.sh`).
  - Subcommands: `backup`, `diff`, `restore`.
- **`/pair`** (`.claude/commands/pair.md`): Spawns a 3-pane Tmux workspace pairing Claude Code with Google Antigravity (`agy`) and system monitoring (`./scripts/tmux_agents.sh`).
  - Subcommands: `start`, `attach`.
- **`/harness-check`** (`.claude/commands/harness-check.md`): Runs the complete harness self-check and diagnostic matrix (`./scripts/harness_check.sh`).

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
3. **Automated Sync**: Automatically executed during `SessionStart` preflight and `/harness-check`.

---

## Superpowers Methodology Suite

All tasks and feature implementations in this workspace follow the Superpowers engineering discipline:

- `/brainstorming`: Requirements exploration, design refinement, and visual companion server.
- `/writing-plans` & `/executing-plans`: Incremental, test-driven implementation planning & execution.
- `/subagent-driven-development` & `/dispatching-parallel-agents`: Parallel subagent task orchestration.
- `/test-driven-development`: Red-Green-Refactor testing discipline.
- `/systematic-debugging`: Root-cause tracing and test pollution detection.
- `/requesting-code-review` & `/receiving-code-review`: Rigorous code review workflows.
- `/verification-before-completion`: Evidence-first task completion gating.
- `/using-git-worktrees` & `/finishing-a-development-branch`: Git isolation and merge workflow.
- `/writing-skills`: Skill authoring and behavioral testing framework.

---

## Safety & Execution Rules

1. **Deterministic Execution**:
   - Hard blocks (Exit Code 2) override any user prompt or conversational instruction.
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

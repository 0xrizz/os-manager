# Product Requirements Document (PRD): OS-Manager Platform

## 1. Executive Summary and Problem Statement

### Background and Operational Context

The `os-manager` platform serves as the centralized control plane, governance harness, and operational automation hub for Debian 13 (Trixie) running on Windows Subsystem for Linux 2 (WSL2) under Windows 11. Modern software engineering workflows combine polyglot toolchains (Node.js, Python UV, Rust Cargo, Bun) with autonomous and semi-autonomous artificial intelligence coding agents such as Claude Code and Google Antigravity.

Operating high-throughput development toolchains inside WSL2 alongside autonomous AI agents introduces distinct operational challenges: filesystem virtualization bottlenecks, dynamic disk space expansion, fragmented agent skill definitions, and catastrophic execution risks when agents invoke unconstrained shell commands. The `os-manager` platform unifies system maintenance, agent safety governance, polyglot runtime lifecycles, and disaster recovery into a single, deterministic control plane.

### Problem 1: WSL2 Resource Bloat and Storage Creep

Virtual hard disk (`.vhdx`) storage in WSL2 expands dynamically on the Windows host as the Linux guest writes files. Deleting files within the ext4 filesystem does not automatically reclaim or shrink the backing `.vhdx` container on the host. Polyglot development workflows compound this growth across Debian APT archives, Python UV wheels, PNPM global stores, Bun caches, and ephemeral `/tmp` build trees. Without scheduled eviction and reclamation routines, workstations face disk exhaustion and degraded responsiveness.

### Problem 2: Autonomous Agent Safety Hazards and Destructive Execution Risks

Autonomous coding agents generate shell commands, edit arbitrary files, and invoke system utilities. Without deterministic runtime guardrails, an agent attempting task completion can execute destructive operations. High-risk actions include root directory obliteration (`rm -rf /`), destructive package purges (`apt purge *`), WSL lifecycle termination (`wsl --unregister`), direct modification of Windows system folders (`/mnt/c/Windows`), or raw block device writes. Model self-restraint and prompt-based instructions fail under adversarial context drift; safety invariants require deterministic, kernel-level and hook-level enforcement.

### Problem 3: Multi-Agent Tooling and Skill Definition Fragmentation

Modern engineering workflows employ multiple AI agent platforms concurrently, including Claude Code, Universal Agent, and Google Antigravity (`agy`). Each framework requires distinct skill discovery paths and configuration schemas. Maintaining disparate skill directories across `.claude/skills/`, `.agents/skills/`, and `~/.gemini/config/skills/` causes configuration drift, duplicated maintenance overhead, and divergent agent behaviors. A single source of truth with automated synchronization keeps all agent frameworks aligned.

### Problem 4: 9P Filesystem Virtualization Latency and Cross-OS POSIX Incompatibilities

WSL2 accesses Windows host drives (`/mnt/c/`, `/mnt/d/`) through the Plan 9 (9P) network protocol. Running development builds, Git operations, package installations, or file watchers on 9P mounts degrades I/O throughput by 500% to 1000% compared to native ext4 storage. Furthermore, 9P mounts lack full Linux inotify event support and introduce POSIX file permission anomalies. Workstations require strict filesystem boundary enforcement: active development must reside entirely within native ext4, while Windows mounts remain restricted to read-only inspection and backup archival.

### Problem 5: Environment Fragility and Manual Recovery Overhead

WSL2 environments remain vulnerable to configuration drift, package corruption, broken symbolic links, and flawed user dotfiles (`.bashrc`, `.tmux.conf`, `.gitconfig`). Rebuilding a customized Debian environment manually requires hours of reconfiguration and halts development. Workstations require verifiable, point-in-time distribution snapshots to dedicated host drives and version-controlled dotfile synchronization with diff inspection.

---

## 2. Vision, Goals, and Explicit Non-Goals

### Strategic Vision

Transform Debian 13 on WSL2 into an enterprise-grade, self-healing, deterministic development workstation where polyglot software engineering and autonomous AI agents operate safely at maximum native ext4 performance.

### Primary Objectives and Success Metrics

- **Zero Destructive Incursions**: 100% deterministic blocking of Tier 3 destructive operations via PreToolUse lifecycle hooks (0 unauthorized destructive executions).
- **Zero Tooling Drift**: 100% synchronization of skill definitions across Claude Code, Universal Agent, and Antigravity frameworks through automated symbolic link orchestration.
- **Sub-100ms Hook Latency**: Lifecycle hook execution overhead remains under 100 milliseconds at the 99th percentile, ensuring zero perceived developer friction.
- **Strict Storage Discipline**: 100% of active Git repositories, virtual environments, and package caches reside on the native ext4 filesystem.
- **Rapid Disaster Recovery**: Complete restoration of the customized distribution from a verified, compressed point-in-time snapshot in under 5 minutes.
- **Automated Harness Integrity**: Continuous 100% pass rate across the 20-assertion automated test suite (`tests/test_harness.sh`).

### Explicit Non-Goals and Out-of-Scope Boundaries

- **Non-Goal 1: Custom Linux Kernel or Distribution Compilation**: The platform operates strictly on upstream Debian 13 (Trixie) packages and WSL2 kernel releases without compiling custom kernel binaries.
- **Non-Goal 2: Graphical User Interface**: The platform provides command-line interfaces, systemd timers, and AI agent harnesses without maintaining a desktop GUI or Electron application.
- **Non-Goal 3: Remote Cloud Infrastructure Management**: The platform governs the local WSL2 instance and local Windows host mounts; it does not provision remote cloud infrastructure or orchestrate external Kubernetes clusters.
- **Non-Goal 4: Windows Host Registry or System Modification**: The platform restricts Windows interactions to userland executable invocations (`wsl.exe`, `explorer.exe`) and read-only host inspection; it does not alter Windows host system files or registry hives.

---

## 3. User Personas and Core Workflows

### Persona 1: The Autonomous Coding Agent

- **Identities**: `system-operator` (systems engineering, automation, refactoring) and `security-auditor` (read-only vulnerability, secret, and configuration auditor).
- **Profile**: Software agents executing autonomous tool calls (file reading, editing, shell execution, testing) in high-iteration loops.
- **Core Workflow**:
  1. The agent initializes a task within an isolated Git worktree.
  2. Before executing any command, the platform intercepts the call via the `PreToolUse` hook, validating the action against the 4-Tier Security Matrix.
  3. Following file modifications, the platform executes `PostToolUse` syntax linters (`bash -n`, `jq`, `python3 -m py_compile`), rejecting invalid syntax with Exit Code 2 to trigger instant agent auto-healing.
  4. On completion, the agent submits code for automated harness verification.

### Persona 2: The High-Velocity Power Developer

- **Profile**: Senior software engineer building polyglot applications across Node.js, Python, Bun, and Rust on WSL2.
- **Core Workflow**:
  1. Executes custom slash commands (`/diag`, `/clean`, `/upgrade`, `/perf`) directly within developer CLI sessions.
  2. Runs `/perf` to verify disk I/O throughput when diagnosing performance bottlenecks.
  3. Uses `/pair` to launch a synchronized, dual-pane tmux workspace running Claude Code and Google Antigravity side by side.
  4. Migrates repositories cloned accidentally on Windows mounts to native ext4 using `./scripts/migrate_repos.sh`.

### Persona 3: The Resiliency and SRE Operator

- **Profile**: Workstation administrator ensuring continuous uptime, backup readiness, and configuration consistency.
- **Core Workflow**:
  1. Installs background systemd user timers via `./scripts/manage_timers.sh` for autonomous daily system maintenance and log rotation.
  2. Generates compressed, verified point-in-time distro tarball backups to `/mnt/d/wsl_backup` using `/snapshot`.
  3. Inspects and restores shell configurations across environments via `/dotfiles`.

---

## 4. Functional Requirements

### FR-1: System Health, Storage Reclamation, and Resource Optimization

- **FR-1.1 (Diagnostics Engine)**: The platform provides a unified diagnostic utility (`scripts/sys_diag.sh`, `/diag`) reporting CPU load, RAM allocation, swap pressure, ext4 root storage utilization, Windows mount states, active systemd failed units, and WSL2 kernel parameters. The utility supports human-readable and structured JSON output formats (`--json`).
- **FR-1.2 (Multi-Tier Cache Eviction)**: The platform provides a safe cleanup utility (`scripts/clean_system.sh`, `/clean`) supporting dry-run inspection (`--dry-run`) and full execution (`--all`). The cleanup routine evicts:
  - APT package cache archives (`/var/cache/apt/archives`).
  - Python UV package cache (`~/.cache/uv`).
  - PNPM global store pruned packages.
  - Bun package cache (`~/.bun/install/cache`).
  - Ephemeral user and system temporary files older than 24 hours in `/tmp`.
- **FR-1.3 (Filesystem I/O Benchmarking)**: The platform provides a storage benchmarking utility (`scripts/perf_tune.sh`, `/perf`) that measures sequential write throughput, random 4K read/write latency, and comparative metrics between native ext4 (`/home/rizz/dev/`) and Windows 9P mounts (`/mnt/c/`, `/mnt/d/`).
- **FR-1.4 (Autonomous Scheduled Maintenance)**: The platform provides systemd user service and timer units (`systemd/os-maintenance.service`, `systemd/os-maintenance.timer`) managed via `scripts/manage_timers.sh` to execute daily automated cache cleanup and telemetry rotation.

### FR-2: AI Agent Governance, 4-Tier Security Matrix, and Auto-Healing Lint Gates

- **FR-2.1 (Deterministic Lifecycle Hook Integration)**: The platform implements and registers six lifecycle hooks in `.claude/settings.json`:
  - `SessionStart` (`scripts/hooks/session_preflight.sh`): Verifies system memory headroom (>300MB), validates required CLI binaries (`jq`, `python3`, `uv`, `node`), synchronizes multi-agent skills, and writes preflight telemetry to `backups/logs/harness_audit.jsonl`.
  - `PreToolUse` (`scripts/hooks/pre_tool_guard.sh`): Evaluates all `Bash`, `Edit`, and `Write` tool calls against the 4-Tier Security Matrix prior to execution.
  - `PostToolUse` (`scripts/hooks/post_tool_lint.sh`): Validates the syntax of modified files (`.sh`, `.json`, `.py`). Returns Exit Code 2 upon syntax errors to force immediate agent auto-healing.
  - `PostToolUseFailure` (`scripts/hooks/post_tool_failure.sh`): Logs tool failure telemetry to `backups/logs/harness_errors.jsonl`.
  - `PreCompact` (`scripts/hooks/pre_compact_state.sh`): Captures active Git status, branch state, and uncommitted diff telemetry to `backups/logs/compact_snapshot.json` before conversation context truncation.
  - `SessionEnd` (`scripts/hooks/session_cleanup.sh`): Flushes audit logs and deletes temporary test artifacts.
- **FR-2.2 (4-Tier Security Matrix Enforcement)**: The `PreToolUse` guardrail enforces four discrete operational tiers:
  - *Tier 0 (Autonomous Read-Only)*: Allows inspection commands (`git status`, `df`, `free`, `ps`, `systemctl status`) to execute without confirmation (Exit Code 0).
  - *Tier 1 (Workspace Contained)*: Allows file reads, writes, and edits strictly bounded within `/home/rizz/dev/os-manager/` (Exit Code 0).
  - *Tier 2 (Controlled System Operations)*: Allows pre-authorized execution of whitelisted repository scripts (`scripts/*.sh`) (Exit Code 0).
  - *Tier 3 (Strict Invariant Violations)*: Hard-blocks destructive operations with Exit Code 2 and outputs structured diagnostic feedback to `stderr`. Prohibited commands include:
    - Root or home obliteration (`rm -rf /`, `rm -rf ~`, `rm -rf $HOME`).
    - WSL instance termination (`wsl --unregister`, `wsl.exe --unregister`, `wsl --shutdown`).
    - Package manager wildcard purges (`apt purge *`, `apt remove -y *`).
    - Raw block device partitioning and formatting (`mkfs.*`, `fdisk`, `dd if=... of=/dev/sd*`).
    - Direct writes to Windows system directories (`/mnt/c/Windows/**`, `Program Files/**`, `AppData/**`).
    - Core Linux system configuration corruption (`/etc/passwd`, `/etc/shadow`, `/boot/**`, `/dev/**`).

### FR-3: Multi-Agent Hub, SSOT Skill Synchronization, and Paired Workspaces

- **FR-3.1 (Master Skill Repository Single Source of Truth)**: The directory `.claude/skills/` serves as the authoritative Single Source of Truth (SSOT) for all 22+ agent skill definitions.
- **FR-3.2 (Zero-Copy Symlink Synchronization Engine)**: The platform provides a synchronization utility (`scripts/sync_agent_skills.sh`) that:
  - Generates relative symbolic links in `.agents/skills/` targeting `.claude/skills/` for the Universal Agent standard.
  - Generates absolute symbolic links in `~/.gemini/config/skills/` for the Google Antigravity (`agy`) runtime.
  - Purges broken or dangling symlinks in target directories automatically.
- **FR-3.3 (Paired Agent Tmux Workspace)**: The platform provides a session orchestrator (`scripts/tmux_agents.sh`, `/pair`) that launches or attaches to a split-pane tmux workspace hosting Claude Code in the primary pane and Google Antigravity in the secondary pane.
- **FR-3.4 (Subagent Registry)**: The platform declares custom subagent profiles in `.claude/agents/`:
  - `security-auditor`: Read-only security persona equipped with `Read`, `Grep`, `Glob`, and read-only `Bash` diagnostics running at high effort.
  - `system-operator`: Worktree-isolated operations persona equipped with `Bash`, `Read`, `Grep`, `Glob`, `Edit`, and `Write` running at high effort.

### FR-4: Polyglot Toolchain Lifecycle Management and Workstation Migration

- **FR-4.1 (Coordinated Toolchain Updates)**: The platform provides a runtime upgrade coordinator (`scripts/update_runtimes.sh`, `/upgrade`) that verifies and updates:
  - Debian core packages via `apt update && apt upgrade`.
  - Node.js global package managers (PNPM, Corepack).
  - Python UV CLI and tool chains.
  - Bun JavaScript runtime.
  - Rust toolchains via `rustup update`.
  - AI coding assistant CLIs (Claude Code, Google Antigravity).
- **FR-4.2 (NTFS to Native Ext4 Migration Engine)**: The platform provides a migration script (`scripts/migrate_repos.sh`) to migrate source repositories from Windows mounts (`/mnt/c/`, `/mnt/d/`) to native ext4 storage (`/home/rizz/dev/`). The migration:
  - Verifies directory readability and target disk capacity.
  - Excludes transient build artifacts (`node_modules`, `.venv`, `target`, `dist`, `build`, `.next`, `.turbo`) during transfer.
  - Reinitializes pristine Git metadata and resets executable file permissions.

### FR-5: Disaster Recovery, Distro Snapshotting, and Dotfiles Resilience

- **FR-5.1 (Compressed Distro Snapshotting)**: The platform provides a snapshot creation utility (`scripts/wsl_snapshot.sh`, `/snapshot`) that exports a gzip-compressed root tarball directly to dedicated Windows host storage at `/mnt/d/wsl_backup/`.
- **FR-5.2 (Archive Verification and Pruning)**: The snapshot utility verifies tarball integrity via `tar -tzf` and enforces retention policies by pruning archives older than a configurable threshold.
- **FR-5.3 (Dotfiles Synchronization Engine)**: The platform provides a dotfiles synchronization utility (`scripts/dotfiles_sync.sh`, `/dotfiles`) supporting three modes:
  - `backup`: Copies user configuration files (`~/.bashrc`, `~/.tmux.conf`, `~/.gitconfig`, `~/.profile`) to version-controlled storage in `backups/dotfiles/`.
  - `diff`: Compares active user configuration files against repository backups and outputs a unified diff.
  - `restore`: Restores backed-up configuration files to the user home directory with safety confirmations.

---

## 5. Non-Functional Requirements

### NFR-1: Deterministic Hook Execution Latency

- **Threshold**: Lifecycle hooks (`PreToolUse`, `PostToolUse`, `SessionStart`) must complete execution within 100 milliseconds at the 99th percentile.
- **Measurement**: Evaluated using automated micro-benchmarks executing sequential tool invocations.
- **Rationale**: Minimal latency prevents pauses during autonomous agent loops.

### NFR-2: Strict Native Ext4 Storage Invariant

- **Threshold**: 100% of development workspaces, compilation artifacts, package stores, and virtual environments must reside on the native ext4 filesystem (`/home/rizz/`).
- **Constraint**: Windows 9P mounts (`/mnt/c/`, `/mnt/d/`) remain strictly limited to read-only inspection and backup archival.
- **Rationale**: Prevents severe 9P virtualization latency penalties and filesystem watcher failures.

### NFR-3: Fail-Closed Security and Diagnostic Remediation

- **Policy**: Any invariant violation in `PreToolUse` or unhandled internal hook error must immediately exit with Exit Code 2.
- **Requirement**: The hook must output structured, machine-parseable, actionable remediation instructions to `stderr` explaining the exact reason for the block.
- **Rationale**: Guarantees that agent safety cannot be bypassed by unhandled exceptions or malformed input payloads.

### NFR-4: Automated Test Coverage and Verification Invariants

- **Standard**: The repository test harness (`tests/test_harness.sh`) must maintain a 100% assertion pass rate across all 20 automated unit tests.
- **Scope**: Tests cover security tier classification, hook blocking mechanics, symlink generation, syntax lint failures, and error logging telemetry.

### NFR-5: Portability and Cross-Runtime Compatibility

- **Standard**: All shell scripts must adhere to POSIX standard conventions where applicable, target Bash 5+, declare strict execution mode (`set -euo pipefail`), and maintain Unix LF line endings.
- **Validation**: Scripts must pass `shellcheck` static analysis with zero errors.

---

## 6. User Stories and Acceptance Criteria

### US-1: Autonomous Protection from Destructive Commands

**As an** AI agent governance harness  
**I want to** intercept and block destructive system commands prior to execution  
**So that** the WSL2 environment and Windows host remain protected from catastrophic modifications  

- **Scenario 1.1 (Blocking Root Obliteration)**:
  - **Given** an autonomous agent initiates a `Bash` tool invocation containing `rm -rf /`
  - **When** `scripts/hooks/pre_tool_guard.sh` evaluates the command payload
  - **Then** the hook terminates with Exit Code 2, outputs `[SECURITY VIOLATION] Root obliteration blocked` to `stderr`, and prevents command execution.

- **Scenario 1.2 (Blocking WSL Unregistration)**:
  - **Given** an agent generates a shell command calling `wsl.exe --unregister Debian`
  - **When** `scripts/hooks/pre_tool_guard.sh` parses the tool input
  - **Then** the hook intercepts the call, exits with status 2, and logs the blocked command to `backups/logs/harness_audit.jsonl`.

- **Scenario 1.3 (Allowing Safe Workspace Modifications)**:
  - **Given** an agent executes an `Edit` tool call on `/home/rizz/dev/os-manager/scripts/sys_diag.sh`
  - **When** `scripts/hooks/pre_tool_guard.sh` evaluates the target file path
  - **Then** the hook recognizes the path within workspace boundaries and exits with status 0.

### US-2: Closed-Loop Auto-Healing on Syntax Defects

**As an** autonomous coding agent  
**I want to** receive immediate, structured linting feedback upon writing defective code  
**So that** I can automatically repair syntax errors before running test suites  

- **Scenario 2.1 (Rejecting Malformed Shell Scripts)**:
  - **Given** an agent writes a shell script with an unclosed `if` statement to `scripts/sample.sh`
  - **When** `scripts/hooks/post_tool_lint.sh` executes `bash -n` against the modified file
  - **Then** the hook exits with status 2, logs the syntax failure to `stderr` with the exact line number, and prompts the agent to initiate an immediate repair turn.

- **Scenario 2.2 (Passing Valid JSON Configurations)**:
  - **Given** an agent modifies `.claude/settings.json` with valid JSON formatting
  - **When** `scripts/hooks/post_tool_lint.sh` executes `jq empty`
  - **Then** the hook completes with status 0, allowing the workflow to proceed without interruption.

### US-3: Automated Background Storage Reclaim via Systemd User Timers

**As a** workstation developer  
**I want** package caches and temporary build artifacts evicted automatically on a daily schedule  
**So that** my WSL2 ext4 partition does not accumulate storage bloat  

- **Scenario 3.1 (Daily Timer Execution)**:
  - **Given** the `os-maintenance.timer` is enabled and active in the systemd user session
  - **When** the scheduled daily trigger time arrives
  - **Then** systemd triggers `os-maintenance.service`, which executes `clean_system.sh --all` and records the reclaimed space to `backups/logs/harness_audit.jsonl`.

### US-4: Zero-Copy Multi-Agent Skill Synchronization

**As a** developer using multiple AI agent interfaces  
**I want** skill definitions authored in `.claude/skills/` to be available immediately in Universal Agent and Google Antigravity  
**So that** all agents possess identical capabilities without manual configuration copying  

- **Scenario 4.1 (Symlink Synchronization During Preflight)**:
  - **Given** a new skill `perf-tune` is created in `.claude/skills/perf-tune`
  - **When** `scripts/hooks/session_preflight.sh` runs during session initialization
  - **Then** a relative symlink is created at `.agents/skills/perf-tune` and an absolute symlink is created at `~/.gemini/config/skills/perf-tune`.

- **Scenario 4.2 (Pruning Dangling Links)**:
  - **Given** a skill file is deleted from `.claude/skills/`
  - **When** `scripts/sync_agent_skills.sh` executes
  - **Then** dead symbolic links in `.agents/skills/` and `~/.gemini/config/skills/` are identified and removed cleanly.

### US-5: Verifiable Point-in-Time Distro Snapshot Archival

**As an** SRE operator  
**I want to** export a compressed tarball of the active Debian WSL2 distribution to `/mnt/d/wsl_backup`  
**So that** I have a verifiable backup archive for disaster recovery  

- **Scenario 5.1 (Successful Snapshot Creation and Verification)**:
  - **Given** the Windows host drive `/mnt/d/wsl_backup` is mounted and has sufficient free disk space
  - **When** the operator runs `./scripts/wsl_snapshot.sh`
  - **Then** the platform creates a timestamped archive (`debian_wsl_snapshot_YYYYMMDD_HHMMSS.tar.gz`), validates its structure via `tar -tzf`, and reports successful archive verification.

### US-6: Cross-Mount Workstation Migration with Binary Artifact Exclusion

**As a** developer migrating legacy projects  
**I want to** transfer a Git repository from `/mnt/c/Users/rizz/project` to `/home/rizz/dev/project` while stripping build caches  
**So that** the project runs at full ext4 performance without transferring gigabytes of redundant dependencies  

- **Scenario 6.1 (Clean Repository Migration)**:
  - **Given** a repository on `/mnt/c/Users/rizz/project` containing `node_modules` and `.venv`
  - **When** the developer runs `./scripts/migrate_repos.sh /mnt/c/Users/rizz/project /home/rizz/dev/project`
  - **Then** source files and Git history are copied to the target path, `node_modules` and `.venv` are excluded, and file permissions are normalized to Linux standards.

---

## 7. Strategic Roadmap and Milestones

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════
                                  OS-MANAGER STRATEGIC ROADMAP                                    
 ══════════════════════════════════════════════════════════════════════════════════════════════════
   PHASE 1 (COMPLETED)           PHASE 2 (COMPLETED)           PHASE 3 (NEAR-TERM)    PHASE 4 (LONG-TERM)
 ┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐ ┌───────────────────┐
 │ Foundation, Safety  │       │ Auto-Maintenance,   │       │ Telemetry Metrics   │ │ Dynamic Mesh &    │
 │ Tiers & Diagnostics │──────▶│ Perf & Migration    │──────▶│ Exporters & Hyper-V │─▶ Cross-Distro Hub  │
 │ • 4-Tier Guardrails │       │ • Systemd Timers    │       │ • Prometheus Output │ │ • Fedora/Arch WSL │
 │ • 20 Unit Tests     │       │ • I/O Benchmark     │       │ • Host vhdx Shrink  │ │ • Inter-Agent Bus │
 │ • SSOT Skill Engine │       │ • Repo Migration    │       │ • Desktop Alerts    │ │ • Auto-Provision  │
 └─────────────────────┘       └─────────────────────┘       └─────────────────────┘ └───────────────────┘
```

### Phase 1: Foundation, Security Guardrails, and Core Automation (Completed)

- **Deliverable 1.1**: Core diagnostic and maintenance scripts (`sys_diag.sh`, `clean_system.sh`, `update_runtimes.sh`).
- **Deliverable 1.2**: 4-Tier Security Matrix and lifecycle hook engine (`pre_tool_guard.sh`, `post_tool_lint.sh`, `session_preflight.sh`).
- **Deliverable 1.3**: Master Single Source of Truth skill directory with 22 skills and multi-agent symlink synchronization (`sync_agent_skills.sh`).
- **Deliverable 1.4**: Automated test suite (`tests/test_harness.sh`) validating 20 core security and operational assertions.
- **Deliverable 1.5**: Initial custom slash commands (`/diag`, `/clean`, `/upgrade`, `/snapshot`, `/dotfiles`, `/pair`, `/harness-check`).

### Phase 2: Autonomous Maintenance, Performance Benchmarking, and Migration (Completed)

- **Deliverable 2.1**: Systemd user service and timer integration (`os-maintenance.service`, `os-maintenance.timer`, `manage_timers.sh`) for automated background execution.
- **Deliverable 2.2**: Filesystem I/O performance benchmark engine (`perf_tune.sh`, `/perf`) measuring ext4 versus 9P throughput.
- **Deliverable 2.3**: Cross-mount workstation migration utility (`migrate_repos.sh`) with selective artifact pruning.
- **Deliverable 2.4**: Dual-pane tmux workspace pairing Claude Code and Google Antigravity (`tmux_agents.sh`, `/pair`).
- **Deliverable 2.5**: PreCompact telemetry snapshotting (`pre_compact_state.sh`) and error telemetry logging (`post_tool_failure.sh`).

### Phase 3: Telemetry Observability and Host Integration (Near-Term)

- **Deliverable 3.1 (Prometheus Metrics Exporter)**: Implement a lightweight background exporter exposing WSL2 CPU, memory, ext4 disk space, and hook execution metrics in Prometheus format on `localhost:9100`.
- **Deliverable 3.2 (Automated Host Disk Compaction)**: Integrate a safe Windows PowerShell Hyper-V script invocation via `manage_timers.sh` that executes `Optimize-VHD` on the backing WSL2 `.vhdx` file when reclaimed disk space exceeds 10 gigabytes.
- **Deliverable 3.3 (Desktop Notification Bridge)**: Provide desktop notification triggers on the Windows host when snapshots complete, system maintenance runs, or Tier 3 security invariant violations occur.
- **Deliverable 3.4 (Hook Performance Tracing)**: Embed microsecond-precision execution timers in all lifecycle hooks, recording latency metrics directly to `backups/logs/harness_audit.jsonl`.

### Phase 4: Dynamic Agent Mesh and Cross-Distribution Portability (Long-Term)

- **Deliverable 4.1 (Cross-Distribution Engine)**: Extend `os-manager` governance and harness scripts to support Ubuntu, Arch Linux, and Fedora WSL2 instances.
- **Deliverable 4.2 (Inter-Agent Message Bus)**: Implement a local domain socket message bus enabling structured communication and task delegation between Claude Code subagents and Antigravity workers.
- **Deliverable 4.3 (Automated Disaster Recovery Provisioning)**: Author automated Windows bootstrap scripts (`bootstrap_wsl.ps1`) capable of provisioning a fresh WSL2 instance from a backup tarball in a single command.
- **Deliverable 4.4 (Agent Workspace Virtualization)**: Integrate lightweight Linux container isolation (via Podman or systemd-nspawn) for untrusted subagent code execution within the ext4 workspace.

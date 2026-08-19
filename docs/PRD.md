# Product Requirements Document (PRD): OS-Manager Platform

## 1. Executive Summary and Problem Statement

### 1.1 Operational Context and Strategic Background

The `os-manager` platform provides a centralized governance harness, security control plane, and operational automation engine for Claude Code. Modern software engineering workflows combine polyglot toolchains (Node.js, Python UV, Rust Cargo, Bun) with autonomous and semi-autonomous artificial intelligence coding agents.

Operating high-throughput developer toolchains alongside autonomous coding agents introduces distinct operational challenges: unconstrained shell command execution, virtual disk bloat, filesystem virtualization latency, fragmented agent configurations, and workstation drift. The `os-manager` platform unites system maintenance, deterministic security guardrails, background telemetry, disaster recovery, and cross-platform runtime abstractions into a single control plane.

### 1.2 Problem Statement

1. **Autonomous Agent Safety Hazards**: Autonomous agents generate shell commands, edit files, and invoke system utilities. Without deterministic guardrails, an agent can execute destructive commands. Risks include root deletion (`rm -rf /`), package purges (`apt purge *`), WSL termination (`wsl --unregister`), and host file tampering. Model self-restraint fails under adversarial context drift. Safety invariants require deterministic lifecycle hooks.
2. **Virtual Disk Storage Creep**: Dynamic virtual hard disk containers (`.vhdx`) in WSL2 expand as guest filesystems write data. Deleting files within guest filesystems does not shrink backing containers on the host. Storage exhaustion occurs without automated cleanup and host disk compaction.
3. **Filesystem Virtualization Latency**: Accessing Windows host storage across network file mounts (such as 9P) degrades I/O performance by 500% to 1000% compared to native ext4 storage. Engineers require strict filesystem boundary enforcement: active development must reside on native filesystems, while host mounts remain restricted to inspection and backup archives.
4. **Environment Fragility and Manual Disaster Recovery**: Development environments face configuration drift, broken dependencies, and corrupted configurations. Rebuilding customized environments manually consumes hours of developer time. Workstations need automated snapshot creation, verifiable disaster recovery provisioning, and version-controlled dotfile tracking.
5. **Cross-Platform and Distribution Fragmentation**: Development teams use diverse operating environments, including Debian, Ubuntu, Arch Linux, Fedora, WSL2, and macOS. A platform must abstract package management, service supervision, and desktop notifications across platforms while maintaining identical Claude Code governance rules.

---

## 2. Vision, Goals, and Core Objectives

### 2.1 Strategic Vision

Transform developer workstations across Linux, WSL2, and macOS into resilient, self-healing environments where Claude Code operates safely at maximum performance.

### 2.2 Primary Objectives and Measurable Key Results

- **100% Deterministic Safety Invariant Enforcement**: 0 unauthorized executions of Tier 3 destructive operations through `PreToolUse` lifecycle hooks.
- **Sub-100ms Hook Execution Overhead**: Lifecycle hook execution overhead remains under 100 milliseconds at the 99th percentile.
- **Continuous 50-Assertion Harness Pass Rate**: The master test harness (`tests/test_harness.sh`) maintains a 100% pass rate across all 50 assertions.
- **Cross-Platform Compatibility**: Complete operational parity across Linux distributions (Debian, Ubuntu, Arch, Fedora, openSUSE), WSL2 (with Windows host integration), and macOS (Darwin).
- **Rapid Disaster Recovery**: Complete environment recovery from a verified, compressed snapshot in under 5 minutes.
- **Dual-Tier Open-Source Distribution**: Seamless installation via Git repository clone with `./install.sh` or Python package CLI (`osm` via `uv tool install os-manager`).

### 2.3 Explicit Non-Goals

- **Custom Kernel Compilation**: The platform runs on standard upstream Linux kernels, WSL2 kernels, and Darwin kernels without maintaining custom kernel builds.
- **Graphical User Interface**: The platform provides CLI commands, slash commands, and background daemons without a graphical desktop interface.
- **Remote Cloud Infrastructure Provisioning**: The platform manages local developer workstations; it does not provision remote cloud instances or orchestrate Kubernetes clusters.

---

## 3. User Personas and Core Workflows

### 3.1 Persona 1: Autonomous Coding Agent

- **Identities**: `system-operator` (systems operations and refactoring) and `security-auditor` (read-only vulnerability and configuration auditor).
- **Profile**: Software agents executing autonomous tool calls (file reading, file writing, shell execution, testing) in high-iteration loops.
- **Core Workflow**:
  1. The agent starts a task inside an isolated Git worktree.
  2. Before executing any command, the platform intercepts the call via the `PreToolUse` hook, validating the action against the 4-Tier Security Matrix.
  3. Following file modifications, the platform executes `PostToolUse` syntax linters (`bash -n`, `jq empty`, `python3 -m py_compile`), rejecting invalid syntax with Exit Code 2 to trigger immediate auto-healing.
  4. For high-risk or untrusted commands, the agent executes tasks inside a rootless container sandbox via `scripts/sandbox_exec.sh`.
  5. On task completion, the agent verifies all changes against the master test suite.

### 3.2 Persona 2: Workstation Developer

- **Profile**: Software engineer building applications across Node.js, Python, Bun, and Rust on Linux, WSL2, or macOS.
- **Core Workflow**:
  1. Installs the platform via `uv tool install os-manager` or `./install.sh`.
  2. Executes custom slash commands (`/diag`, `/clean`, `/upgrade`, `/perf`, `/harness-check`) inside Claude Code sessions.
  3. Runs `/perf` to benchmark disk I/O throughput across native filesystems and cross-OS mounts.
  4. Manages dotfile backups and inspections across machines via `/dotfiles`.

### 3.3 Persona 3: Site Reliability Operator

- **Profile**: Systems administrator ensuring workstation uptime, backup readiness, and configuration consistency.
- **Core Workflow**:
  1. Installs background service units (`manage_timers.sh`) for scheduled maintenance, metrics export, and inter-agent message routing.
  2. Generates compressed, verified distribution backups using `/snapshot`.
  3. Provisions fresh workstations from backup archives using automated recovery scripts (`bootstrap_wsl.ps1` or `post_bootstrap.sh`).

---

## 4. Functional Requirements

### 4.1 System Health, Resource Reclamation, and Performance Benchmarking (FR-1)

- **FR-1.1 (System Diagnostics Engine)**: The unified diagnostic utility (`scripts/sys_diag.sh`, `/diag`, `osm diag`) reports CPU load, memory, swap, disk capacity, mount states, failed systemd units, and kernel parameters. Output formats include text and JSON (`--json`).
- **FR-1.2 (Multi-Tier Cache Eviction)**: The cleanup utility (`scripts/clean_system.sh`, `/clean`, `osm clean`) reclaims disk space across APT archives, UV caches, PNPM stores, Bun caches, and `/tmp`. It supports dry-run inspection (`--dry-run`) and full execution (`--all`).
- **FR-1.3 (Filesystem I/O Benchmarking)**: The benchmark utility (`scripts/perf_tune.sh`, `/perf`, `osm perf`) measures sequential write throughput, random 4K read/write latency, and memory throughput.
- **FR-1.4 (Automated Scheduled Maintenance)**: Background timer units (`systemd/os-maintenance.timer` on Linux, Launchd property lists on macOS) managed via `scripts/manage_timers.sh` execute daily cache cleanup and log rotation.

### 4.2 AI Agent Governance, 4-Tier Security Matrix, and Auto-Healing (FR-2)

- **FR-2.1 (Deterministic Lifecycle Hook Integration)**: The platform registers six lifecycle hooks in `.claude/settings.json`:
  - `SessionStart` (`scripts/hooks/session_preflight.sh`): Verifies system memory headroom (>300MB), validates required CLI binaries (`jq`, `python3`, `uv`, `node`), checks background daemons, and writes preflight telemetry to audit logs.
  - `PreToolUse` (`scripts/hooks/pre_tool_guard.sh`): Evaluates all `Bash`, `Edit`, and `Write` tool calls against the 4-Tier Security Matrix before execution.
  - `PostToolUse` (`scripts/hooks/post_tool_lint.sh`): Validates the syntax of modified scripts (`.sh`, `.json`, `.py`). Returns Exit Code 2 upon syntax errors to trigger immediate agent auto-healing.
  - `PostToolUseFailure` (`scripts/hooks/post_tool_failure.sh`): Logs tool failure telemetry to `backups/logs/harness_errors.jsonl`.
  - `PreCompact` (`scripts/hooks/pre_compact_state.sh`): Captures active Git status, branch state, and uncommitted diff telemetry before context truncation.
  - `SessionEnd` (`scripts/hooks/session_cleanup.sh`): Flushes audit logs and deletes temporary test artifacts.
- **FR-2.2 (4-Tier Security Matrix Enforcement)**: The `PreToolUse` guardrail enforces four operational tiers:
  - *Tier 0 (Autonomous Read-Only)*: Allows inspection commands (`git status`, `df`, `free`, `ps`, `uptime`, `uname`) to execute without confirmation (Exit Code 0).
  - *Tier 1 (Workspace Contained)*: Allows file reads, writes, and edits bounded within `${CLAUDE_PROJECT_DIR}` (Exit Code 0).
  - *Tier 2 (Controlled Operations)*: Allows pre-authorized execution of whitelisted repository scripts (`scripts/*.sh`, `scripts/*.py`, `osm`) (Exit Code 0).
  - *Tier 3 (Strict Invariant Violations)*: Hard-blocks destructive operations with Exit Code 2 and outputs structured diagnostic feedback to `stderr`. Prohibited commands include:
    - Root or home directory obliteration (`rm -rf /`, `rm -rf ~`, `rm -rf $HOME`).
    - WSL instance termination (`wsl --unregister`, `wsl.exe --unregister`, `wsl --shutdown`).
    - Package manager wildcard purges (`apt purge *`, `pacman -Rcs *`, `brew uninstall --force *`).
    - Raw block device partitioning and formatting (`mkfs.*`, `fdisk`, `dd if=... of=/dev/sd*`).
    - Host operating system directory modification (`/mnt/c/Windows/**`, `/System/**`, `/Library/**`).
    - Core system credential corruption (`/etc/passwd`, `/etc/shadow`).

### 4.3 Telemetry Observability, Metrics Export, and Latency Tracing (FR-3)

- **FR-3.1 (Prometheus Metrics Exporter)**: The platform provides a zero-dependency HTTP server daemon (`scripts/metrics_exporter.py`) listening on `127.0.0.1:9100`. It exports Prometheus 0.0.4 metrics covering CPU utilization, memory pressure, disk capacity, and hook execution metrics.
- **FR-3.2 (Monotonic Hook Latency Tracing)**: The platform implements nanosecond-precision tracing (`scripts/hooks/lib/trace_helper.sh`) within all lifecycle hooks, recording duration telemetry directly to audit logs.
- **FR-3.3 (Desktop Notification Bridge)**: The platform provides desktop alerts (`scripts/notify_host.sh`) supporting Windows WinRT toasts (via PowerShell), macOS native alerts (via AppleScript), and Linux desktop notifications (via `notify-send`).
- **FR-3.4 (Automated Host Disk Compaction)**: The platform provides disk compaction utilities (`scripts/compact_host_disk.sh`). These trigger Hyper-V `Optimize-VHD` on backing WSL2 `.vhdx` files when slack space exceeds a threshold (default: 10GB).

### 4.4 Multi-Agent Interoperability, Sandboxing, and Subagents (FR-4)

- **FR-4.1 (Inter-Agent Message Bus)**: An asynchronous JSON-RPC 2.0 Unix socket daemon (`scripts/agent_bus.py`) and non-blocking client (`scripts/bus_send.sh`) enable inter-agent communication, task delegation, and event broadcasting.
- **FR-4.2 (Agent Workspace Virtualization Sandbox)**: A rootless container wrapper (`scripts/sandbox_exec.sh`) uses Podman to isolate untrusted subagent execution with read-only root filesystems and restricted network access.
- **FR-4.3 (Custom Subagent Registry)**: The platform defines custom subagent profiles in `.claude/agents/`:
  - `security-auditor`: Read-only security auditor analyzing vulnerabilities, secrets, and permissions at high effort.
  - `system-operator`: Worktree-isolated operations engineer executing refactoring and system automation at high effort.

### 4.5 Disaster Recovery and Workstation Migration (FR-5)

- **FR-5.1 (Compressed Snapshot Archival)**: The platform provides snapshot creation utilities (`scripts/wsl_snapshot.sh`, `/snapshot`) generating gzip-compressed tarballs to dedicated backup storage.
- **FR-5.2 (Automated Disaster Recovery Provisioner)**: A Windows PowerShell provisioner (`scripts/bootstrap_wsl.ps1`) and post-bootstrap verifier (`scripts/post_bootstrap.sh`) rebuild customized workstations in a single step.
- **FR-5.3 (Dotfiles Backup and Synchronization)**: The platform provides dotfile tracking (`scripts/dotfiles_sync.sh`, `/dotfiles`) supporting backup, diff inspection, and safe restoration.
- **FR-5.4 (NTFS to Native Ext4 Migration Engine)**: A migration utility (`scripts/migrate_repos.sh`) transfers repositories from host mounts to native storage, excluding transient build caches (`node_modules`, `.venv`, `target`, `dist`).

### 4.6 Dual-Tier Distribution and Open-Source Governance (FR-6)

- **FR-6.1 (Git Repository and Shell Installer)**: The platform provides `./install.sh` supporting global installation (`--global`), project-level scaffolding (`--project <dir>`), and clean uninstallation (`--uninstall`).
- **FR-6.2 (Python Package Distribution)**: The platform provides standard `pyproject.toml` packaging exposing the `osm` CLI (`osm init`, `osm check`, `osm diag`, `osm clean`, `osm perf`, `osm service`).
- **FR-6.3 (Cross-Platform Engine)**: The platform implements runtime detection (`scripts/lib/platform.sh` and `os_manager/platform/`) supporting Debian, Ubuntu, Arch Linux, Fedora, openSUSE, WSL2, and macOS.
- **FR-6.4 (Open-Source Governance Artifacts)**: The repository maintains MIT License, public issue templates, contribution guides (`CONTRIBUTING.md`), security disclosure policies (`SECURITY.md`), and Contributor Covenant v2.1 code of conduct.
- **FR-6.5 (Continuous Integration Matrix)**: The platform implements GitHub Actions workflows (`.github/workflows/ci.yml`) validating syntax, linting, and running the 50-assertion test suite across Ubuntu and macOS runners.

---

## 5. Non-Functional Requirements

### 5.1 Performance and Latency Invariants (NFR-1)

- **Execution Overhead**: Lifecycle hooks (`PreToolUse`, `PostToolUse`, `SessionStart`) must complete within 100 milliseconds at the 99th percentile.
- **Storage Performance**: Active development repositories and virtual environments must reside on native filesystems (ext4 or APFS) to prevent 9P virtualization latency.

### 5.2 Security and Fail-Closed Invariants (NFR-2)

- **Fail-Closed Policy**: Any unhandled exception or security tier violation in `PreToolUse` must immediately exit with status 2, preventing command execution.
- **Structured Feedback**: Guardrail rejections must output clear, actionable remediation messages to `stderr`.

### 5.3 Quality and Test Invariants (NFR-3)

- **Test Suite Coverage**: The master test harness (`tests/test_harness.sh`) must maintain a 100% pass rate across all 50 assertions.
- **Static Code Analysis**: All shell scripts must pass `shellcheck` with zero errors and maintain `set -euo pipefail`. All Python modules must compile cleanly and pass syntax checks.

---

## 6. Strategic Roadmap and Milestones

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════
                                  OS-MANAGER STRATEGIC ROADMAP                                    
 ══════════════════════════════════════════════════════════════════════════════════════════════════
   PHASE 1 (COMPLETED)           PHASE 2 (COMPLETED)           PHASE 3 (COMPLETED)    PHASE 4 (COMPLETED)
 ┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐ ┌───────────────────┐
 │ Foundation, Safety  │       │ Auto-Maintenance,   │       │ Observability, Host │ │ Dynamic Mesh,     │
 │ Tiers & Diagnostics │──────▶│ Perf & Migration    │──────▶│ Integration & Bridge│─▶ Sandbox & Recovery│
 │ • 4-Tier Guardrails │       │ • Systemd Timers    │       │ • Prometheus Daemon │ │ • Inter-Agent Bus │
 │ • 20 Core Tests     │       │ • I/O Benchmark     │       │ • Host vhdx Shrink  │ │ • Podman Sandbox  │
 │ • Initial Commands  │       │ • Repo Migration    │       │ • Toast Bridge      │ │ • Auto-Provision  │
 └─────────────────────┘       └─────────────────────┘       └─────────────────────┘ └───────────────────┘
                                                                                               │
                                                               ┌───────────────────────────────┘
                                                               ▼
                                                     PHASE 5 (ACTIVE IMPLEMENTATION)
                                                   ┌─────────────────────────────────┐
                                                   │ Open-Source Transformation &    │
                                                   │ Dual-Tier Packaging             │
                                                   │ • Cross-Platform Engine         │
                                                   │ • Python Package & `osm` CLI    │
                                                   │ • Shell Installer (`install.sh`)│
                                                   │ • CI Matrix across OS Runners   │
                                                   │ • Community Governance & Docs   │
                                                   └─────────────────────────────────┘
```

### Completed Phases

- **Phase 1: Foundation, Security Guardrails, and Core Automation (Completed)**: Delivered 4-tier security matrix, core diagnostics (`sys_diag.sh`), cleanup utilities (`clean_system.sh`), and initial slash commands.
- **Phase 2: Autonomous Maintenance, Performance Benchmarking, and Migration (Completed)**: Delivered systemd timer automation (`manage_timers.sh`), filesystem I/O benchmarking (`perf_tune.sh`), repository migration (`migrate_repos.sh`), and dual-agent pairing.
- **Phase 3: Observability and Host Integration (Completed)**: Delivered the Prometheus metrics daemon (`metrics_exporter.py`), desktop alert bridge (`notify_host.sh`), automated disk compaction (`compact_host_disk.sh`), and monotonic hook tracing (`trace_helper.sh`).
- **Phase 4: Dynamic Agent Mesh, Workspace Virtualization, and Recovery (Completed)**: Delivered the message bus (`agent_bus.py`), container sandbox (`sandbox_exec.sh`), distro abstraction (`distro.sh`), and recovery provisioning (`bootstrap_wsl.ps1`). Master test assertions reached 50.

### Phase 5: Open-Source Transformation and Multi-Platform Distribution (Active)

- **Deliverable 5.1 (Universal Platform Abstraction)**: Author `scripts/lib/platform.sh` and Python platform modules supporting Linux (Debian, Ubuntu, Arch, Fedora, openSUSE), WSL2 host bridges, and macOS Darwin.
- **Deliverable 5.2 (Dual-Tier Installation and CLI Packaging)**: Author `./install.sh` shell installer and Python `pyproject.toml` package exposing the `osm` CLI.
- **Deliverable 5.3 (Repository Sanitization and Dotfile Templates)**: Parametrize all personal directory paths across scripts and configuration files; create clean `.example` dotfile templates.
- **Deliverable 5.4 (Open-Source Community Governance)**: Author `LICENSE` (MIT), `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, and GitHub issue/PR templates.
- **Deliverable 5.5 (Multi-OS Continuous Integration Pipeline)**: Configure `.github/workflows/ci.yml` running linters and the master harness across Ubuntu and macOS runners.

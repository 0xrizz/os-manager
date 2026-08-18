# OS-Manager Automation and Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 2 and Phase 3 of the `os-manager` blueprint: automated background maintenance via systemd user units, recovery playbooks, I/O benchmarking tooling, and extended test assertions.

**Architecture:** Deliver declarative systemd user service and timer definitions for autonomous cache maintenance. Provide actionable Markdown recovery playbooks for dotfiles drift and snapshot restoration. Build `scripts/perf_tune.sh` to benchmark I/O latency across native ext4 and 9P Windows host mounts. Expose the new utility as an SDO-compliant skill (`perf-tune`), whitelist it in the Tier 2 security matrix, and expand unit test assertions in `tests/test_harness.sh`.

**Tech Stack:** Bash (POSIX / Linux ext4), Systemd User Units, Markdown (agent-style compliant), JSON, YAML frontmatter, ShellCheck.

**Spec:** `docs/superpowers/specs/2026-08-18-os-manager-vision-mission-design.md`

## Global Constraints

- All shell scripts MUST maintain LF line endings, `chmod +x` permissions, and `set -euo pipefail`.
- All Markdown prose MUST strictly adhere to *The Elements of Agent Style* (active voice, direct directives, 0 violations on `agent-style review --audit-only`).
- New skills MUST follow Skill Discovery Optimization (SDO) with YAML frontmatter starting with `description: Use when...`.
- All unit tests in `tests/test_harness.sh` and `./scripts/harness_check.sh` MUST pass with 100% success rate.
- Tier 2 Security Matrix and PreToolUse guardrails MUST whitelist new maintenance scripts.
- Multi-agent skill symlinks MUST be synchronized across `.agents/skills/` and `~/.gemini/config/skills/` via `scripts/sync_agent_skills.sh`.

---

### Task 1: Systemd User Units for Automated Background Maintenance

**Files:**
- Create: `systemd/os-maintenance.service`
- Create: `systemd/os-maintenance.timer`
- Create: `scripts/manage_timers.sh`

**Interfaces:**
- Consumes: `/home/rizz/dev/os-manager/scripts/clean_system.sh`
- Produces: Declarative systemd user units and timer manager script (`scripts/manage_timers.sh`)

- [ ] **Step 1: Create systemd user service unit**

Create directory `systemd/` and write `systemd/os-maintenance.service`:

```ini
[Unit]
Description=OS-Manager Automated System Maintenance
Documentation=https://github.com/0xrizz/os-manager
After=network.target

[Service]
Type=oneshot
ExecStart=/home/rizz/dev/os-manager/scripts/clean_system.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

- [ ] **Step 2: Create systemd user timer unit**

Write `systemd/os-maintenance.timer`:

```ini
[Unit]
Description=Daily OS-Manager Maintenance Timer
Documentation=https://github.com/0xrizz/os-manager

[Timer]
OnCalendar=daily
RandomizedDelaySec=30m
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Create `scripts/manage_timers.sh`**

Write `scripts/manage_timers.sh` to install, enable, check, or disable the systemd user timer:

```bash
#!/usr/bin/env bash
# scripts/manage_timers.sh - Install and manage os-manager systemd user timers
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
ACTION="${1:-status}"

install_units() {
    echo "=== Installing OS-Manager Systemd User Units ==="
    mkdir -p "${SYSTEMD_USER_DIR}"
    cp "${WORKSPACE_ROOT}/systemd/os-maintenance.service" "${SYSTEMD_USER_DIR}/"
    cp "${WORKSPACE_ROOT}/systemd/os-maintenance.timer" "${SYSTEMD_USER_DIR}/"
    
    systemctl --user daemon-reload
    systemctl --user enable --now os-maintenance.timer
    echo "✓ Timer installed and activated."
}

uninstall_units() {
    echo "=== Disabling OS-Manager Systemd User Units ==="
    systemctl --user disable --now os-maintenance.timer || true
    rm -f "${SYSTEMD_USER_DIR}/os-maintenance.service"
    rm -f "${SYSTEMD_USER_DIR}/os-maintenance.timer"
    systemctl --user daemon-reload
    echo "✓ Timer disabled and uninstalled."
}

check_status() {
    echo "=== OS-Manager Systemd User Timer Status ==="
    systemctl --user list-timers --all | grep -E 'os-maintenance|NEXT' || echo "No active timers found."
}

case "${ACTION}" in
    install|enable)
        install_units
        ;;
    uninstall|disable)
        uninstall_units
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status}"
        exit 1
        ;;
esac
```

- [ ] **Step 4: Set execution permissions and validate syntax**

```bash
chmod +x scripts/manage_timers.sh
bash -n scripts/manage_timers.sh
```

- [ ] **Step 5: Commit Task 1 changes**

```bash
git add systemd/ scripts/manage_timers.sh
git commit -m "feat(systemd): add user service, timer, and timer manager script"
```

---

### Task 2: Dotfiles and Disaster Recovery Playbooks

**Files:**
- Create: `playbooks/dotfiles_sync.md`
- Create: `playbooks/disaster_recovery.md`

**Interfaces:**
- Consumes: `scripts/dotfiles_sync.sh`, `scripts/wsl_snapshot.sh`
- Produces: Actionable, step-by-step markdown operational runbooks

- [ ] **Step 1: Write `playbooks/dotfiles_sync.md`**

Write `playbooks/dotfiles_sync.md`:

```markdown
# Playbook: Dotfiles Synchronization and Drift Management

Operational runbook for managing configuration drift, backing up dotfiles, and safely restoring user settings.

## Overview

`os-manager` tracks critical user environment configurations:
- `~/.bashrc` (Shell environment and aliases)
- `~/.tmux.conf` (Terminal multiplexer layout)
- `~/.gitconfig` (Git identity and preferences)

Backups reside in `backups/dotfiles/` within the repository.

---

## Standard Workflows

### 1. Pre-Modification Backup
Run backup before modifying active shell or tmux configurations:

```bash
/home/rizz/dev/os-manager/scripts/dotfiles_sync.sh backup
```

Verify that files are copied to `backups/dotfiles/`:
```bash
git status backups/dotfiles/
```

### 2. Inspecting Configuration Drift
Check differences between active home directory dotfiles and repository copies:

```bash
/home/rizz/dev/os-manager/scripts/dotfiles_sync.sh diff
```

### 3. Restoring Configurations After Environment Reset
Overwriting active dotfiles requires explicit confirmation:

```bash
/home/rizz/dev/os-manager/scripts/dotfiles_sync.sh restore
```

Review the prompted confirmation, confirm with `y`, and reload shell configuration:
```bash
source ~/.bashrc
```

---

## Troubleshooting

### Unintended Overwrites
If you mistakenly overwrite a dotfile, recover previous versions using git history:
```bash
git checkout HEAD -- backups/dotfiles/.bashrc
cp backups/dotfiles/.bashrc ~/.bashrc
```
```

- [ ] **Step 2: Write `playbooks/disaster_recovery.md`**

Write `playbooks/disaster_recovery.md`:

```markdown
# Playbook: WSL2 Disaster Recovery and Snapshot Restoration

Operational runbook for creating, verifying, and restoring full Debian WSL2 point-in-time snapshots.

## Storage Architecture

- **Snapshot Target**: `/mnt/d/wsl_backup/` (Dedicated NTFS host storage)
- **Archive Format**: Compressed `.tar.gz` with accompanying `.sha256` checksums

---

## Standard Recovery Procedures

### 1. Creating Disaster Recovery Snapshots
Generate a fresh point-in-time archive before major upgrades:

```bash
/home/rizz/dev/os-manager/scripts/wsl_snapshot.sh
```

### 2. Verifying Snapshot Integrity
Verify SHA256 checksums of stored archives:

```bash
/home/rizz/dev/os-manager/scripts/wsl_snapshot.sh --verify
```

### 3. Pruning Outdated Snapshots
Retain only the three most recent archives:

```bash
/home/rizz/dev/os-manager/scripts/wsl_snapshot.sh --prune
```

### 4. Full Distro Restoration Procedure
To restore a snapshot to a new or clean WSL instance from Windows PowerShell:

1. Locate the latest archive in `D:\wsl_backup\`:
   ```powershell
   Get-ChildItem D:\wsl_backup\*.tar.gz | Sort-Object LastWriteTime -Descending | Select-Object -First 1
   ```
2. Import the tarball into a new WSL instance:
   ```powershell
   wsl --import Debian-Restored D:\WSL\Debian-Restored D:\wsl_backup\<snapshot_name>.tar.gz
   ```
3. Set the default user in `/etc/wsl.conf`:
   ```ini
   [user]
   default=rizz
   ```
4. Launch the restored instance:
   ```powershell
   wsl -d Debian-Restored
   ```
```

- [ ] **Step 3: Audit style on newly created playbooks**

```bash
agent-style review --audit-only playbooks/dotfiles_sync.md playbooks/disaster_recovery.md
```
Expected: 0 violations for both files.

- [ ] **Step 4: Commit Task 2 changes**

```bash
git add playbooks/
git commit -m "docs(playbooks): add dotfiles sync and disaster recovery runbooks"
```

---

### Task 3: I/O Benchmark and Performance Tuning Utility (`scripts/perf_tune.sh`)

**Files:**
- Create: `scripts/perf_tune.sh`

**Interfaces:**
- Consumes: Native ext4 (`/home/rizz/`) and 9P Windows mounts (`/mnt/c/`, `/mnt/d/`)
- Produces: CLI tool measuring write and read throughput with JSON and human-readable output

- [ ] **Step 1: Write `scripts/perf_tune.sh`**

Write `scripts/perf_tune.sh`:

```bash
#!/usr/bin/env bash
# scripts/perf_tune.sh - Filesystem I/O performance benchmark utility for WSL2
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FORMAT="text"
BLOCK_COUNT=100
BLOCK_SIZE="1M"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)
            FORMAT="json"
            shift
            ;;
        --quick)
            BLOCK_COUNT=20
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--json] [--quick]"
            echo "  --json   Output results in JSON format"
            echo "  --quick  Run a smaller 20MB benchmark sample"
            exit 0
            ;;
        *)
            echo "Unknown flag: $1" >&2
            exit 1
            ;;
    esac
done

benchmark_path() {
    local target_dir="$1"
    local label="$2"
    local test_file="${target_dir}/.os_manager_io_test.tmp"
    
    if [ ! -d "${target_dir}" ] || [ ! -w "${target_dir}" ]; then
        echo "{\"label\":\"${label}\",\"path\":\"${target_dir}\",\"status\":\"unwritable\"}"
        return 0
    fi
    
    # Measure write performance
    local write_out
    write_out=$(dd if=/dev/zero of="${test_file}" bs="${BLOCK_SIZE}" count="${BLOCK_COUNT}" conv=fdatasync 2>&1)
    local write_speed
    write_speed=$(echo "${write_out}" | awk '/bytes/{print $(NF-1), $NF}')
    
    # Measure read performance
    local read_out
    read_out=$(dd if="${test_file}" of=/dev/null bs="${BLOCK_SIZE}" count="${BLOCK_COUNT}" 2>&1)
    local read_speed
    read_speed=$(echo "${read_out}" | awk '/bytes/{print $(NF-1), $NF}')
    
    rm -f "${test_file}"
    
    if [ "${FORMAT}" = "json" ]; then
        echo "{\"label\":\"${label}\",\"path\":\"${target_dir}\",\"write_speed\":\"${write_speed}\",\"read_speed\":\"${read_speed}\",\"status\":\"ok\"}"
    else
        echo "[$label] Path: ${target_dir}"
        echo "  Write Speed: ${write_speed}"
        echo "  Read Speed:  ${read_speed}"
    fi
}

if [ "${FORMAT}" = "json" ]; then
    echo "{"
    echo "  \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\","
    echo "  \"benchmarks\": ["
    echo "    $(benchmark_path "${WORKSPACE_ROOT}" "Native EXT4 (Workspace)"),"
    echo "    $(benchmark_path "/tmp" "Native EXT4 (/tmp)"),"
    echo "    $(benchmark_path "/mnt/d/wsl_backup" "Windows D: 9P Mount")"
    echo "  ]"
    echo "}"
else
    echo "=================================================="
    echo "      os-manager WSL2 I/O Latency Benchmark       "
    echo "=================================================="
    benchmark_path "${WORKSPACE_ROOT}" "Native EXT4 (Workspace)"
    echo "--------------------------------------------------"
    benchmark_path "/tmp" "Native EXT4 (/tmp)"
    echo "--------------------------------------------------"
    benchmark_path "/mnt/d/wsl_backup" "Windows D: 9P Mount"
    echo "=================================================="
fi
```

- [ ] **Step 2: Set execution permissions and test script**

```bash
chmod +x scripts/perf_tune.sh
bash -n scripts/perf_tune.sh
./scripts/perf_tune.sh --quick
./scripts/perf_tune.sh --quick --json | jq .
```

- [ ] **Step 3: Commit Task 3 changes**

```bash
git add scripts/perf_tune.sh
git commit -m "feat(perf): add WSL2 filesystem IO benchmark utility"
```

---

### Task 4: Add `perf-tune` Skill and Synchronize Multi-Agent SSOT

**Files:**
- Create: `.claude/skills/perf-tune/SKILL.md`

**Interfaces:**
- Consumes: `scripts/perf_tune.sh`
- Produces: 22nd SSOT skill synchronized to Universal Agent and Antigravity

- [ ] **Step 1: Write `.claude/skills/perf-tune/SKILL.md`**

Write `.claude/skills/perf-tune/SKILL.md`:

```markdown
---
name: perf-tune
description: Use when measuring I/O latency between ext4 and 9P Windows mounts, running disk throughput benchmarks, or diagnosing filesystem performance bottlenecks
---

# Performance Tuning and I/O Benchmark Skill

Measures write and read throughput across native Linux ext4 partitions and Windows 9P mounts (`/mnt/c/`, `/mnt/d/`).

## Trigger Scenarios
- Investigating slow build times or package installation bottlenecks
- Comparing I/O latency between native ext4 (`/home/rizz/`) and Windows host mounts
- Verifying storage performance before running intensive data or AI workflows

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/perf_tune.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Executes standard 100MB read and write benchmark |
| `--quick` | Runs faster 20MB benchmark sample |
| `--json` | Emits structured JSON results for automated profiling |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Non-destructive benchmark operating in workspace and temp directories.
```

- [ ] **Step 2: Audit style on `perf-tune` skill**

```bash
agent-style review --audit-only .claude/skills/perf-tune/SKILL.md
```
Expected: 0 violations.

- [ ] **Step 3: Synchronize multi-agent symlinks**

```bash
./scripts/sync_agent_skills.sh
```
Expected: 22 skills synchronized to `.agents/skills/` and `~/.gemini/config/skills/`.

- [ ] **Step 4: Commit Task 4 changes**

```bash
git add .claude/skills/perf-tune/SKILL.md
git commit -m "feat(skills): add perf-tune SDO skill and synchronize multi-agent bridges"
```

---

### Task 5: Extend Test Suite & Security Matrix for New Components

**Files:**
- Modify: `.claude/rules/safety-tiers.md`
- Modify: `scripts/hooks/pre_tool_guard.sh`
- Modify: `tests/test_harness.sh`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `scripts/perf_tune.sh`, `scripts/manage_timers.sh`, `systemd/`, `playbooks/`
- Produces: Whitelisted execution and 18 unit test assertions

- [ ] **Step 1: Update `.claude/rules/safety-tiers.md`**

Add `./scripts/perf_tune.sh` and `./scripts/manage_timers.sh` to the Tier 2 whitelist:

```markdown
  - `./scripts/perf_tune.sh` (Filesystem I/O performance benchmark)
  - `./scripts/manage_timers.sh` (Systemd user timer manager)
```

- [ ] **Step 2: Update `scripts/hooks/pre_tool_guard.sh`**

Whitelist `perf_tune.sh` and `manage_timers.sh` in the Tier 2 regex in `scripts/hooks/pre_tool_guard.sh`.

- [ ] **Step 3: Update `tests/test_harness.sh`**

Add unit assertions for:
1. `perf_tune.sh` quick benchmark execution (Tier 2 execution test).
2. Systemd unit syntax validation (`systemd-analyze verify` or file presence check).
3. Playbook existence and `agent-style review` compliance.

- [ ] **Step 4: Update `CLAUDE.md`**

Update the skill count to 22, add `perf_tune.sh` and `manage_timers.sh` to Common Operational Commands, and reflect updated test assertion count.

- [ ] **Step 5: Run test suite and full harness check**

```bash
./tests/test_harness.sh
./scripts/harness_check.sh
```
Expected: All tests pass with 0 errors.

- [ ] **Step 6: Commit Task 5 changes**

```bash
git add .claude/rules/safety-tiers.md scripts/hooks/pre_tool_guard.sh tests/test_harness.sh CLAUDE.md
git commit -m "test(harness): extend test assertions and whitelist new maintenance scripts"
```

---

### Task 6: Full Verification, Style Audit, and Branch Integration

**Files:**
- Read/Verify: All repository components

**Interfaces:**
- Consumes: All 6 tasks
- Produces: Clean git status, verified test matrix, and pushed remote commits

- [ ] **Step 1: Run comprehensive agent-style review across all markdown files**

```bash
agent-style review --audit-only CLAUDE.md playbooks/*.md .claude/rules/*.md .claude/skills/*/SKILL.md
```
Expected: 0 violations across all files.

- [ ] **Step 2: Run complete harness self-check**

```bash
./scripts/harness_check.sh
```
Expected: All checks pass, symlinks valid, settings JSON clean.

- [ ] **Step 3: Push changes to main**

```bash
git push origin main
```

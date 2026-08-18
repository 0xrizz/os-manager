# Technical Design Specification: Automated Host Disk Compaction (Deliverable 3.2)

## 1. Executive Summary & Objective

This document defines the technical specification for **Automated Host Disk Compaction** (Deliverable 3.2 from `docs/PRD.md`).

Virtual hard disk (`.vhdx`) storage in WSL2 expands dynamically on the Windows host as files are written in the Linux guest. Deleting packages and build caches via `scripts/clean_system.sh` marks ext4 blocks as free. However, the host `.vhdx` file does not automatically shrink. This specification defines a safe, threshold-driven disk compaction mechanism that coordinates Linux `fstrim` block discards with Windows host Hyper-V compaction.

---

## 2. System Architecture & Component Interaction

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════
                         AUTOMATED HOST DISK COMPACTION TOPOLOGY
 ══════════════════════════════════════════════════════════════════════════════════════════════════

 ┌──────────────────────────────────────────────────────────────────────────────────────────────┐
 │ SYSTEMD MAINTENANCE SERVICE / CLI INVOCATION                                                 │
 │ • `systemd/os-maintenance.service` or manual `./scripts/clean_system.sh --compact`           │
 └──────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                │
 ┌──────────────────────────────────────────────▼───────────────────────────────────────────────┐
 │ SYSTEM CLEANUP ENGINE (`scripts/clean_system.sh`)                                            │
 │ • Step 1: Evicts APT, UV, PNPM, Bun, and /tmp caches                                         │
 │ • Step 2: Executes `fstrim /` to discard unused ext4 filesystem blocks                       │
 └──────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                │
 ┌──────────────────────────────────────────────▼───────────────────────────────────────────────┐
 │ HOST COMPACTION COORDINATOR (`scripts/compact_host_disk.sh`)                                 │
 │ • Queries ext4 used bytes vs Windows host `ext4.vhdx` file size via PowerShell interop       │
 │ • Evaluates threshold: Slack Space = (Host VHDX Size - Ext4 Used Size) >= 10GB               │
 └──────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                │
        ┌───────────────────────────────────────┴───────────────────────────────────────┐
        │ [Slack >= 10GB & Preconditions Met]                                           │ [Slack < 10GB or Blocked]
        ▼                                                                               ▼
 ┌──────────────────────────────────────────────┐                       ┌──────────────────────────────────────────────┐
 │ POWERSHELL EXECUTION BRIDGE                  │                       │ ADVISORY & LOGGING                           │
 │ • Invokes `powershell.exe -NoProfile`        │                       │ • Logs measurement to audit telemetry       │
 │ • Executes `Optimize-VHD -Mode Full`         │                       │ • Skips host compaction safely               │
 │ • Fallback: Diskpart attach/compact script   │                       └──────────────────────────────────────────────┘
 └──────────────────────────────────────────────┘
```

### 2.1 Component Breakdown

1. **Host Compaction Coordinator (`scripts/compact_host_disk.sh`)**:
   - Manages lockfiles to prevent concurrent compaction runs.
   - Measures guest ext4 disk space usage via `df -B1 /`.
   - Resolves the host `.vhdx` path from Windows user profile environment variables.
   - Queries the physical `.vhdx` file size on the host using `powershell.exe`.
   - Computes reclaimable slack space. If slack exceeds the 10GB threshold (configurable via `--threshold-gb`), initiates compaction.

2. **Linux Guest Discard Routine**:
   - Executes `fstrim -v /` inside the WSL2 guest.
   - Informs the virtual SCSI storage driver that freed ext4 blocks contain zeroes.

3. **PowerShell Execution Bridge (`scripts/lib/compact_vhd.ps1`)**:
   - Executes via non-interactive interop: `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ...`.
   - Inspects Hyper-V module availability (`Get-Command Optimize-VHD -ErrorAction SilentlyContinue`).
   - Executes `Optimize-VHD -Path <vhdx_path> -Mode Full`.
   - If `Optimize-VHD` is unavailable, attempts fallback using temporary `diskpart` script commands (`select vdisk file=...`, `compact vdisk`).

---

## 3. Threshold Detection Logic & Metrics

### 3.1 Mathematical Calculation

$$\text{Ext4 Used Space (Bytes)} = \text{Blocks Used} \times \text{Block Size}$$
$$\text{Host VHDX Size (Bytes)} = \text{FileInfo.Length of backing } ext4.vhdx$$
$$\text{Reclaimable Slack Space (Bytes)} = \text{Host VHDX Size} - \text{Ext4 Used Space}$$

### 3.2 Decision Matrix

| Condition | Action | Result |
|---|---|---|
| Slack Space < 10GB | Skip host compaction | Log telemetry: `compaction_skipped_below_threshold` |
| Slack Space >= 10GB (Hyper-V available) | Run `fstrim` + `Optimize-VHD` | Host `.vhdx` shrinks; log space reclaimed |
| Slack Space >= 10GB (Hyper-V missing, Diskpart ok) | Run `fstrim` + `diskpart` fallback | Host `.vhdx` shrinks via storage service |
| Slack Space >= 10GB (Permission denied) | Log advisory remediation | Emit guidance for elevated PowerShell execution |
| Host Drive Free Space < 5GB | Abort compaction | Prevent temporary allocation starvation |

---

## 4. Safety Preconditions & Invariant Protections

### 4.1 Guardrail Compliance & Tier Classification
- **Tier 2 Whitelist**: `scripts/compact_host_disk.sh` is registered as a pre-authorized Tier 2 script in `scripts/hooks/pre_tool_guard.sh` and `.claude/rules/safety-tiers.md`.
- **Prohibited Commands**: The script never invokes destructive commands such as `wsl --unregister`, `wsl --shutdown`, or `diskpart clean`.
- **Read-Only Host Inspection**: Path resolution only reads file attributes from `/mnt/c/Users/<user>/AppData/Local/Packages/.../ext4.vhdx`. It never writes to Windows system directories.

### 4.2 Concurrency & Lockfile Management
- A flock-based lockfile `/tmp/os_manager_compaction.lock` prevents overlapping compaction runs.
- If a compaction is already active, subsequent invocations exit immediately with Exit Code 0 and an advisory message.

---

## 5. Integration with Maintenance Pipeline

### 5.1 System Cleanup Integration (`scripts/clean_system.sh`)
`scripts/clean_system.sh` supports a `--compact` flag:
- In default mode (`clean_system.sh`), cleans caches and reports space.
- In full mode (`clean_system.sh --all` or `--compact`), triggers `scripts/compact_host_disk.sh` after cache eviction.

### 5.2 Systemd User Unit Integration (`systemd/os-maintenance.service`)
Update `systemd/os-maintenance.service` to invoke:
```ini
ExecStart=/home/rizz/dev/os-manager/scripts/clean_system.sh --all
```

---

## 6. Resilience & Comprehensive Error Recovery

1. **Missing Windows Interop**:
   - If `powershell.exe` is inaccessible (interop disabled in `/etc/wsl.conf`), the script logs a warning and skips host compaction gracefully.
2. **Missing Hyper-V Module**:
   - The script detects missing `Hyper-V` cmdlets and pivots to `diskpart` automation.
3. **Elevated Privilege Requirement**:
   - If non-elevated user context cannot compact the VHDX, the script outputs a ready-to-run one-line command for the user's Windows terminal without failing the Linux maintenance run.
4. **VHDX Path Auto-Discovery**:
   - The script searches standard WSL distribution package paths under `%LOCALAPPDATA%\Packages` and `%USERPROFILE%\AppData\Local\Packages` dynamically.

---

## 7. Verification & Automated Testing Plan

### 7.1 Unit & Script Verification (`tests/test_compact_host_disk.sh`)
- Test `--dry-run` flag reporting calculated slack space accurately.
- Test lockfile acquisition and release mechanics.
- Test threshold calculation logic with mock VHDX sizes.
- Verify `powershell.exe` command formatting and escaping.

### 7.2 Harness Test Suite Extension (`tests/test_harness.sh`)
- Assert `scripts/compact_host_disk.sh` passes `bash -n` and `shellcheck`.
- Assert `scripts/compact_host_disk.sh --help` returns Exit Code 0.
- Assert `pre_tool_guard.sh` authorizes `compact_host_disk.sh` under Tier 2.

---

## 8. Alternative Architectural Plans

### 8.1 Backup Plan: Native WSL2 Sparse VHD Mode
- **Mechanism**: Execute `fstrim -v /` inside WSL2 after configuring sparse VHD mode on the host (`wsl --manage Debian --set-sparse true`).
- **Activation**: Applied on Windows 11 systems running WSL 2.0.0 or newer where sparse VHD is enabled.

### 8.2 Backup Plan: Userland Desktop Notification & Interactive Compactor
- **Mechanism**: Linux maintenance outputs a `.bat` script to `/mnt/c/Users/<user>/Desktop/compact_wsl.bat` and issues a Windows desktop alert when slack exceeds 15GB.
- **Activation**: Used when automated PowerShell execution is blocked by organizational security policies.

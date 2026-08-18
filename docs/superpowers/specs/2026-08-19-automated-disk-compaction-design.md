# Technical Design Specification: Automated Host Disk Compaction (Deliverable 3.2)

## 1. Executive Summary and Objective

This document defines the technical specification for **Automated Host Disk Compaction** (Deliverable 3.2 from `docs/PRD.md`).

Virtual hard disk (`.vhdx`) storage in WSL2 expands dynamically on the Windows host as files are written in the Linux guest. Deleting packages and build caches via `scripts/clean_system.sh` marks ext4 blocks as free. However, the host `.vhdx` file does not automatically shrink. This specification defines a safe, threshold-driven disk compaction mechanism that mandates Linux `sudo fstrim -v /` block discards prior to triggering PowerShell `Optimize-VHD`.

---

## 2. System Architecture and Component Interaction

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
 │ • Step 2: Executes `sudo fstrim -v /` to discard unused ext4 filesystem blocks (Mandatory)  │
 └──────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                │
 ┌──────────────────────────────────────────────▼───────────────────────────────────────────────┐
 │ HOST COMPACTION COORDINATOR (`scripts/compact_host_disk.sh`)                                 │
 │ • Step 1: Executes `sudo fstrim -v /` (Invariant Check)                                      │
 │ • Step 2: Queries ext4 used bytes vs Windows host `ext4.vhdx` file size via PowerShell       │
 │ • Step 3: Evaluates threshold: Slack Space = (Host VHDX Size - Ext4 Used Size) >= 10GB       │
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
   - Executes `sudo fstrim -v /` inside the Linux guest to zero and discard unallocated ext4 blocks.
   - Measures guest ext4 disk space usage via `df -B1 /`.
   - Resolves the host `.vhdx` path from Windows user profile environment variables in read-only mode.
   - Queries the physical `.vhdx` file size on the host using `powershell.exe`.
   - Computes reclaimable slack space. If slack exceeds the 10GB threshold (configurable via `--threshold-gb`), initiates host compaction.

2. **Mandatory Linux Guest Discard Routine**:
   - Invariant: `compact_host_disk.sh` MUST execute `sudo fstrim -v /` inside Linux before invoking host compaction.
   - Informs the virtual SCSI storage driver that freed ext4 blocks contain zeroes, enabling Hyper-V compaction to release underlying disk clusters.

3. **PowerShell Execution Bridge (`scripts/lib/compact_vhd.ps1`)**:
   - Executes via non-interactive interop: `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ...`.
   - Inspects Hyper-V module availability (`Get-Command Optimize-VHD -ErrorAction SilentlyContinue`).
   - Executes `Optimize-VHD -Path <vhdx_path> -Mode Full`.
   - If `Optimize-VHD` is unavailable, attempts fallback using temporary `diskpart` script commands (`select vdisk file=...`, `compact vdisk`).

---

## 3. Threshold Detection Logic and Metrics

### 3.1 Mathematical Calculation

$$\text{Ext4 Used Space (Bytes)} = \text{Blocks Used} \times \text{Block Size}$$
$$\text{Host VHDX Size (Bytes)} = \text{FileInfo.Length of backing } ext4.vhdx$$
$$\text{Reclaimable Slack Space (Bytes)} = \text{Host VHDX Size} - \text{Ext4 Used Space}$$

### 3.2 Decision Matrix

| Condition | Action | Result |
|---|---|---|
| Slack Space < 10GB | Skip host compaction | Log telemetry: `compaction_skipped_below_threshold` |
| Slack Space >= 10GB (Hyper-V available) | Run `sudo fstrim -v /` + `Optimize-VHD` | Host `.vhdx` shrinks; log space reclaimed |
| Slack Space >= 10GB (Hyper-V missing, Diskpart ok) | Run `sudo fstrim -v /` + `diskpart` fallback | Host `.vhdx` shrinks via storage service |
| Slack Space >= 10GB (Permission denied) | Log advisory remediation | Emit guidance for elevated PowerShell execution |
| Host Drive Free Space < 5GB | Abort compaction | Prevent temporary allocation starvation |

---

## 4. Safety Preconditions and Invariant Protections

### 4.1 Guardrail Compliance and Tier Classification
- **Tier 2 Whitelist**: `scripts/compact_host_disk.sh` is registered as a pre-authorized Tier 2 script in `scripts/hooks/pre_tool_guard.sh` and `.claude/rules/safety-tiers.md`.
- **Prohibited Commands**: The script never invokes destructive commands such as `wsl --unregister`, `wsl --shutdown`, or `diskpart clean`.
- **Read-Only Host Inspection**: Path resolution only reads file attributes from `/mnt/c/Users/<user>/AppData/Local/Packages/.../ext4.vhdx`. It never writes to Windows system directories.

### 4.2 Concurrency and Lockfile Management
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

## 6. Resilience and Comprehensive Error Recovery

1. **Missing Windows Interop**:
   - If `powershell.exe` is inaccessible (interop disabled in `/etc/wsl.conf`), the script logs a warning and skips host compaction gracefully after executing `fstrim`.
2. **Missing Hyper-V Module**:
   - The script detects missing `Hyper-V` cmdlets and pivots to `diskpart` automation.
3. **Elevated Privilege Requirement**:
   - If non-elevated user context cannot compact the VHDX, the script outputs a ready-to-run one-line command for the user's Windows terminal without failing the Linux maintenance run.
4. **VHDX Path Auto-Discovery**:
   - The script searches standard WSL distribution package paths under `%LOCALAPPDATA%\Packages` and `%USERPROFILE%\AppData\Local\Packages` dynamically.

---

## 7. Verification and Automated Testing Plan

### 7.1 Unit and Script Verification (`tests/test_compact_host_disk.sh`)
- Test `--dry-run` flag reporting calculated slack space accurately.
- Test lockfile acquisition and release mechanics.
- Test that `sudo fstrim -v /` is invoked prior to compaction calls.
- Test threshold calculation logic with mock VHDX sizes.
- Verify `powershell.exe` command formatting and escaping.

### 7.2 Harness Test Suite Extension (`tests/test_harness.sh`)
- Assert `scripts/compact_host_disk.sh` passes `bash -n` and `shellcheck`.
- Assert `scripts/compact_host_disk.sh --help` returns Exit Code 0.
- Assert `pre_tool_guard.sh` authorizes `compact_host_disk.sh` under Tier 2.

---

## 8. Rollout Sequence and Implementation DAG

Automated Host Disk Compaction belongs to Stage 2 of the implementation plan:

1. **Stage 1 (Foundation Libraries and Tracing)**:
   - Deliverable 3.4: Hook Performance Tracing (`scripts/hooks/lib/trace_helper.sh`, `scripts/hook_benchmark.sh`).
   - Deliverable 4.1: Cross-Distribution Engine (`scripts/lib/distro.sh`, generalized package guardrails).
2. **Stage 2 (Base System Services, Notifications, and Sandbox)**:
   - Deliverable 3.1: Prometheus Metrics Exporter (`scripts/metrics_exporter.py`).
   - Deliverable 3.3: Desktop Notification Bridge (`scripts/notify_host.sh`).
   - Deliverable 3.2: Automated Host Disk Compaction (`scripts/compact_host_disk.sh`).
   - Deliverable 4.4: Agent Workspace Virtualization (`scripts/sandbox_exec.sh`).
3. **Stage 3 (Multi-Agent Mesh and Disaster Recovery)**:
   - Deliverable 4.2: Inter-Agent Message Bus (`scripts/agent_bus.py`, `scripts/bus_send.sh`).
   - Deliverable 4.3: Automated Disaster Recovery Provisioning (`scripts/bootstrap_wsl.ps1`, `scripts/post_bootstrap.sh`).

# Kernel Watchdog and Polling Overhead Reduction Design Specification

- **Document ID**: `SPEC-2026-08-28-KERNEL-WATCHDOG-01`
- **Author**: os-manager Architecture & Performance Team
- **Date**: 2026-08-28
- **Status**: Approved for Implementation
- **Target Kernel**: Linux Kernel 6.6+ / 6.12 LTS on Debian 13 (Trixie), WSL2 & Native Linux

---

## 1. Executive Summary & Problem Statement

Workstation, development, and low-latency interactive audio/terminal workloads frequently suffer from micro-stutters, periodic timer interrupts, and cache-line evictions caused by default kernel diagnostic watchdogs and frequent kernel polling timers:
1. **NMI Watchdog Interrupt Jitter**: The Non-Maskable Interrupt (NMI) watchdog generates high-frequency hardware interrupts across all CPU cores to detect hardware lockups, stealing CPU cycles and causing latency spikes during parallel compilation and real-time audio processing.
2. **Soft Lockup & Generic Watchdog Overhead**: Kernel watchdog timers keep CPU cores waking up periodically from low-power C-states, degrading single-core boost consistency and increasing idle power consumption.
3. **High-Frequency VM Statistics Polling (`vm.stat_interval = 1`)**: The kernel VM subsystem wakes up every single second to calculate memory zone statistics, generating unnecessary timer ticks across idle cores.
4. **Timer Migration Jitter (`kernel.timer_migration = 1`)**: Timers are migrated across CPU cores to consolidate wakeups, which can inadvertently bounce active timers into cores executing latency-critical user tasks and thrash L1/L2 cache locality.

This specification introduces the **Kernel Watchdog & Polling Overhead Reduction** engine to `os-manager` via `osm tune kernel` and integrates it into the unified `osm tune system` workflow backed by atomic snapshot and rollback guarantees.

---

## 2. Technical Architecture & Sysctl Parameter Matrix

The kernel watchdog engine manages an immutable, idempotent drop-in configuration at `/etc/sysctl.d/99-osm-kernel.conf`.

### 2.1 Sysctl Parameter Matrix

| Sysctl Key | Target Value | Baseline / Default | Architectural Rationale |
|---|---|---|---|
| `kernel.nmi_watchdog` | `0` | `1` | Disables periodic NMI hardware interrupts across all cores, eliminating timer jitter during intensive compilation and latency-sensitive workloads. |
| `kernel.watchdog` | `0` | `1` | Disables soft lockup and general kernel watchdog background polling on stable developer workstations. |
| `vm.stat_interval` | `10` | `1` | Reduces VM statistics polling frequency from 1s to 10s, drastically reducing unnecessary kernel timer wakeups. |
| `kernel.timer_migration` | `0` | `1` | Disables migration of timers across CPU cores, preserving CPU cache locality and eliminating inter-core timer bounce. |

---

## 3. Module & Component Design (`os_manager/commands/tune.py`)

### 3.1 Constants & Drop-in Path
```python
SYSCTL_KERNEL_PATH = "/etc/sysctl.d/99-osm-kernel.conf"
```

### 3.2 Generator Function
```python
def generate_kernel_sysctl_config(
    nmi_watchdog: int = 0,
    watchdog: int = 0,
    vm_stat_interval: int = 10,
    timer_migration: int = 0,
) -> str:
    """Generate sysctl configuration for reducing kernel polling and watchdog jitter."""
    return (
        "# /etc/sysctl.d/99-osm-kernel.conf - Managed by os-manager\n"
        f"kernel.nmi_watchdog = {nmi_watchdog}\n"
        f"kernel.watchdog = {watchdog}\n"
        f"vm.stat_interval = {vm_stat_interval}\n"
        f"kernel.timer_migration = {timer_migration}\n"
    )
```

### 3.3 Audit Subsystem Function
```python
def audit_kernel_subsystem() -> dict[str, Any]:
    """Inspect active kernel watchdog and timer polling parameters and drop-in status."""
    return {
        "nmi_watchdog": _read_sysctl("kernel.nmi_watchdog"),
        "watchdog": _read_sysctl("kernel.watchdog"),
        "vm_stat_interval": _read_sysctl("vm.stat_interval"),
        "timer_migration": _read_sysctl("kernel.timer_migration"),
        "kernel_dropin_present": Path(SYSCTL_KERNEL_PATH).is_file(),
    }
```

### 3.4 Integration with Master Telemetry & Snapshots
1. **Snapshot Invariant**: `SYSCTL_KERNEL_PATH` is registered in `create_system_snapshot()` target files.
2. **Master Telemetry**: `collect_tune_telemetry()` exposes `subsystems.kernel` with the dictionary returned by `audit_kernel_subsystem()`.
3. **Master System Tuning**: `apply_system_tuning()` writes `SYSCTL_KERNEL_PATH` and reloads sysctl via `sysctl --system`.

---

## 4. CLI Routing & Interfaces

### 4.1 CLI Command Signature under `osm tune kernel`
- `osm tune kernel`: Audit active kernel watchdog and polling parameters.
- `osm tune kernel --apply [--dry-run]`: Generate and apply `/etc/sysctl.d/99-osm-kernel.conf`.
- `osm tune kernel --revert`: Revert kernel drop-in from snapshot.
- `osm tune kernel --json`: Output machine-readable JSON structure for agent consumption.

---

## 5. Verification & Test Plan (TDD)

1. **Unit Test Suite (`tests/test_tune_kernel.py`)**:
   - `test_generate_kernel_sysctl_config_defaults`: Asserts exact sysctl lines generated for `nmi_watchdog=0`, `watchdog=0`, `vm_stat_interval=10`, `timer_migration=0`.
   - `test_generate_kernel_sysctl_config_custom`: Asserts custom parameter configuration.
   - `test_audit_kernel_subsystem_structure`: Asserts return dictionary keys.
   - `test_audit_kernel_subsystem_mocked`: Asserts parsing of sysctl parameters and file presence detection.
2. **CLI & System Integration (`tests/test_cli.py`, `tests/test_tune_system.py`)**:
   - Verify `osm tune kernel`, `osm tune kernel --apply`, and `osm tune kernel --json` routing.
   - Verify master telemetry contains `subsystems.kernel`.
3. **Snapshot Revert Verification (`tests/test_tune_revert.py`)**:
   - Ensure snapshots back up and restore `/etc/sysctl.d/99-osm-kernel.conf` cleanly.

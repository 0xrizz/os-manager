# sched_ext Dynamic eBPF Scheduler Subsystem Design Specification

- **Document ID**: `SPEC-2026-08-28-SCHED-EXT-01`
- **Author**: os-manager Architecture & Performance Team
- **Date**: 2026-08-28
- **Status**: Approved for Implementation
- **Target Kernel**: Linux Kernel 6.12+ LTS with `CONFIG_SCHED_CLASS_EXT=y` on Debian 13 (Trixie), Custom Linux Kernels (CachyOS, XanMod, Liquorix), with Graceful EEVDF Fallback

---

## 1. Executive Summary & Problem Statement

Linux 6.12+ introduced the `sched_ext` (Extensible Scheduler Class) infrastructure, enabling dynamically loaded eBPF-based CPU schedulers to govern kernel thread scheduling directly from user space without modifying kernel source code or rebooting. While standard Linux CFS/EEVDF (Earliest Eligible Virtual Deadline First) scheduling operates as a general-purpose compromise, high-intensity developer workloads exhibit distinct performance needs:
1. **Interactive Gaming & Low Latency Audio/UI**: Requires strict latency guarantees and prioritization for active user-facing threads (`scx_lavd`).
2. **Heterogeneous CPU Workloads**: Requires intelligent balancing between Performance (P) and Efficiency (E) cores without kernel-level thermal or frequency stuttering (`scx_bpfland`).
3. **Multi-Threaded Compilation & Batch Throughput**: Demands maximal CPU saturation and minimal context-switch overhead during parallel builds (`cargo build`, `gcc`, `pytest`) (`scx_rusty`).
4. **Graceful Fallback on Stock Kernels**: Kernels compiled without `CONFIG_SCHED_CLASS_EXT=y` (such as standard Debian 13 release kernels) must not crash or degrade, but rather maintain optimized baseline EEVDF slice parameters.

This specification introduces the **`sched_ext` Dynamic eBPF Scheduler Subsystem** (`os_manager.scheduler.scx`) to `os-manager`. It provides multi-method compatibility probing, profile selection, systemd service management, on-demand execution, and master telemetry integration under `osm tune scheduler`.

---

## 2. Technical Architecture & Component Hierarchy

The subsystem architecture separates compatibility probing, profile configuration, and process/service lifecycle management:

```text
                               ┌──────────────────────────────────────────────┐
                               │           CLI Dispatcher                     │
                               │  - osm tune scheduler                        │
                               │  - osm tune scheduler --scx <action>         │
                               │  - osm tune scheduler --profile <profile>    │
                               └──────────────────────┬───────────────────────┘
                                                      │
                               ┌──────────────────────▼───────────────────────┐
                               │       os_manager.scheduler.scx               │
                               │  - ScxSupportStatus & Dataclasses            │
                               │  - probe_sched_ext_support()                 │
                               │  - SCX_PROFILES registry                     │
                               │  - ScxLifecycleManager                       │
                               │  - generate_scx_systemd_unit()               │
                               └──────────────────────┬───────────────────────┘
                                                      │
               ┌──────────────────────────────────────┼──────────────────────────────────────┐
               ▼                                      ▼                                      ▼
    ┌──────────────────────┐               ┌──────────────────────┐               ┌──────────────────────┐
    │  Kernel Probe Engine │               │   Systemd Daemon     │               │   EEVDF Baseline     │
    │  - /sys/kernel/sched │               │   /etc/systemd/      │               │   - sched_base_slice │
    │    _ext/state        │               │   system/scx.service │               │   - User Slices      │
    │  - /boot/config-*    │               │   (Persistent)       │               │   (Graceful Fallback)│
    │  - $PATH discovery   │               │   (scripts/sudo_exec)│               │   (tune.py)          │
    └──────────────────────┘               └──────────────────────┘               └──────────────────────┘
```

---

## 3. Data Models & Scheduler Profile Registry (`os_manager.scheduler.scx`)

### 3.1 Data Models

```python
from dataclasses import dataclass, field
from typing import Literal

ScxProfileName = Literal["lavd", "bpfland", "rusty", "central", "simple"]

@dataclass
class ScxProfile:
    name: ScxProfileName
    binary_name: str
    description: str
    recommended_for: str
    default_args: list[str] = field(default_factory=list)

@dataclass
class ScxSupportStatus:
    kernel_supported: bool
    sysfs_present: bool
    active_scheduler: str | None
    installed_schedulers: list[str] = field(default_factory=list)
    service_active: bool = False
    service_enabled: bool = False
    details: str = ""
```

### 3.2 Standard Profile Registry

| Profile Name | Binary | Description & Target Workload |
|---|---|---|
| `lavd` | `scx_lavd` | Low-latency audio, desktop responsiveness, and gaming. Prioritizes latency-critical interactive tasks. |
| `bpfland` | `scx_bpfland` | Heterogeneous core balancing (Intel Alder/Raptor Lake, AMD Zen4c). Balances interactive vs compute tasks. |
| `rusty` | `scx_rusty` | Multi-threaded compilation and batch compute. Maximizes cache locality and parallel throughput for `cargo`/`gcc`. |
| `central` | `scx_central` | Centralized queueing for high-core count workstation/server CPUs. |
| `simple` | `scx_simple` | Minimal baseline reference scheduler for verification and test suites. |

---

## 4. Multi-Method Compatibility & State Probing Engine

### 4.1 Probing Hierarchy (`probe_sched_ext_support()`)

1. **Sysfs State Node Check**:
   - Inspect `/sys/kernel/sched_ext/state`. If readable:
     - `enabled`: Sched_ext is compiled and actively managing scheduling.
     - `disabled`: Sched_ext is compiled into kernel but no eBPF scheduler is currently loaded.
2. **Kernel Configuration File Inspection**:
   - If sysfs node is absent, inspect `/boot/config-$(uname -r)` or `/proc/config.gz` for `CONFIG_SCHED_CLASS_EXT=y`.
   - If not set, mark `kernel_supported=False` with remediation hint ("Stock Debian 13 kernel detected. EEVDF baseline active. To enable sched_ext, install a 6.12+ kernel with CONFIG_SCHED_CLASS_EXT=y such as CachyOS or XanMod").
3. **Binary Discovery**:
   - Inspect `$PATH` (and `/usr/local/bin`, `/usr/bin`, `~/.cargo/bin`) for binaries matching `scx_*`.
4. **Active Scheduler & Service Detection**:
   - Read `/sys/kernel/sched_ext/root/ops` or execute `pgrep -a -f 'scx_'` to detect running scheduler.
   - Check systemd status of `scx.service` via `systemctl is-active scx.service` and `systemctl is-enabled scx.service`.

---

## 5. Lifecycle Management & Systemd Integration

### 5.1 Systemd Unit Template Generator

`generate_scx_systemd_unit(binary_path: str, profile_args: list[str]) -> str`:
```ini
# /etc/systemd/system/scx.service - Managed by os-manager
[Unit]
Description=sched_ext eBPF Kernel Scheduler
Documentation=https://github.com/sched-ext/scx
After=network.target local-fs.target
ConditionPathExists=/sys/kernel/sched_ext

[Service]
Type=simple
ExecStart={binary_path} {joined_args}
Restart=on-failure
RestartSec=2s
LimitMEMLOCK=infinity

[Install]
WantedBy=multi-user.target
```

### 5.2 Lifecycle Operations

- **Start / Switch Scheduler**:
  - `start_scx_scheduler(profile: ScxProfileName, runtime_only: bool = False) -> dict[str, Any]`
  - If `runtime_only=False`: Writes `/etc/systemd/system/scx.service` via `./scripts/sudo_exec.sh`, reloads systemd daemon, and starts the service.
  - If `runtime_only=True`: Spawns the binary directly as a detached background daemon with PID tracking.
- **Stop Scheduler**:
  - `stop_scx_scheduler() -> dict[str, Any]`
  - Stops `scx.service` or terminates running `scx_*` processes. Kernel automatically falls back to default EEVDF scheduling without interruption.
- **Enable / Disable Autostart**:
  - `enable_scx_service()` / `disable_scx_service()` via `systemctl enable/disable scx.service`.

---

## 6. Master CLI & Telemetry Integration

### 6.1 CLI Command Signatures in `osm tune scheduler`

```text
osm tune scheduler                     # Audit active scheduler (EEVDF + sched_ext)
osm tune scheduler --json              # Emit structured JSON telemetry
osm tune scheduler --scx status        # Inspect sched_ext probing details
osm tune scheduler --scx start --profile <lavd|bpfland|rusty|central>
osm tune scheduler --scx stop          # Stop eBPF scheduler and restore EEVDF
osm tune scheduler --scx enable --profile <name> # Enable persistent boot service
osm tune scheduler --scx disable       # Disable persistent service
osm tune scheduler --base-slice-ns 2000000 # Tune baseline EEVDF slice
```

### 6.2 Master Telemetry Schema

`collect_tune_telemetry()` in `os_manager/commands/tune.py` aggregates scheduler metrics into `subsystems.scheduler`:
```json
{
  "subsystems": {
    "scheduler": {
      "base_slice_ns": "2000000",
      "cfs_bandwidth_slice_us": "3000",
      "session_slice_configured": true,
      "background_slice_configured": true,
      "sched_ext": {
        "kernel_supported": false,
        "sysfs_present": false,
        "active_scheduler": null,
        "installed_schedulers": [],
        "service_active": false,
        "service_enabled": false,
        "recommendation": "Kernel 6.12.105 lacks CONFIG_SCHED_CLASS_EXT. Using Linux EEVDF baseline tuning."
      }
    }
  }
}
```

---

## 7. Verification & Test Plan (TDD)

1. **Compatibility & Probing Tests (`tests/scheduler/test_scx_probe.py`)**:
   - `test_probe_sched_ext_supported_sysfs_enabled`: Mock `/sys/kernel/sched_ext/state` returning `enabled`.
   - `test_probe_sched_ext_supported_config_file`: Mock `/boot/config-x` with `CONFIG_SCHED_CLASS_EXT=y`.
   - `test_probe_sched_ext_unsupported_graceful`: Mock stock kernel without config flag and assert graceful report.
   - `test_discover_installed_schedulers`: Mock `shutil.which` finding `scx_lavd` and `scx_bpfland`.
2. **Profile & Service Generation Tests (`tests/scheduler/test_scx_lifecycle.py`)**:
   - `test_generate_scx_systemd_unit`: Verify exact systemd unit string generation with `LimitMEMLOCK=infinity`.
   - `test_profile_registry_defaults`: Verify `lavd`, `bpfland`, `rusty`, `central` definitions.
   - `test_start_and_stop_scx_scheduler_mocked`: Mock systemctl execution and process termination.
3. **CLI & Telemetry Integration Tests (`tests/test_cli.py`, `tests/test_tune_scheduler.py`)**:
   - Verify `osm tune scheduler --scx status` and `osm tune scheduler --scx start` routing.
   - Verify `collect_tune_telemetry()` includes nested `subsystems.scheduler.sched_ext`.

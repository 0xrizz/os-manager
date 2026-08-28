# Autonomous PSI Feedback & zRAM Compaction Daemon Design Specification

- **Document ID**: `SPEC-2026-08-28-PSI-DAEMON-01`
- **Author**: os-manager Architecture & Performance Team
- **Date**: 2026-08-28
- **Status**: Approved for Implementation
- **Target Kernel**: Linux Kernel 6.6+ / 6.12 LTS on Debian 13 (Trixie), WSL2 & Native Linux with `/proc/pressure/*` and zRAM Multi-Stream Support

---

## 1. Executive Summary & Problem Statement

Modern Linux developer workstations experience intense, bursty resource contention during parallel software compilation (`cargo build`, `gcc`, `pytest`), local Large Language Model (LLM) inference (`llama.cpp`, `vLLM`), and container workload execution. Traditional threshold monitoring (based merely on percentage of used RAM) fails because high RAM usage is desirable (for page caches); what degrades interactive responsiveness is **Memory & I/O Stall Time** (tasks waiting on memory allocation, direct reclaim, or swap thrashing).

Linux Pressure Stall Information (PSI) provides real-time metrics (`/proc/pressure/{cpu,memory,io}`) measuring the exact percentage of wall-clock time tasks spend stalled. However, standard Linux lacks an autonomous user-space daemon to reactively alleviate memory pressure before the Out-Of-Memory (OOM) killer fires.

This specification introduces the **Autonomous PSI Feedback & zRAM Compaction Daemon** (`os_manager.memory.psi_daemon`) to `os-manager`. It provides:
1. Low-overhead kernel PSI event monitoring (`epoll` triggers with periodic async fallback).
2. A 3-Tier Staged Mitigation Engine that autonomously compacts zRAM memory, triggers MGLRU page aging, and throttles background cgroup slices.
3. Debounced cooldown mechanics preventing churn and tight loops.
4. CLI operations via `osm psi` and unified memory telemetry under `osm tune memory`.

---

## 2. Technical Architecture & Component Hierarchy

The subsystem architecture separates metric collection, threshold evaluation, mitigation execution, and daemon lifecycle management:

```text
                               ┌──────────────────────────────────────────────┐
                               │               CLI Dispatcher                 │
                               │   - osm psi [status|monitor|compact|daemon]  │
                               │   - osm tune memory                          │
                               └──────────────────────┬───────────────────────┘
                                                      │
                               ┌──────────────────────▼───────────────────────┐
                               │      os_manager.memory.psi_daemon            │
                               │   - PsiMetrics & PsiThresholds Dataclasses   │
                               │   - parse_psi_metrics(subsystem)             │
                               │   - PsiMonitorEngine (epoll + poller)        │
                               │   - StagedMitigationController (Tier 1-3)    │
                               │   - generate_psi_systemd_unit()              │
                               └──────────────────────┬───────────────────────┘
                                                      │
               ┌──────────────────────────────────────┼──────────────────────────────────────┐
               ▼                                      ▼                                      ▼
    ┌──────────────────────┐               ┌──────────────────────┐               ┌──────────────────────┐
    │  /proc/pressure/*    │               │  /sys/block/zram*/   │               │   /etc/systemd/      │
    │  - cpu, memory, io   │               │    compact           │               │   system/osm-psi.srv │
    │  - some & full avg   │               │  (zRAM Compaction)   │               │   (scripts/sudo_exec)│
    └──────────────────────┘               └──────────────────────┘               └──────────────────────┘
```

---

## 3. Data Models & PSI Parser (`os_manager.memory.psi_daemon`)

### 3.1 Data Models

```python
from dataclasses import dataclass, field
from typing import Literal

PsiSubsystem = Literal["cpu", "memory", "io"]
MitigationTier = Literal["none", "tier1_compact", "tier2_mglru_sync", "tier3_throttle_drop"]

@dataclass
class PsiReading:
    avg10: float
    avg60: float
    avg300: float
    total: int

@dataclass
class PsiMetrics:
    cpu_some: PsiReading
    memory_some: PsiReading
    memory_full: PsiReading
    io_some: PsiReading
    io_full: PsiReading
    timestamp: str

@dataclass
class PsiThresholds:
    tier1_memory_some_avg10: float = 10.0
    tier1_memory_some_avg60: float = 5.0
    tier2_memory_some_avg10: float = 25.0
    tier2_memory_full_avg10: float = 10.0
    tier3_memory_full_avg10: float = 40.0
    cooldown_seconds: int = 20
```

### 3.2 Parsing Logic (`parse_psi_file(path: str) -> dict[str, PsiReading]`)
Parses lines from `/proc/pressure/{cpu,memory,io}`:
```text
some avg10=0.00 avg60=0.15 avg300=0.26 total=33557507
full avg10=0.00 avg60=0.15 avg300=0.26 total=32458166
```
Extracts `avg10`, `avg60`, `avg300`, and `total` microseconds into structured `PsiReading` records.

---

## 4. 3-Tier Staged Mitigation Engine & Cooldown Invariants

### 4.1 Mitigation Tiers

| Tier | Trigger Thresholds | Autonomous Mitigation Actions | Impact & Rationale |
|---|---|---|---|
| **Tier 1: Mild Pressure** | `memory.some.avg10 >= 10.0` OR `memory.some.avg60 >= 5.0` | Trigger zRAM Compaction:<br>`echo 1 > /sys/block/zram*/compact` | Re-compresses and consolidates fragmented zRAM memory pages without evicting active file cache or interrupting tasks. |
| **Tier 2: Moderate Pressure** | `memory.some.avg10 >= 25.0` OR `memory.full.avg10 >= 10.0` | 1. Trigger zRAM Compaction.<br>2. Trigger MGLRU page generation kick:<br>`echo 1 > /sys/kernel/mm/lru_gen/enabled`<br>3. Async dirty sync (`sync -f /`). | Accelerates inactive cold page identification, freeing physical RAM buffers before allocation stalls cause task freeze. |
| **Tier 3: Critical Stall** | `memory.full.avg10 >= 40.0` | 1. Log incident to `backups/logs/psi_events.jsonl`.<br>2. Safe page cache drop:<br>`echo 1 > /proc/sys/vm/drop_caches`.<br>3. Deprioritize `background.slice` cgroup. | Prevents complete kernel lockup or aggressive uncontrolled OOM killing of developer IDE/shell sessions. |

### 4.2 Debounce & Cooldown Guarantee
- The engine enforces a **Cooldown Window** (default `20` seconds) after any tier action is executed.
- During the cooldown window, metric readings continue to be tracked, but further mitigation triggers are suppressed to allow kernel memory subsystems to stabilize without thrashing CPU cycles on continuous compaction.

---

## 5. Dual Monitoring Engine: `epoll` Event-Driven & Async Fallback

### 5.1 Event-Driven `epoll` Trigger
- Registers event triggers directly on `/proc/pressure/memory` using Linux `epoll` with threshold triggers (e.g., `some 10000 1000000` = 10ms stall in a 1-second window).
- Yields **0% CPU utilization** while system pressure is normal; process awakens only when kernel fires a stall threshold notification.

### 5.2 Async Periodic Fallback Poller
- If `epoll` registration fails (e.g. running inside unprivileged containers or virtualized WSL2 kernels without eventfd support), daemon smoothly transitions to periodic async polling (`asyncio.sleep(interval)` with configurable 2s - 5s rate).

---

## 6. Systemd Service Daemon & Lifecycle Management

### 6.1 Unit Template Generator (`generate_psi_systemd_unit()`)

`/etc/systemd/system/osm-psi.service`:
```ini
# /etc/systemd/system/osm-psi.service - Managed by os-manager
[Unit]
Description=os-manager Autonomous PSI Memory Feedback & zRAM Compaction Daemon
Documentation=https://github.com/0xrizz/os-manager
After=systemd-modules-load.service zramswap.service

[Service]
Type=simple
ExecStart=/usr/local/bin/osm psi daemon --run
Restart=always
RestartSec=5s
Nice=-5
MemoryHigh=64M
MemoryMax=128M

[Install]
WantedBy=multi-user.target
```

### 6.2 Daemon Lifecycle Operations
- `osm psi daemon status`: Check running status and metrics from systemd / process.
- `osm psi daemon start`: Start daemon service.
- `osm psi daemon stop`: Stop daemon service.
- `osm psi daemon enable`: Enable persistent autostart across reboots.
- `osm psi daemon disable`: Disable persistent autostart.

---

## 7. Master CLI & Telemetry Integration

### 7.1 CLI Commands under `osm psi`

```text
osm psi status [--json]           # View formatted table of CPU, Memory, and I/O PSI readings
osm psi monitor [--interval 1]    # Live real-time terminal monitor
osm psi compact                   # On-demand manual zRAM compaction trigger
osm psi daemon [start|stop|status|enable|disable]  # Manage background service
```

### 7.2 Telemetry Integration in `collect_tune_telemetry()`

```json
{
  "subsystems": {
    "psi": {
      "supported": true,
      "cpu": {"some_avg10": 0.0, "some_avg60": 0.0, "some_avg300": 0.06},
      "memory": {"some_avg10": 0.0, "full_avg10": 0.0, "some_avg60": 0.15},
      "io": {"some_avg10": 1.72, "full_avg10": 1.72, "some_avg60": 0.43},
      "daemon_active": true,
      "zram_devices": ["/sys/block/zram0"],
      "last_mitigation": {
        "tier": "tier1_compact",
        "timestamp": "2026-08-28T10:00:00Z"
      }
    }
  }
}
```

---

## 8. Verification & Test Plan (TDD)

1. **PSI Parser Tests (`tests/memory/test_psi_parser.py`)**:
   - `test_parse_psi_memory_file`: Mock sample `/proc/pressure/memory` output and verify `some` & `full` reading values.
   - `test_parse_psi_cpu_file`: Verify single-line `some` parsing.
   - `test_parse_psi_missing_file`: Verify graceful return when `/proc/pressure` is absent.
2. **Mitigation Engine & Cooldown Tests (`tests/memory/test_psi_mitigation.py`)**:
   - `test_evaluate_tier1_trigger`: Assert zRAM compaction triggered on mild pressure.
   - `test_evaluate_tier2_trigger`: Assert MGLRU kick triggered on moderate pressure.
   - `test_evaluate_tier3_trigger`: Assert drop caches and log entry on critical stall.
   - `test_cooldown_suppression`: Assert subsequent high pressure readings within 20 seconds are debounced.
3. **CLI & Telemetry Tests (`tests/test_cli_psi.py` & `tests/test_tune_memory.py`)**:
   - Verify `osm psi status` and `osm psi compact` routing.
   - Verify `collect_tune_telemetry()` includes `subsystems.psi`.

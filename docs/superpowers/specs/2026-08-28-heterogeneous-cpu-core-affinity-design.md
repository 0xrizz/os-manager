# Heterogeneous CPU Core Affinity Router & Topology Partitioning Design Specification

- **Document ID**: `SPEC-2026-08-28-CPU-AFFINITY-01`
- **Author**: os-manager Architecture & Performance Team
- **Date**: 2026-08-28
- **Status**: Approved for Implementation
- **Target Kernel**: Linux Kernel 6.6+ / 6.12 LTS on Debian 13 (Trixie), WSL2 & Native Linux (Intel Hybrid Alder/Raptor/Arrow Lake, AMD Zen4/Zen4c, ARM big.LITTLE, Homogeneous x86_64)

---

## 1. Executive Summary & Problem Statement

Modern workstation processors increasingly feature heterogeneous architectures combining high-performance Performance Cores (P-Cores) with energy-efficient Efficiency Cores (E-Cores). While Linux kernel scheduler developments (such as ITMT/Energy-Aware Scheduling and EEVDF) handle general load balancing, high-intensity developer workloads suffer from specific scheduling pathologies:
1. **Compilation & Inference Latency Jitter**: Bursty parallel builds (`cargo build`, `gcc`, `pytest`) or local LLM inference engines (`llama.cpp`, `vLLM`) can be descheduled onto E-cores or throttled when background daemons compete on P-cores.
2. **Background Process Core Contention**: Resource-heavy background daemons (indexing, language servers, metric agents, sync services) frequently wake up on P-cores, consuming cache hierarchy and kicking interactive editor/shell threads out of L1/L2 caches.
3. **Lack of Dynamic User-Space Affinity Control**: Developers lack an integrated, zero-friction CLI interface to steer specific commands or active PIDs to designated core clusters without manual hex bitmask math.

This specification introduces the **Heterogeneous CPU Core Affinity Router** (`os_manager.cpu`) to `os-manager`. It provides multi-tier topology discovery, declarative systemd cgroups v2 slice isolation, and on-demand process affinity execution via `osm cpu` and `osm tune cpu`.

---

## 2. Technical Architecture & Component Hierarchy

The subsystem is partitioned into modular, single-responsibility components:

```text
                               ┌──────────────────────────────────────────────┐
                               │               CLI Dispatcher                 │
                               │   - osm cpu [topology|audit|run|pin]         │
                               │   - osm tune cpu [--apply|--dry-run|--revert]│
                               └──────────────────────┬───────────────────────┘
                                                      │
                               ┌──────────────────────▼───────────────────────┐
                               │          os_manager.cpu.topology             │
                               │   - CpuCore & CpuTopology Dataclasses        │
                               │   - Multi-Tier Sysfs Discovery Engine        │
                               │   - CPU Set Range Formatter / Mask Helper    │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
┌─────────────────────────────────────────────┐               ┌─────────────────────────────────────────────┐
│          os_manager.cpu.affinity            │               │         os_manager.commands.tune            │
│   - execute_with_affinity(cmd, target)      │               │   - generate_session_cpuset_config()        │
│   - pin_pid_affinity(pid, target)           │               │   - generate_background_cpuset_config()     │
│   - audit_slice_cpusets()                   │               │   - apply_cpu_tuning() & snapshot rollback  │
└─────────────────────────────────────────────┘               └─────────────────────────────────────────────┘
```

---

## 3. Topology Discovery Engine (`os_manager.cpu.topology`)

### 3.1 Multi-Tier Discovery Algorithm

The topology discovery engine inspects sysfs nodes under `/sys/devices/system/cpu/` using a prioritized multi-tier classification:

```text
   ┌─────────────────────────────────────────────────────────────┐
   │ Scan /sys/devices/system/cpu/cpu[0-9]*                      │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
                [Tier 1: topology/core_type exists?]
                     ├── Yes ──> Intel Hybrid (intel_core = P, intel_atom = E)
                     └── No
                          │
                          ▼
                [Tier 2: cpu_capacity exists?]
                     ├── Yes ──> Capacity Clustering (Max Capacity = P, Lower = E)
                     └── No
                          │
                          ▼
                [Tier 3: cpufreq/cpuinfo_max_freq exists?]
                     ├── Yes ──> Max Frequency Clustering (Higher Freq = P, Lower = E)
                     └── No
                          │
                          ▼
                [Tier 4: Homogeneous / WSL2 Fallback]
                     └───────> All cores equal; Partition lower half (0..N/2-1) as P-equiv,
                               upper half (N/2..N-1) as E-equiv.
```

### 3.2 Data Models

```python
from dataclasses import dataclass, field
from typing import Literal

CoreType = Literal["performance", "efficiency", "standard"]
DetectionMethod = Literal["core_type", "cpu_capacity", "max_freq", "homogeneous"]

@dataclass
class CpuCore:
    cpu_id: int
    core_type: CoreType
    online: bool = True
    max_freq_khz: int | None = None
    capacity: int | None = None
    physical_package_id: int | None = None
    core_id: int | None = None

@dataclass
class CpuTopology:
    total_cpus: int
    is_heterogeneous: bool
    detection_method: DetectionMethod
    cores: list[CpuCore] = field(default_factory=list)
    p_cores: list[int] = field(default_factory=list)
    e_cores: list[int] = field(default_factory=list)
    p_core_mask: str = ""
    e_core_mask: str = ""
    all_cores_mask: str = ""
```

### 3.3 Core Range Formatter
A utility function `format_cpu_range(core_ids: list[int]) -> str` converts integer core lists (e.g. `[0, 1, 2, 3, 8, 9, 10, 11]`) into standard Linux cpuset strings (e.g. `"0-3,8-11"`).

---

## 4. Declarative Cgroups v2 & Systemd Slice Configuration

### 4.1 Drop-In Paths & Directives
Systemd User Slices enforce core isolation at the cgroup level via `AllowedCPUs=` drop-ins:

1. **Session Slice (`/etc/systemd/user/session.slice.d/10-cpuset.conf`)**:
   - Allocated to **All Cores** or **P-Cores** to guarantee low latency for interactive shells, IDEs, and active dev processes.
   ```ini
   [Slice]
   AllowedCPUs=0-3,8-11
   ```

2. **Background Slice (`/etc/systemd/user/background.slice.d/10-cpuset.conf`)**:
   - Restricted strictly to **E-Cores** (or secondary core partition in homogeneous systems) to prevent background jobs from polluting P-core caches.
   ```ini
   [Slice]
   AllowedCPUs=4-7
   ```

### 4.2 Snapshot & Rollback Guarantee
In accordance with `os-manager` Zero-Trust invariants:
- Any modification to `/etc/systemd/user/*.slice.d/10-cpuset.conf` creates an atomic snapshot recorded in `/var/backups/osm/snapshots/` (or `~/.local/share/osm/snapshots/`).
- `osm tune cpu --revert` or `osm tune revert` cleanly restores prior slice configurations and triggers `systemctl --user daemon-reload`.

---

## 5. Imperative Process Affinity & Execution (`os_manager.cpu.affinity`)

### 5.1 On-Demand Command Execution (`osm cpu run`)
Executes commands pinned to target core sets:
- **P-Core Target**: Invokes command bound to `p_core_mask` (or all cores if system is homogeneous and no restriction is requested).
- **E-Core Target**: Invokes command bound to `e_core_mask`.
- **Implementation**: Uses `os.sched_setaffinity` before subprocess execution or wraps with `taskset -c <mask_str>`.

### 5.2 Live Process Pinning (`osm cpu pin`)
Adjusts affinity mask of an existing running process:
- `pin_pid_affinity(pid: int, target: Literal["p-core", "e-core", "all"]) -> bool`
- Interacts with `os.sched_setaffinity(pid, target_cores)` or `taskset -cp <mask_str> <pid>`.

---

## 6. CLI Routing & Interfaces

### 6.1 `osm cpu` Subcommands
- `osm cpu topology [--json]`: Displays formatted table or JSON of detected CPU cores, frequencies, capacities, and P/E classifications.
- `osm cpu audit [--json]`: Audits active systemd slice cpuset masks and current affinity defaults.
- `osm cpu run (--p-core | --e-core) <command...>`: Runs target command pinned to P-cores or E-cores.
- `osm cpu pin --pid <PID> (--p-core | --e-core | --all)`: Pinned a running process by PID to target core cluster.

### 6.2 `osm tune cpu` Subcommands
- `osm tune cpu`: Audits declarative systemd cpuset slice configuration.
- `osm tune cpu --apply [--dry-run]`: Generates and writes `/etc/systemd/user/{session,background}.slice.d/10-cpuset.conf` and reloads systemd.
- `osm tune cpu --revert`: Reverts slice cpuset drop-ins to prior snapshot.
- `osm tune cpu --json`: Emits machine-readable JSON status of CPU tuning.

---

## 7. Master Telemetry Integration

`collect_tune_telemetry()` in `os_manager/commands/tune.py` aggregates CPU affinity metrics into the `subsystems.cpu` object:
```json
{
  "subsystems": {
    "cpu": {
      "total_cpus": 8,
      "is_heterogeneous": false,
      "detection_method": "homogeneous",
      "p_cores": [0, 1, 2, 3],
      "e_cores": [4, 5, 6, 7],
      "p_core_mask": "0-3",
      "e_core_mask": "4-7",
      "session_cpuset_configured": true,
      "background_cpuset_configured": true
    }
  }
}
```

---

## 8. Verification & Test Plan (TDD)

1. **Topology Discovery Tests (`tests/cpu/test_topology.py`)**:
   - `test_format_cpu_range`: Test contiguous ranges (`0-3`), disjoint ranges (`0-1,4-5`), and single cores (`0,2,4`).
   - `test_detect_cpu_topology_tier1_intel_hybrid`: Mock `/sys/.../topology/core_type` returning `intel_core` vs `intel_atom`.
   - `test_detect_cpu_topology_tier2_cpu_capacity`: Mock `/sys/.../cpu_capacity` returning `1024` vs `512`.
   - `test_detect_cpu_topology_tier3_max_freq`: Mock `/sys/.../cpufreq/cpuinfo_max_freq` with high vs low clock speeds.
   - `test_detect_cpu_topology_tier4_homogeneous_fallback`: Mock uniform cores and verify logical split.

2. **Affinity Execution & Slice Generator Tests (`tests/cpu/test_affinity.py`)**:
   - `test_generate_session_cpuset_config`: Assert `AllowedCPUs=` directive generation.
   - `test_generate_background_cpuset_config`: Assert `AllowedCPUs=` directive generation.
   - `test_execute_with_affinity`: Verify subprocess execution with correct CPU mask.
   - `test_pin_pid_affinity`: Verify `os.sched_setaffinity` or `taskset` invocation on PID.

3. **CLI Integration Tests (`tests/test_cli_cpu.py` & `tests/test_tune_system.py`)**:
   - Verify `osm cpu topology`, `osm cpu audit`, `osm cpu run`, and `osm cpu pin` routing and status codes.
   - Verify `osm tune cpu` audit and `--apply --dry-run`.
   - Verify master telemetry contains `subsystems.cpu`.

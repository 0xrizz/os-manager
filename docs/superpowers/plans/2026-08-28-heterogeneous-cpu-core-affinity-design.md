# Heterogeneous CPU Core Affinity Router & Topology Partitioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Heterogeneous CPU Core Affinity Router (`os_manager.cpu`) providing multi-tier sysfs topology discovery, declarative systemd cgroups v2 slice isolation (`session.slice` and `background.slice` `AllowedCPUs=`), on-demand process affinity execution/pinning, CLI commands (`osm cpu` and `osm tune cpu`), and master telemetry integration.

**Architecture:** Create `os_manager/cpu/` with `topology.py` (multi-tier sysfs parser and range formatter) and `affinity.py` (process execution and PID pinning). Integrate declarative slice generation, audit, and rollback into `os_manager/commands/tune.py`. Expose CLI dispatchers in `os_manager/commands/cpu.py`, register `osm cpu` in `os_manager/cli.py`, and wire telemetry in `collect_tune_telemetry()`.

**Tech Stack:** Python 3.11+ standard library (`dataclasses`, `typing`, `pathlib`, `subprocess`, `os`, `argparse`, `json`), Linux sysfs (`/sys/devices/system/cpu/`), Linux cgroups v2 / systemd user slices (`AllowedCPUs=`).

**Spec:** `docs/superpowers/specs/2026-08-28-heterogeneous-cpu-core-affinity-design.md`

## Global Constraints

- Configuration drop-in paths:
  - `/etc/systemd/user/session.slice.d/10-cpuset.conf`
  - `/etc/systemd/user/background.slice.d/10-cpuset.conf`
- Sysfs inspection root: `/sys/devices/system/cpu/` (must support custom sysfs root for deterministic unit testing)
- Discovery algorithm hierarchy:
  - Tier 1: `topology/core_type` (`intel_core` vs `intel_atom`)
  - Tier 2: `cpu_capacity` (Max capacity = P-core, Lower capacity = E-core)
  - Tier 3: `cpufreq/cpuinfo_max_freq` (Higher max frequency = P-core, Lower = E-core)
  - Tier 4: Homogeneous fallback (split lower half `0..N/2-1` as P-equivalent, upper half `N/2..N-1` as E-equivalent)
- Zero-Trust safety matrix: Non-destructive systemd drop-in writes with atomic snapshot tracking via `create_system_snapshot` and rollback via `revert_system_snapshot`
- Non-interactive privileged execution: Use passwordless or `sudo -S` via `scripts/sudo_exec.sh`

---

### Task 1: CPU Topology Discovery & Core Range Formatter

**Files:**
- Create: `os_manager/cpu/__init__.py`
- Create: `os_manager/cpu/topology.py`
- Test: `tests/cpu/test_topology.py`

**Interfaces:**
- Produces:
  - `CoreType = Literal["performance", "efficiency", "standard"]`
  - `DetectionMethod = Literal["core_type", "cpu_capacity", "max_freq", "homogeneous"]`
  - `CpuCore(cpu_id: int, core_type: CoreType, online: bool = True, max_freq_khz: int | None = None, capacity: int | None = None, physical_package_id: int | None = None, core_id: int | None = None)`
  - `CpuTopology(total_cpus: int, is_heterogeneous: bool, detection_method: DetectionMethod, cores: list[CpuCore], p_cores: list[int], e_cores: list[int], p_core_mask: str, e_core_mask: str, all_cores_mask: str)`
  - `format_cpu_range(core_ids: list[int]) -> str`
  - `detect_cpu_topology(sysfs_root: str = "/sys/devices/system/cpu") -> CpuTopology`

- [ ] **Step 1: Write unit tests for topology discovery & range formatter**

Create `tests/cpu/test_topology.py`:

```python
"""tests/cpu/test_topology.py - Unit tests for CPU topology detection and cpuset range formatting."""

import os
import tempfile
import unittest
from pathlib import Path

from os_manager.cpu.topology import (
    CpuCore,
    CpuTopology,
    detect_cpu_topology,
    format_cpu_range,
)


class TestCpuTopology(unittest.TestCase):
    """Test suite for CPU topology discovery across Intel Hybrid, ARM/AMD capacity, frequency, and fallback."""

    def test_format_cpu_range_contiguous_and_disjoint(self):
        """Test formatting integer core lists to cpuset range strings."""
        self.assertEqual(format_cpu_range([]), "")
        self.assertEqual(format_cpu_range([0]), "0")
        self.assertEqual(format_cpu_range([0, 1, 2, 3]), "0-3")
        self.assertEqual(format_cpu_range([0, 1, 2, 3, 8, 9, 10, 11]), "0-3,8-11")
        self.assertEqual(format_cpu_range([0, 2, 4, 6]), "0,2,4,6")
        self.assertEqual(format_cpu_range([3, 2, 1, 0]), "0-3")

    def test_detect_cpu_topology_tier1_intel_hybrid(self):
        """Test Tier 1 detection via topology/core_type (Alder/Raptor/Arrow Lake)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create 4 P-cores (core_type: intel_core / 0x40) and 4 E-cores (core_type: intel_atom / 0x20)
            for i in range(4):
                cpu_dir = root / f"cpu{i}" / "topology"
                cpu_dir.mkdir(parents=True)
                (cpu_dir / "core_type").write_text("intel_core\n", encoding="utf-8")
            for i in range(4, 8):
                cpu_dir = root / f"cpu{i}" / "topology"
                cpu_dir.mkdir(parents=True)
                (cpu_dir / "core_type").write_text("intel_atom\n", encoding="utf-8")

            topo = detect_cpu_topology(sysfs_root=str(root))
            self.assertEqual(topo.total_cpus, 8)
            self.assertTrue(topo.is_heterogeneous)
            self.assertEqual(topo.detection_method, "core_type")
            self.assertEqual(topo.p_cores, [0, 1, 2, 3])
            self.assertEqual(topo.e_cores, [4, 5, 6, 7])
            self.assertEqual(topo.p_core_mask, "0-3")
            self.assertEqual(topo.e_core_mask, "4-7")
            self.assertEqual(topo.all_cores_mask, "0-7")

    def test_detect_cpu_topology_tier2_cpu_capacity(self):
        """Test Tier 2 detection via cpu_capacity (ARM big.LITTLE / DynamIQ)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # 2 P-cores (capacity 1024), 4 E-cores (capacity 446)
            for i in range(2):
                cpu_dir = root / f"cpu{i}"
                cpu_dir.mkdir(parents=True)
                (cpu_dir / "cpu_capacity").write_text("1024\n", encoding="utf-8")
            for i in range(2, 6):
                cpu_dir = root / f"cpu{i}"
                cpu_dir.mkdir(parents=True)
                (cpu_dir / "cpu_capacity").write_text("446\n", encoding="utf-8")

            topo = detect_cpu_topology(sysfs_root=str(root))
            self.assertEqual(topo.total_cpus, 6)
            self.assertTrue(topo.is_heterogeneous)
            self.assertEqual(topo.detection_method, "cpu_capacity")
            self.assertEqual(topo.p_cores, [0, 1])
            self.assertEqual(topo.e_cores, [2, 3, 4, 5])
            self.assertEqual(topo.p_core_mask, "0-1")
            self.assertEqual(topo.e_core_mask, "2-5")

    def test_detect_cpu_topology_tier3_max_freq(self):
        """Test Tier 3 detection via cpufreq/cpuinfo_max_freq."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # 4 High-freq cores (4800000 kHz), 4 Low-freq cores (3200000 kHz)
            for i in range(4):
                freq_dir = root / f"cpu{i}" / "cpufreq"
                freq_dir.mkdir(parents=True)
                (freq_dir / "cpuinfo_max_freq").write_text("4800000\n", encoding="utf-8")
            for i in range(4, 8):
                freq_dir = root / f"cpu{i}" / "cpufreq"
                freq_dir.mkdir(parents=True)
                (freq_dir / "cpuinfo_max_freq").write_text("3200000\n", encoding="utf-8")

            topo = detect_cpu_topology(sysfs_root=str(root))
            self.assertEqual(topo.total_cpus, 8)
            self.assertTrue(topo.is_heterogeneous)
            self.assertEqual(topo.detection_method, "max_freq")
            self.assertEqual(topo.p_cores, [0, 1, 2, 3])
            self.assertEqual(topo.e_cores, [4, 5, 6, 7])

    def test_detect_cpu_topology_tier4_homogeneous_fallback(self):
        """Test Tier 4 fallback for homogeneous systems (or WSL2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # 8 Identical cores with same freq
            for i in range(8):
                freq_dir = root / f"cpu{i}" / "cpufreq"
                freq_dir.mkdir(parents=True)
                (freq_dir / "cpuinfo_max_freq").write_text("3500000\n", encoding="utf-8")

            topo = detect_cpu_topology(sysfs_root=str(root))
            self.assertEqual(topo.total_cpus, 8)
            self.assertFalse(topo.is_heterogeneous)
            self.assertEqual(topo.detection_method, "homogeneous")
            self.assertEqual(topo.p_cores, [0, 1, 2, 3])
            self.assertEqual(topo.e_cores, [4, 5, 6, 7])
            self.assertEqual(topo.p_core_mask, "0-3")
            self.assertEqual(topo.e_core_mask, "4-7")
            self.assertEqual(topo.all_cores_mask, "0-7")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/cpu/test_topology.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'os_manager.cpu'`

- [ ] **Step 3: Implement `os_manager/cpu/__init__.py` and `os_manager/cpu/topology.py`**

Create `os_manager/cpu/__init__.py`:
```python
"""os_manager.cpu - Heterogeneous CPU topology discovery, slice isolation, and affinity routing."""

from .topology import (
    CpuCore,
    CpuTopology,
    detect_cpu_topology,
    format_cpu_range,
)

__all__ = [
    "CpuCore",
    "CpuTopology",
    "detect_cpu_topology",
    "format_cpu_range",
]
```

Create `os_manager/cpu/topology.py`:
```python
"""os_manager/cpu/topology.py - Multi-tier CPU topology discovery engine and core mask formatting."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

CoreType = Literal["performance", "efficiency", "standard"]
DetectionMethod = Literal["core_type", "cpu_capacity", "max_freq", "homogeneous"]


@dataclass
class CpuCore:
    """Detailed hardware metadata for an individual logical CPU core."""
    cpu_id: int
    core_type: CoreType = "standard"
    online: bool = True
    max_freq_khz: int | None = None
    capacity: int | None = None
    physical_package_id: int | None = None
    core_id: int | None = None


@dataclass
class CpuTopology:
    """Aggregated processor topology and heterogeneous core affinity partition."""
    total_cpus: int
    is_heterogeneous: bool
    detection_method: DetectionMethod
    cores: list[CpuCore] = field(default_factory=list)
    p_cores: list[int] = field(default_factory=list)
    e_cores: list[int] = field(default_factory=list)
    p_core_mask: str = ""
    e_core_mask: str = ""
    all_cores_mask: str = ""


def format_cpu_range(core_ids: list[int]) -> str:
    """Convert a list of CPU IDs into standard Linux cpuset format (e.g. [0,1,2,3,8,9] -> '0-3,8-9')."""
    if not core_ids:
        return ""
    sorted_ids = sorted(set(core_ids))
    ranges: list[str] = []
    start = sorted_ids[0]
    end = start

    for cid in sorted_ids[1:]:
        if cid == end + 1:
            end = cid
        else:
            if start == end:
                ranges.append(f"{start}")
            else:
                ranges.append(f"{start}-{end}")
            start = end = cid

    if start == end:
        ranges.append(f"{start}")
    else:
        ranges.append(f"{start}-{end}")

    return ",".join(ranges)


def detect_cpu_topology(sysfs_root: str = "/sys/devices/system/cpu") -> CpuTopology:
    """Discover CPU topology inspecting sysfs with multi-tier heterogeneous fallback."""
    root = Path(sysfs_root)
    cpu_dirs: list[tuple[int, Path]] = []

    if root.exists():
        for p in root.iterdir():
            if p.is_dir() and re.match(r"^cpu[0-9]+$", p.name):
                cid = int(p.name.replace("cpu", ""))
                cpu_dirs.append((cid, p))

    cpu_dirs.sort(key=lambda x: x[0])
    total_cpus = len(cpu_dirs)
    if total_cpus == 0:
        # Fallback to os.cpu_count() if sysfs is unavailable
        total_cpus = os.cpu_count() or 1
        p_list = list(range(0, max(1, total_cpus // 2)))
        e_list = list(range(max(1, total_cpus // 2), total_cpus))
        if not e_list:
            e_list = list(p_list)
        return CpuTopology(
            total_cpus=total_cpus,
            is_heterogeneous=False,
            detection_method="homogeneous",
            cores=[CpuCore(cpu_id=i) for i in range(total_cpus)],
            p_cores=p_list,
            e_cores=e_list,
            p_core_mask=format_cpu_range(p_list),
            e_core_mask=format_cpu_range(e_list),
            all_cores_mask=format_cpu_range(list(range(total_cpus))),
        )

    cores: list[CpuCore] = []
    has_tier1 = False
    has_tier2 = False
    has_tier3 = False

    for cid, cpath in cpu_dirs:
        core = CpuCore(cpu_id=cid)
        # Check online status
        online_file = cpath / "online"
        if online_file.is_file():
            try:
                core.online = online_file.read_text(encoding="utf-8").strip() == "1"
            except Exception:
                core.online = True
        else:
            core.online = True

        # Tier 1: core_type (Intel Hybrid)
        core_type_file = cpath / "topology" / "core_type"
        if core_type_file.is_file():
            try:
                val = core_type_file.read_text(encoding="utf-8").strip().lower()
                if "core" in val or val == "0x40":
                    core.core_type = "performance"
                    has_tier1 = True
                elif "atom" in val or val == "0x20":
                    core.core_type = "efficiency"
                    has_tier1 = True
            except Exception:
                pass

        # Tier 2: cpu_capacity (ARM big.LITTLE / DynamIQ)
        cap_file = cpath / "cpu_capacity"
        if cap_file.is_file():
            try:
                core.capacity = int(cap_file.read_text(encoding="utf-8").strip())
                has_tier2 = True
            except Exception:
                pass

        # Tier 3: max_freq (cpufreq)
        freq_file = cpath / "cpufreq" / "cpuinfo_max_freq"
        if freq_file.is_file():
            try:
                core.max_freq_khz = int(freq_file.read_text(encoding="utf-8").strip())
                has_tier3 = True
            except Exception:
                pass

        # Package & Core ID
        pkg_file = cpath / "topology" / "physical_package_id"
        if pkg_file.is_file():
            try:
                core.physical_package_id = int(pkg_file.read_text(encoding="utf-8").strip())
            except Exception:
                pass
        cid_file = cpath / "topology" / "core_id"
        if cid_file.is_file():
            try:
                core.core_id = int(cid_file.read_text(encoding="utf-8").strip())
            except Exception:
                pass

        cores.append(core)

    p_cores: list[int] = []
    e_cores: list[int] = []
    detection_method: DetectionMethod = "homogeneous"
    is_hetero = False

    # Evaluate Tier 1
    if has_tier1:
        p_cores = [c.cpu_id for c in cores if c.core_type == "performance"]
        e_cores = [c.cpu_id for c in cores if c.core_type == "efficiency"]
        if p_cores and e_cores:
            is_hetero = True
            detection_method = "core_type"

    # Evaluate Tier 2 if not settled
    if not is_hetero and has_tier2:
        caps = [c.capacity for c in cores if c.capacity is not None]
        if caps and len(set(caps)) > 1:
            max_cap = max(caps)
            p_cores = [c.cpu_id for c in cores if c.capacity == max_cap]
            e_cores = [c.cpu_id for c in cores if c.capacity is not None and c.capacity < max_cap]
            for c in cores:
                c.core_type = "performance" if c.cpu_id in p_cores else "efficiency"
            is_hetero = True
            detection_method = "cpu_capacity"

    # Evaluate Tier 3 if not settled
    if not is_hetero and has_tier3:
        freqs = [c.max_freq_khz for c in cores if c.max_freq_khz is not None]
        if freqs and len(set(freqs)) > 1:
            max_freq = max(freqs)
            p_cores = [c.cpu_id for c in cores if c.max_freq_khz == max_freq]
            e_cores = [c.cpu_id for c in cores if c.max_freq_khz is not None and c.max_freq_khz < max_freq]
            for c in cores:
                c.core_type = "performance" if c.cpu_id in p_cores else "efficiency"
            is_hetero = True
            detection_method = "max_freq"

    # Tier 4: Homogeneous Fallback
    if not is_hetero:
        detection_method = "homogeneous"
        half = max(1, total_cpus // 2)
        p_cores = [c.cpu_id for c in cores[:half]]
        e_cores = [c.cpu_id for c in cores[half:]]
        if not e_cores:
            e_cores = list(p_cores)
        for c in cores:
            c.core_type = "performance" if c.cpu_id in p_cores else "efficiency"

    all_ids = [c.cpu_id for c in cores]
    return CpuTopology(
        total_cpus=total_cpus,
        is_heterogeneous=is_hetero,
        detection_method=detection_method,
        cores=cores,
        p_cores=p_cores,
        e_cores=e_cores,
        p_core_mask=format_cpu_range(p_cores),
        e_core_mask=format_cpu_range(e_cores),
        all_cores_mask=format_cpu_range(all_ids),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/cpu/test_topology.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add os_manager/cpu/__init__.py os_manager/cpu/topology.py tests/cpu/test_topology.py
git commit -m "feat(cpu): implement multi-tier cpu topology discovery and mask formatter"
```

---

### Task 2: Process Affinity Execution & Live PID Pinning

**Files:**
- Create: `os_manager/cpu/affinity.py`
- Modify: `os_manager/cpu/__init__.py`
- Test: `tests/cpu/test_affinity.py`

**Interfaces:**
- Consumes: `os_manager.cpu.topology: detect_cpu_topology, CpuTopology`
- Produces:
  - `execute_with_affinity(command: list[str], target: Literal["p-core", "e-core", "all"] = "p-core", topology: CpuTopology | None = None) -> int`
  - `pin_pid_affinity(pid: int, target: Literal["p-core", "e-core", "all"] = "p-core", topology: CpuTopology | None = None) -> dict[str, Any]`
  - `audit_process_affinity(pid: int | None = None) -> dict[str, Any]`

- [ ] **Step 1: Write unit tests for affinity execution and pinning**

Create `tests/cpu/test_affinity.py`:

```python
"""tests/cpu/test_affinity.py - Unit tests for process affinity execution and PID pinning."""

import os
import unittest
from unittest.mock import MagicMock, patch

from os_manager.cpu.affinity import (
    audit_process_affinity,
    execute_with_affinity,
    pin_pid_affinity,
)
from os_manager.cpu.topology import CpuTopology


class TestCpuAffinity(unittest.TestCase):
    """Test suite for imperative CPU affinity execution and PID pinning."""

    def setUp(self):
        self.mock_topo = CpuTopology(
            total_cpus=8,
            is_heterogeneous=True,
            detection_method="core_type",
            p_cores=[0, 1, 2, 3],
            e_cores=[4, 5, 6, 7],
            p_core_mask="0-3",
            e_core_mask="4-7",
            all_cores_mask="0-7",
        )

    def test_execute_with_affinity_p_core(self):
        """Verify command execution bound to P-cores."""
        with patch("os_manager.cpu.affinity.detect_cpu_topology", return_value=self.mock_topo), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            code = execute_with_affinity(["cargo", "build", "--release"], target="p-core")
            self.assertEqual(code, 0)
            mock_run.assert_called_once()
            called_cmd = mock_run.call_args[0][0]
            self.assertEqual(called_cmd, ["taskset", "-c", "0-3", "cargo", "build", "--release"])

    def test_execute_with_affinity_e_core(self):
        """Verify command execution bound to E-cores."""
        with patch("os_manager.cpu.affinity.detect_cpu_topology", return_value=self.mock_topo), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            code = execute_with_affinity(["pytest"], target="e-core")
            self.assertEqual(code, 0)
            mock_run.assert_called_once()
            called_cmd = mock_run.call_args[0][0]
            self.assertEqual(called_cmd, ["taskset", "-c", "4-7", "pytest"])

    def test_pin_pid_affinity_success(self):
        """Verify pinning existing PID affinity."""
        with patch("os_manager.cpu.affinity.detect_cpu_topology", return_value=self.mock_topo), \
             patch("os.sched_setaffinity") as mock_sched:
            res = pin_pid_affinity(pid=1234, target="p-core")
            self.assertTrue(res["success"])
            self.assertEqual(res["pid"], 1234)
            self.assertEqual(res["target"], "p-core")
            self.assertEqual(res["mask"], "0-3")
            mock_sched.assert_called_once_with(1234, {0, 1, 2, 3})

    def test_pin_pid_affinity_taskset_fallback(self):
        """Verify fallback to taskset command if os.sched_setaffinity raises PermissionError / OSError."""
        with patch("os_manager.cpu.affinity.detect_cpu_topology", return_value=self.mock_topo), \
             patch("os.sched_setaffinity", side_effect=PermissionError("Permission denied")), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="pid 1234's current affinity mask: ff\n")
            res = pin_pid_affinity(pid=1234, target="e-core")
            self.assertTrue(res["success"])
            self.assertEqual(res["mask"], "4-7")
            mock_run.assert_called_once_with(["taskset", "-cp", "4-7", "1234"], capture_output=True, text=True, check=False)

    def test_audit_process_affinity(self):
        """Verify auditing current process or target PID affinity."""
        with patch("os.sched_getaffinity", return_value={0, 1, 2, 3}):
            res = audit_process_affinity(pid=0)
            self.assertEqual(res["affinity_cores"], [0, 1, 2, 3])
            self.assertEqual(res["affinity_mask"], "0-3")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/cpu/test_affinity.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'os_manager.cpu.affinity'`

- [ ] **Step 3: Implement `os_manager/cpu/affinity.py`**

Create `os_manager/cpu/affinity.py`:
```python
"""os_manager/cpu/affinity.py - Imperative CPU affinity execution and live process pinning."""

import os
import shutil
import subprocess
from typing import Any, Literal

from .topology import CpuTopology, detect_cpu_topology, format_cpu_range

AffinityTarget = Literal["p-core", "e-core", "all"]


def _resolve_target_cores(target: AffinityTarget, topology: CpuTopology) -> tuple[list[int], str]:
    """Resolve target name to core list and mask string."""
    if target == "p-core":
        cores = topology.p_cores
        mask = topology.p_core_mask
    elif target == "e-core":
        cores = topology.e_cores
        mask = topology.e_core_mask
    else:
        cores = [c.cpu_id for c in topology.cores]
        mask = topology.all_cores_mask
    return cores, mask


def execute_with_affinity(
    command: list[str],
    target: AffinityTarget = "p-core",
    topology: CpuTopology | None = None,
) -> int:
    """Execute a subprocess pinned to the target core partition."""
    if not command:
        return 0
    if topology is None:
        topology = detect_cpu_topology()

    _, mask = _resolve_target_cores(target, topology)
    if not mask:
        res = subprocess.run(command)
        return res.returncode

    taskset_bin = shutil.which("taskset")
    if taskset_bin:
        full_cmd = [taskset_bin, "-c", mask] + command
        res = subprocess.run(full_cmd)
        return res.returncode
    else:
        # Fallback to direct execution
        res = subprocess.run(command)
        return res.returncode


def pin_pid_affinity(
    pid: int,
    target: AffinityTarget = "p-core",
    topology: CpuTopology | None = None,
) -> dict[str, Any]:
    """Pin an existing running process PID to target CPU core partition."""
    if topology is None:
        topology = detect_cpu_topology()

    cores, mask = _resolve_target_cores(target, topology)
    if not cores or not mask:
        return {"success": False, "pid": pid, "error": "No cores resolved for target"}

    # Attempt native os.sched_setaffinity
    if hasattr(os, "sched_setaffinity"):
        try:
            os.sched_setaffinity(pid, set(cores))
            return {
                "success": True,
                "pid": pid,
                "target": target,
                "cores": cores,
                "mask": mask,
                "method": "sched_setaffinity",
            }
        except Exception as exc:
            pass

    # Fallback to taskset CLI
    taskset_bin = shutil.which("taskset")
    if taskset_bin:
        cmd = [taskset_bin, "-cp", mask, str(pid)]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return {
                "success": True,
                "pid": pid,
                "target": target,
                "cores": cores,
                "mask": mask,
                "method": "taskset",
                "output": res.stdout.strip(),
            }
        return {
            "success": False,
            "pid": pid,
            "error": res.stderr.strip() or f"taskset exited with {res.returncode}",
        }

    return {"success": False, "pid": pid, "error": "No affinity mechanism available"}


def audit_process_affinity(pid: int = 0) -> dict[str, Any]:
    """Audit CPU affinity mask for specified PID (0 = current process)."""
    target_pid = pid if pid > 0 else os.getpid()
    if hasattr(os, "sched_getaffinity"):
        try:
            cores = sorted(list(os.sched_getaffinity(target_pid)))
            return {
                "pid": target_pid,
                "affinity_cores": cores,
                "affinity_mask": format_cpu_range(cores),
                "available": True,
            }
        except Exception as exc:
            return {"pid": target_pid, "available": False, "error": str(exc)}

    return {"pid": target_pid, "available": False, "error": "sched_getaffinity unsupported"}
```

Update `os_manager/cpu/__init__.py`:
```python
"""os_manager.cpu - Heterogeneous CPU topology discovery, slice isolation, and affinity routing."""

from .affinity import (
    audit_process_affinity,
    execute_with_affinity,
    pin_pid_affinity,
)
from .topology import (
    CpuCore,
    CpuTopology,
    detect_cpu_topology,
    format_cpu_range,
)

__all__ = [
    "CpuCore",
    "CpuTopology",
    "detect_cpu_topology",
    "format_cpu_range",
    "execute_with_affinity",
    "pin_pid_affinity",
    "audit_process_affinity",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/cpu/test_affinity.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add os_manager/cpu/affinity.py os_manager/cpu/__init__.py tests/cpu/test_affinity.py
git commit -m "feat(cpu): add process affinity execution and live pid pinning engine"
```

---

### Task 3: Declarative Systemd Slices (`session.slice` & `background.slice`) Generator & Tuning Integration

**Files:**
- Modify: `os_manager/commands/tune.py:35-50, 850-920, 1850-1920, 2130-2200`
- Test: `tests/test_tune_cpu.py`

**Interfaces:**
- Consumes: `os_manager.cpu: detect_cpu_topology, CpuTopology`
- Produces:
  - `SESSION_CPUSET_SLICE_PATH = "/etc/systemd/user/session.slice.d/10-cpuset.conf"`
  - `BACKGROUND_CPUSET_SLICE_PATH = "/etc/systemd/user/background.slice.d/10-cpuset.conf"`
  - `generate_session_cpuset_config(allowed_cpus: str | None = None) -> str`
  - `generate_background_cpuset_config(allowed_cpus: str | None = None) -> str`
  - `audit_cpu_subsystem() -> dict[str, Any]`

- [ ] **Step 1: Write unit tests for declarative CPU slice generator and audit**

Create `tests/test_tune_cpu.py`:

```python
"""tests/test_tune_cpu.py - Unit tests for declarative CPU slice configuration and audit."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    BACKGROUND_CPUSET_SLICE_PATH,
    SESSION_CPUSET_SLICE_PATH,
    audit_cpu_subsystem,
    generate_background_cpuset_config,
    generate_session_cpuset_config,
)
from os_manager.cpu.topology import CpuTopology


class TestTuneCpuSubsystem(unittest.TestCase):
    """Test suite for declarative systemd cgroups v2 slice generation and audit."""

    def test_generate_session_cpuset_config_default(self):
        """Verify generation of session.slice cpuset drop-in."""
        cfg = generate_session_cpuset_config("0-3,8-11")
        self.assertIn("[Slice]", cfg)
        self.assertIn("AllowedCPUs=0-3,8-11", cfg)

    def test_generate_background_cpuset_config_default(self):
        """Verify generation of background.slice cpuset drop-in."""
        cfg = generate_background_cpuset_config("4-7")
        self.assertIn("[Slice]", cfg)
        self.assertIn("AllowedCPUs=4-7", cfg)

    def test_audit_cpu_subsystem_structure(self):
        """Verify audit_cpu_subsystem returns structured topology and drop-in status."""
        mock_topo = CpuTopology(
            total_cpus=8,
            is_heterogeneous=True,
            detection_method="core_type",
            p_cores=[0, 1, 2, 3],
            e_cores=[4, 5, 6, 7],
            p_core_mask="0-3",
            e_core_mask="4-7",
            all_cores_mask="0-7",
        )
        with patch("os_manager.commands.tune.detect_cpu_topology", return_value=mock_topo), \
             patch("pathlib.Path.is_file", return_value=True):
            audit = audit_cpu_subsystem()
            self.assertEqual(audit["total_cpus"], 8)
            self.assertTrue(audit["is_heterogeneous"])
            self.assertEqual(audit["detection_method"], "core_type")
            self.assertEqual(audit["p_core_mask"], "0-3")
            self.assertEqual(audit["e_core_mask"], "4-7")
            self.assertTrue(audit["session_cpuset_configured"])
            self.assertTrue(audit["background_cpuset_configured"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tune_cpu.py`
Expected: FAIL with `ImportError: cannot import name 'SESSION_CPUSET_SLICE_PATH' from 'os_manager.commands.tune'`

- [ ] **Step 3: Modify `os_manager/commands/tune.py` to add slice paths, generators, audit, and CLI/all dispatchers**

In `os_manager/commands/tune.py`:
1. Add imports:
```python
from os_manager.cpu import (
    CpuTopology,
    detect_cpu_topology,
)
```
2. Define drop-in constants:
```python
SESSION_CPUSET_SLICE_PATH = "/etc/systemd/user/session.slice.d/10-cpuset.conf"
BACKGROUND_CPUSET_SLICE_PATH = "/etc/systemd/user/background.slice.d/10-cpuset.conf"
```
3. Implement generator and audit functions:
```python
def generate_session_cpuset_config(allowed_cpus: str | None = None) -> str:
    """Generate systemd user session.slice AllowedCPUs drop-in."""
    if not allowed_cpus:
        topo = detect_cpu_topology()
        allowed_cpus = topo.p_core_mask or topo.all_cores_mask
    return (
        "# /etc/systemd/user/session.slice.d/10-cpuset.conf - Managed by os-manager\n"
        "[Slice]\n"
        f"AllowedCPUs={allowed_cpus}\n"
    )


def generate_background_cpuset_config(allowed_cpus: str | None = None) -> str:
    """Generate systemd user background.slice AllowedCPUs drop-in."""
    if not allowed_cpus:
        topo = detect_cpu_topology()
        allowed_cpus = topo.e_core_mask or topo.all_cores_mask
    return (
        "# /etc/systemd/user/background.slice.d/10-cpuset.conf - Managed by os-manager\n"
        "[Slice]\n"
        f"AllowedCPUs={allowed_cpus}\n"
    )


def audit_cpu_subsystem() -> dict[str, Any]:
    """Inspect CPU topology, P/E core partition, and systemd user slice configuration."""
    topo = detect_cpu_topology()
    return {
        "total_cpus": topo.total_cpus,
        "is_heterogeneous": topo.is_heterogeneous,
        "detection_method": topo.detection_method,
        "p_cores": topo.p_cores,
        "e_cores": topo.e_cores,
        "p_core_mask": topo.p_core_mask,
        "e_core_mask": topo.e_core_mask,
        "all_cores_mask": topo.all_cores_mask,
        "session_cpuset_configured": Path(SESSION_CPUSET_SLICE_PATH).is_file(),
        "background_cpuset_configured": Path(BACKGROUND_CPUSET_SLICE_PATH).is_file(),
    }
```
4. Wire `osm tune cpu` subaction handler in `run_tune`:
```python
    elif parsed_args.subaction == "cpu":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            topo = detect_cpu_topology()
            print(f"[PLAN] CPU affinity tuning simulation: session.slice (AllowedCPUs={topo.p_core_mask or topo.all_cores_mask}) and background.slice (AllowedCPUs={topo.e_core_mask or topo.all_cores_mask}).")
            return 0
        is_json = getattr(parsed_args, "json", False)
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            create_system_snapshot(
                caller="osm tune cpu --apply",
                target_files=[SESSION_CPUSET_SLICE_PATH, BACKGROUND_CPUSET_SLICE_PATH],
            )
            sess_cfg = generate_session_cpuset_config()
            bg_cfg = generate_background_cpuset_config()
            try:
                if os.geteuid() != 0:
                    subprocess.run(["sudo", "mkdir", "-p", "/etc/systemd/user/session.slice.d", "/etc/systemd/user/background.slice.d"], capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", SESSION_CPUSET_SLICE_PATH], input=sess_cfg, text=True, capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", BACKGROUND_CPUSET_SLICE_PATH], input=bg_cfg, text=True, capture_output=True, check=False)
                    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, check=False)
                else:
                    Path(SESSION_CPUSET_SLICE_PATH).parent.mkdir(parents=True, exist_ok=True)
                    Path(SESSION_CPUSET_SLICE_PATH).write_text(sess_cfg, encoding="utf-8")
                    Path(BACKGROUND_CPUSET_SLICE_PATH).parent.mkdir(parents=True, exist_ok=True)
                    Path(BACKGROUND_CPUSET_SLICE_PATH).write_text(bg_cfg, encoding="utf-8")
                    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, check=False)
                print("[PASS] CPU core affinity and systemd user slice cpuset drop-ins applied.")
                return 0
            except Exception as exc:
                print(f"[FAIL] Failed to apply CPU affinity tuning: {exc}")
                return 1
        else:
            cpu_info = audit_cpu_subsystem()
            if is_json:
                print(json.dumps(cpu_info, indent=2))
                return 0
            print("==================================================")
            print("       CPU Topology & Systemd Slices Audit        ")
            print("==================================================")
            print(f"1. Total Logical Cores: {cpu_info['total_cpus']}")
            print(f"2. Heterogeneous: {'Yes' if cpu_info['is_heterogeneous'] else 'No (Homogeneous)'} (via {cpu_info['detection_method']})")
            print(f"3. P-Cores Mask: {cpu_info['p_core_mask']}")
            print(f"4. E-Cores Mask: {cpu_info['e_core_mask']}")
            print(f"5. session.slice Cpuset: {'Configured' if cpu_info['session_cpuset_configured'] else 'Missing'}")
            print(f"6. background.slice Cpuset: {'Configured' if cpu_info['background_cpuset_configured'] else 'Missing'}")
            return 0
```
5. Update `collect_tune_telemetry()` to include `subsystems["cpu"] = audit_cpu_subsystem()`.
6. Update `osm tune all --apply` to include `SESSION_CPUSET_SLICE_PATH` and `BACKGROUND_CPUSET_SLICE_PATH` in snapshots, write drop-ins, and reload systemd.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_tune_cpu.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py tests/test_tune_cpu.py
git commit -m "feat(tune): integrate declarative cpu slice generation and audit into tune command"
```

---

### Task 4: CLI Subcommand `osm cpu` & Dispatcher Registration

**Files:**
- Create: `os_manager/commands/cpu.py`
- Modify: `os_manager/cli.py:10-25, 70-80, 110-130`
- Test: `tests/test_cli_cpu.py`

**Interfaces:**
- Consumes: `os_manager.cpu: detect_cpu_topology, execute_with_affinity, pin_pid_affinity, audit_process_affinity`
- Produces: `run_cpu(argv: list[str]) -> int`

- [ ] **Step 1: Write CLI routing tests for `osm cpu`**

Create `tests/test_cli_cpu.py`:

```python
"""tests/test_cli_cpu.py - Unit tests for osm cpu CLI subcommands."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from os_manager.cli import main
from os_manager.cpu.topology import CpuCore, CpuTopology


class TestCliCpu(unittest.TestCase):
    """Test suite for osm cpu CLI argument parsing and routing."""

    def setUp(self):
        self.mock_topo = CpuTopology(
            total_cpus=8,
            is_heterogeneous=True,
            detection_method="core_type",
            cores=[
                CpuCore(cpu_id=0, core_type="performance", max_freq_khz=4800000),
                CpuCore(cpu_id=4, core_type="efficiency", max_freq_khz=3200000),
            ],
            p_cores=[0, 1, 2, 3],
            e_cores=[4, 5, 6, 7],
            p_core_mask="0-3",
            e_core_mask="4-7",
            all_cores_mask="0-7",
        )

    def test_osm_cpu_topology_json(self):
        """Test 'osm cpu topology --json' output."""
        with patch("os_manager.commands.cpu.detect_cpu_topology", return_value=self.mock_topo), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["cpu", "topology", "--json"])
            self.assertEqual(code, 0)
            data = json.loads(mock_out.getvalue())
            self.assertEqual(data["total_cpus"], 8)
            self.assertTrue(data["is_heterogeneous"])
            self.assertEqual(data["p_core_mask"], "0-3")

    def test_osm_cpu_run_p_core(self):
        """Test 'osm cpu run --p-core echo hello'."""
        with patch("os_manager.commands.cpu.execute_with_affinity", return_value=0) as mock_exec:
            code = main(["cpu", "run", "--p-core", "echo", "hello"])
            self.assertEqual(code, 0)
            mock_exec.assert_called_once_with(["echo", "hello"], target="p-core")

    def test_osm_cpu_pin_pid(self):
        """Test 'osm cpu pin --pid 1234 --p-core'."""
        with patch("os_manager.commands.cpu.pin_pid_affinity", return_value={"success": True, "pid": 1234, "target": "p-core", "mask": "0-3"}) as mock_pin:
            code = main(["cpu", "pin", "--pid", "1234", "--p-core"])
            self.assertEqual(code, 0)
            mock_pin.assert_called_once_with(pid=1234, target="p-core")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli_cpu.py`
Expected: FAIL with `SystemExit` or unrecognized arguments

- [ ] **Step 3: Implement `os_manager/commands/cpu.py` and register in `os_manager/cli.py`**

Create `os_manager/commands/cpu.py`:
```python
"""os_manager/commands/cpu.py - Heterogeneous CPU Affinity Router CLI Command Module."""

import argparse
import json
import sys
from dataclasses import asdict
from typing import List

from ..cpu import (
    audit_process_affinity,
    detect_cpu_topology,
    execute_with_affinity,
    pin_pid_affinity,
)


def run_cpu(argv: List[str]) -> int:
    """Entrypoint dispatcher for 'osm cpu' commands."""
    parser = argparse.ArgumentParser(
        prog="osm cpu",
        description="Heterogeneous CPU Core Affinity Router & Topology Partitioning",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="CPU action")

    # topology
    topo_parser = subparsers.add_parser("topology", help="Display CPU core topology and P/E partition")
    topo_parser.add_argument("--json", action="store_true", help="Output topology as JSON")

    # audit
    audit_parser = subparsers.add_parser("audit", help="Audit current process or system affinity")
    audit_parser.add_argument("--pid", type=int, default=0, help="Target process PID (default: current)")
    audit_parser.add_argument("--json", action="store_true", help="Output audit as JSON")

    # run
    run_parser = subparsers.add_parser("run", help="Execute command pinned to core partition")
    run_group = run_parser.add_mutually_exclusive_group()
    run_group.add_argument("--p-core", action="store_true", help="Run on Performance Cores (default)")
    run_group.add_argument("--e-core", action="store_true", help="Run on Efficiency Cores")
    run_group.add_argument("--all", action="store_true", help="Run across all cores")
    run_parser.add_argument("command", nargs=argparse.REMAINDER, help="Target command and arguments")

    # pin
    pin_parser = subparsers.add_parser("pin", help="Pin existing PID to core partition")
    pin_parser.add_argument("--pid", type=int, required=True, help="Target process PID")
    pin_group = pin_parser.add_mutually_exclusive_group()
    pin_group.add_argument("--p-core", action="store_true", help="Pin to Performance Cores (default)")
    pin_group.add_argument("--e-core", action="store_true", help="Pin to Efficiency Cores")
    pin_group.add_argument("--all", action="store_true", help="Pin across all cores")
    pin_parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args, unknown = parser.parse_known_args(argv)

    if args.subcommand == "topology":
        topo = detect_cpu_topology()
        if args.json:
            print(json.dumps(asdict(topo), indent=2))
            return 0
        print("==================================================")
        print("         CPU Core Topology & Partition            ")
        print("==================================================")
        print(f"Total Cores: {topo.total_cpus}")
        print(f"Heterogeneous: {'Yes' if topo.is_heterogeneous else 'No'} (via {topo.detection_method})")
        print(f"P-Cores ({len(topo.p_cores)}): {topo.p_core_mask}")
        print(f"E-Cores ({len(topo.e_cores)}): {topo.e_core_mask}")
        print(f"All Cores: {topo.all_cores_mask}")
        print("\nCore Details:")
        for c in topo.cores:
            freq_str = f"{c.max_freq_khz // 1000} MHz" if c.max_freq_khz else "N/A"
            cap_str = f"Cap: {c.capacity}" if c.capacity else ""
            print(f"  CPU {c.cpu_id:2d}: {c.core_type:<12} (Max: {freq_str}) {cap_str}")
        return 0

    elif args.subcommand == "audit":
        audit = audit_process_affinity(pid=args.pid)
        if args.json:
            print(json.dumps(audit, indent=2))
            return 0
        print(f"PID {audit.get('pid')}: Affinity Mask: {audit.get('affinity_mask', 'N/A')} (Cores: {audit.get('affinity_cores', [])})")
        return 0

    elif args.subcommand == "run":
        target = "p-core"
        if args.e_core:
            target = "e-core"
        elif args.all:
            target = "all"
        cmd = args.command
        if unknown:
            cmd = unknown + cmd
        if not cmd:
            print("Error: No command specified to run.", file=sys.stderr)
            return 1
        return execute_with_affinity(cmd, target=target)

    elif args.subcommand == "pin":
        target = "p-core"
        if args.e_core:
            target = "e-core"
        elif args.all:
            target = "all"
        res = pin_pid_affinity(pid=args.pid, target=target)
        if args.json:
            print(json.dumps(res, indent=2))
            return 0 if res.get("success") else 1
        if res.get("success"):
            print(f"[PASS] Pinned PID {args.pid} to {target} (Mask: {res.get('mask')}).")
            return 0
        else:
            print(f"[FAIL] Failed to pin PID {args.pid}: {res.get('error')}", file=sys.stderr)
            return 1

    else:
        parser.print_help()
        return 0
```

Update `os_manager/cli.py` to register `subparsers.add_parser("cpu", ...)` and dispatch `run_cpu(argv[1:])`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli_cpu.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/cpu.py os_manager/cli.py tests/test_cli_cpu.py
git commit -m "feat(cli): add osm cpu command and router dispatcher"
```

---

### Task 5: Master Harness & Full Suite Verification

**Files:**
- Modify: `tests/test_harness.sh`
- Test: `tests/test_tune_system.py`

**Interfaces:**
- Verifies:
  - All unit tests across `tests/cpu/`, `tests/test_tune_cpu.py`, `tests/test_cli_cpu.py`, `tests/test_tune_system.py`
  - Integration with master test harness `./tests/test_harness.sh`

- [ ] **Step 1: Add CPU affinity assertions to `tests/test_tune_system.py` and `tests/test_harness.sh`**

In `tests/test_tune_system.py`:
- Assert `subsystems.cpu` exists in `collect_tune_telemetry()` output.
- Assert `osm tune cpu` outputs formatted audit and dry-run output.

In `tests/test_harness.sh`:
- Add test steps executing `osm cpu topology --json`, `osm cpu audit --json`, and `osm tune cpu --dry-run`.

- [ ] **Step 2: Run complete Pytest test suite**

Run: `.venv/bin/pytest tests/`
Expected: PASS (all tests pass)

- [ ] **Step 3: Run master harness test suite**

Run: `./tests/test_harness.sh`
Expected: All checks PASS (0 failures)

- [ ] **Step 4: Commit**

```bash
git add tests/test_tune_system.py tests/test_harness.sh
git commit -m "test(harness): integrate cpu affinity router and slice isolation into master harness"
```

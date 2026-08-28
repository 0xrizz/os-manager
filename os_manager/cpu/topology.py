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

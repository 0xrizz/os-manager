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

    if shutil.which("taskset"):
        full_cmd = ["taskset", "-c", mask] + command
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
        except Exception:
            pass

    # Fallback to taskset CLI
    if shutil.which("taskset"):
        cmd = ["taskset", "-cp", mask, str(pid)]
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

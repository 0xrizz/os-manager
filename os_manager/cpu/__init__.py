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

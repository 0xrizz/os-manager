"""sched_ext (Extensible Scheduler Class) dynamic eBPF scheduler controller and profile registry."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ScxProfileName = Literal["lavd", "bpfland", "rusty", "central", "simple"]
SYSTEMD_SCX_UNIT_PATH = "/etc/systemd/system/scx.service"


@dataclass
class ScxProfile:
    """Configuration definition for a sched_ext eBPF scheduler profile."""

    name: ScxProfileName
    binary_name: str
    description: str
    recommended_for: str
    default_args: list[str] = field(default_factory=list)


@dataclass
class ScxSupportStatus:
    """Telemetry and capability probe status for kernel sched_ext support."""

    kernel_supported: bool
    sysfs_present: bool
    active_scheduler: str | None
    installed_schedulers: list[str] = field(default_factory=list)
    service_active: bool = False
    service_enabled: bool = False
    details: str = ""


SCX_PROFILES: dict[ScxProfileName, ScxProfile] = {
    "lavd": ScxProfile(
        name="lavd",
        binary_name="scx_lavd",
        description="Latency-critical and virtual deadline scheduler.",
        recommended_for="Low-latency audio, gaming, and interactive desktop responsiveness.",
    ),
    "bpfland": ScxProfile(
        name="bpfland",
        binary_name="scx_bpfland",
        description="Heterogeneous core scheduler with P/E core balancing.",
        recommended_for="Intel Alder/Raptor Lake and AMD Zen4c hybrid architectures.",
    ),
    "rusty": ScxProfile(
        name="rusty",
        binary_name="scx_rusty",
        description="Multi-threaded cache-aware compilation and compute scheduler.",
        recommended_for="Heavy parallel builds (cargo build, gcc, clang, pytest) and batch tasks.",
    ),
    "central": ScxProfile(
        name="central",
        binary_name="scx_central",
        description="Centralized queue scheduler for high-core count workstation CPUs.",
        recommended_for="Multi-socket systems and high-core workstation/server topologies.",
    ),
    "simple": ScxProfile(
        name="simple",
        binary_name="scx_simple",
        description="Minimal reference scheduler for verification and validation.",
        recommended_for="Subsystem testing and baseline eBPF scheduling verification.",
    ),
}


def generate_scx_systemd_unit(binary_path: str, profile_args: list[str] | None = None) -> str:
    """Generate systemd service unit definition for running sched_ext scheduler as a system daemon."""
    args_str = f" {' '.join(profile_args)}" if profile_args else ""
    return f"""# /etc/systemd/system/scx.service - Managed by os-manager
[Unit]
Description=sched_ext eBPF Kernel Scheduler
Documentation=https://github.com/sched-ext/scx
After=network.target local-fs.target
ConditionPathExists=/sys/kernel/sched_ext

[Service]
Type=simple
ExecStart={binary_path}{args_str}
Restart=on-failure
RestartSec=2s
LimitMEMLOCK=infinity

[Install]
WantedBy=multi-user.target
"""

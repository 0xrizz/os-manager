"""os_manager.scheduler - Linux kernel CPU scheduling, EEVDF slicing, and sched_ext eBPF engine."""

from os_manager.scheduler.scx import (
    SCX_PROFILES,
    SYSTEMD_SCX_UNIT_PATH,
    ScxProfile,
    ScxProfileName,
    ScxSupportStatus,
    disable_scx_service,
    discover_installed_schedulers,
    enable_scx_service,
    generate_scx_systemd_unit,
    probe_sched_ext_support,
    start_scx_scheduler,
    stop_scx_scheduler,
)

__all__ = [
    "ScxProfile",
    "ScxProfileName",
    "ScxSupportStatus",
    "SCX_PROFILES",
    "SYSTEMD_SCX_UNIT_PATH",
    "generate_scx_systemd_unit",
    "discover_installed_schedulers",
    "probe_sched_ext_support",
    "start_scx_scheduler",
    "stop_scx_scheduler",
    "enable_scx_service",
    "disable_scx_service",
]

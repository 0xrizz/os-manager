"""Zero-trust zRAM manager conflict detection and autonomous remediation engine."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

CONFLICTING_ZRAM_SERVICES: list[str] = [
    "zramswap.service",       # zram-tools
    "zram-config.service",     # zram-config
    "zram.service",            # generic zram service
    "zram-init.service",       # zram-init
]

CANONICAL_ZRAM_GENERATOR_PKG = "systemd-zram-generator"
CANONICAL_ZRAM_CONF = "/etc/systemd/zram-generator.conf"
CANONICAL_ZRAM_DEVICE = "/dev/zram0"


@dataclass
class ConflictingServiceStatus:
    name: str
    installed: bool = False
    enabled: bool = False
    active: bool = False
    failed: bool = False
    masked: bool = False


@dataclass
class ZramAuditReport:
    canonical_installed: bool = False
    canonical_configured: bool = False
    zram_device_active: bool = False
    active_devices: list[dict[str, Any]] = field(default_factory=list)
    conflicts_detected: bool = False
    conflicting_services: list[ConflictingServiceStatus] = field(default_factory=list)
    status: str = "UNCONFIGURED"  # OPTIMAL, CONFLICT_DETECTED, DEGRADED, UNCONFIGURED
    summary_message: str = ""


def _query_service_status(service_name: str) -> ConflictingServiceStatus:
    """Query systemd state for a single service."""
    status = ConflictingServiceStatus(name=service_name)
    try:
        res_file = subprocess.run(
            ["systemctl", "list-unit-files", service_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if res_file.returncode == 0 and service_name in res_file.stdout:
            status.installed = True
            if "masked" in res_file.stdout:
                status.masked = True
            elif "enabled" in res_file.stdout:
                status.enabled = True

        res_active = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        out_active = res_active.stdout.strip()
        status.active = out_active == "active"
        if out_active == "failed":
            status.failed = True

        res_failed = subprocess.run(
            ["systemctl", "is-failed", service_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if res_failed.stdout.strip() == "failed":
            status.failed = True

    except Exception:
        pass
    return status


def audit_zram_system(
    proc_swaps_path: str = "/proc/swaps",
    conf_path: str = CANONICAL_ZRAM_CONF,
) -> ZramAuditReport:
    """Inspect zRAM devices, canonical generator status, and conflicting services."""
    report = ZramAuditReport()

    # 1. Inspect active swap devices in /proc/swaps
    swaps_node = Path(proc_swaps_path)
    if swaps_node.is_file():
        try:
            lines = swaps_node.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[1:]:
                parts = line.split()
                if not parts:
                    continue
                dev = parts[0]
                dev_type = parts[1] if len(parts) > 1 else ""
                size_kb = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                used_kb = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
                prio = int(parts[4]) if len(parts) > 4 and (parts[4].isdigit() or parts[4].startswith("-")) else 0

                entry = {
                    "device": dev,
                    "type": dev_type,
                    "size_kb": size_kb,
                    "used_kb": used_kb,
                    "priority": prio,
                }
                report.active_devices.append(entry)
                if "zram" in dev:
                    report.zram_device_active = True
        except Exception:
            pass

    # 2. Check canonical generator configuration and package
    cfg_node = Path(conf_path)
    if cfg_node.is_file():
        try:
            content = cfg_node.read_text(encoding="utf-8")
            if "[zram0]" in content:
                report.canonical_configured = True
        except Exception:
            pass

    if (
        shutil.which("systemd-zram-generator")
        or Path("/usr/lib/systemd/system-generators/systemd-zram-generator").is_file()
    ):
        report.canonical_installed = True

    # 3. Check conflicting services
    conflicts: list[ConflictingServiceStatus] = []
    for svc in CONFLICTING_ZRAM_SERVICES:
        svc_status = _query_service_status(svc)
        if svc_status.installed and not svc_status.masked:
            if svc_status.enabled or svc_status.active or svc_status.failed:
                conflicts.append(svc_status)
        elif svc_status.active or svc_status.failed:
            conflicts.append(svc_status)

    report.conflicting_services = conflicts
    report.conflicts_detected = len(conflicts) > 0

    # 4. Synthesize overall status
    if report.conflicts_detected:
        report.status = "CONFLICT_DETECTED"
        svc_names = ", ".join(c.name for c in report.conflicting_services)
        report.summary_message = f"Conflicting zRAM services detected: {svc_names}"
    elif report.zram_device_active and report.canonical_configured:
        report.status = "OPTIMAL"
        report.summary_message = "zRAM configured with systemd-zram-generator and active without conflicts."
    elif report.zram_device_active:
        report.status = "DEGRADED"
        report.summary_message = "zRAM device active but canonical configuration missing."
    else:
        report.status = "UNCONFIGURED"
        report.summary_message = "No active zRAM devices or generator found."

    return report

"""Hardware power, thermal, system, desktop, and terminal customization command module."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SYSFS_CONSERVATION_DEFAULT = "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"
SYSFS_PROFILE_DEFAULT = "/sys/firmware/acpi/platform_profile"
SYSFS_PROFILE_CHOICES_DEFAULT = "/sys/firmware/acpi/platform_profile_choices"
SYSFS_FN_LOCK_DEFAULT = "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/fn_lock"
SYSFS_GPU_DEFAULT = "/sys/bus/pci/devices/0000:01:00.0/power"


def get_battery_conservation_status(sysfs_path: str = SYSFS_CONSERVATION_DEFAULT) -> str:
    """Read current battery conservation mode from sysfs."""
    node = Path(sysfs_path)
    if not node.is_file():
        return "unsupported"
    try:
        val = node.read_text().strip()
        return "enabled" if val == "1" else "disabled"
    except Exception:
        return "unsupported"


def set_battery_conservation_mode(enable: bool, sysfs_path: str = SYSFS_CONSERVATION_DEFAULT) -> bool:
    """Write battery conservation mode value to sysfs."""
    target_val = "1" if enable else "0"
    try:
        res = subprocess.run(
            ["tee", sysfs_path],
            input=f"{target_val}\n",
            text=True,
            capture_output=True,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def get_platform_profile(profile_path: str = SYSFS_PROFILE_DEFAULT) -> str:
    """Read current ACPI platform profile."""
    node = Path(profile_path)
    if not node.is_file():
        return "unsupported"
    try:
        return node.read_text().strip()
    except Exception:
        return "unsupported"


def set_platform_profile(
    profile: str,
    profile_path: str = SYSFS_PROFILE_DEFAULT,
    choices_path: str = SYSFS_PROFILE_CHOICES_DEFAULT,
) -> bool:
    """Set ACPI platform profile."""
    target = "low-power" if profile == "quiet" else profile
    choices_node = Path(choices_path)
    if choices_node.is_file():
        valid_choices = choices_node.read_text().strip().split()
        if target not in valid_choices:
            return False
    try:
        res = subprocess.run(
            ["tee", profile_path],
            input=f"{target}\n",
            text=True,
            capture_output=True,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def get_fn_lock_status(fn_path: str = SYSFS_FN_LOCK_DEFAULT) -> str:
    """Read current Fn-Lock status from sysfs."""
    node = Path(fn_path)
    if not node.is_file():
        return "unsupported"
    try:
        val = node.read_text().strip()
        return "enabled" if val == "1" else "disabled"
    except Exception:
        return "unsupported"


def set_fn_lock_mode(enable: bool, fn_path: str = SYSFS_FN_LOCK_DEFAULT) -> bool:
    """Set Fn-Lock mode in sysfs."""
    target_val = "1" if enable else "0"
    try:
        res = subprocess.run(
            ["tee", fn_path],
            input=f"{target_val}\n",
            text=True,
            capture_output=True,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def audit_gpu_runtime_power(gpu_pci_path: str = SYSFS_GPU_DEFAULT) -> dict[str, Any]:
    """Audit discrete GPU runtime power management state."""
    base = Path(gpu_pci_path)
    if not base.is_dir():
        return {"available": False, "details": "Discrete GPU power node not present"}

    status_file = base / "runtime_status"
    control_file = base / "control"
    runtime_status = status_file.read_text().strip() if status_file.is_file() else "unknown"
    control = control_file.read_text().strip() if control_file.is_file() else "unknown"

    return {
        "available": True,
        "runtime_status": runtime_status,
        "control": control,
        "power_saving": runtime_status == "suspended",
    }


def audit_vaapi_acceleration() -> dict[str, Any]:
    """Inspect VA-API hardware video acceleration via vainfo."""
    if not shutil.which("vainfo"):
        return {
            "available": False,
            "details": "vainfo not installed (sudo apt install -y vainfo intel-media-va-driver-non-free)",
        }

    res = subprocess.run(["vainfo"], capture_output=True, text=True, check=False)
    return {
        "available": res.returncode == 0,
        "details": res.stdout if res.returncode == 0 else res.stderr,
    }


def generate_hardware_persist_unit(conf_path: str = "/etc/osm/hardware-tune.conf") -> str:
    """Generate systemd service unit definition for boot persistence."""
    return f"""[Unit]
Description=os-manager Lenovo Hardware Power & ACPI Tuning Persistence
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/osm tune hardware-persist apply --config {conf_path}
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""

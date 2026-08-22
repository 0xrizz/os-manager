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


def generate_sysctl_performance_config() -> str:
    """Generate sysctl performance configuration content."""
    return """# os-manager Debian 13 Kernel Performance Tuning
vm.swappiness = 10
vm.vfs_cache_pressure = 50
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 1024
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
"""


def audit_sysctl_parameters() -> dict[str, str]:
    """Inspect active kernel sysctl values."""
    def _read_sysctl(key: str) -> str:
        res = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, check=False)
        return res.stdout.strip() if res.returncode == 0 else "unknown"

    return {
        "swappiness": _read_sysctl("vm.swappiness"),
        "inotify_watches": _read_sysctl("fs.inotify.max_user_watches"),
        "congestion_control": _read_sysctl("net.ipv4.tcp_congestion_control"),
    }


def audit_fstrim_timer_status() -> dict[str, Any]:
    """Inspect systemd fstrim.timer state."""
    res = subprocess.run(["systemctl", "is-active", "fstrim.timer"], capture_output=True, text=True, check=False)
    return {"active": res.stdout.strip() == "active"}


def audit_ufw_firewall_status() -> dict[str, Any]:
    """Inspect UFW firewall status and default incoming policy."""
    if not shutil.which("ufw"):
        return {"available": False, "active": False, "default_deny_incoming": False}

    res = subprocess.run(["ufw", "status", "verbose"], capture_output=True, text=True, check=False)
    out = res.stdout
    is_active = "Status: active" in out
    default_deny = "deny (incoming)" in out
    return {"available": True, "active": is_active, "default_deny_incoming": default_deny}


def audit_pipewire_audio_status() -> dict[str, Any]:
    """Check availability of PipeWire audio stack."""
    pw_bin = shutil.which("pipewire")
    wp_bin = shutil.which("wireplumber")
    return {
        "available": bool(pw_bin),
        "pipewire": pw_bin or "missing",
        "wireplumber": wp_bin or "missing",
    }


GTK_BOOKMARKS_DEFAULT = os.path.expanduser("~/.config/gtk-3.0/bookmarks")


def get_nautilus_bookmarks(bookmark_file: str = GTK_BOOKMARKS_DEFAULT) -> list[str]:
    """Retrieve list of configured GTK bookmarks."""
    p = Path(bookmark_file)
    if not p.is_file():
        return []
    return [line.strip() for line in p.read_text().splitlines() if line.strip()]


def add_nautilus_bookmark(uri: str, label: str, bookmark_file: str = GTK_BOOKMARKS_DEFAULT) -> bool:
    """Idempotently add a bookmark to the GTK bookmarks file."""
    p = Path(bookmark_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = get_nautilus_bookmarks(bookmark_file)

    for entry in existing:
        if entry.startswith(uri):
            return True

    entry = f"{uri} {label}\n"
    with open(p, "a", encoding="utf-8") as f:
        f.write(entry)
    return True


def apply_desktop_gsettings() -> dict[str, bool]:
    """Apply standard GNOME 48 desktop ergonomics via gsettings."""
    settings = [
        ("org.gnome.desktop.interface", "font-name", "'Inter 10.5'"),
        ("org.gnome.desktop.interface", "document-font-name", "'Inter 11'"),
        ("org.gnome.desktop.interface", "monospace-font-name", "'JetBrains Mono 10'"),
        ("org.gnome.desktop.interface", "font-antialiasing", "'rgba'"),
        ("org.gnome.desktop.interface", "font-hinting", "'slight'"),
        ("org.gnome.desktop.wm.preferences", "button-layout", "'appmenu:minimize,maximize,close'"),
        ("org.gnome.mutter", "center-new-windows", "true"),
        ("org.gnome.desktop.interface", "color-scheme", "'prefer-dark'"),
        ("org.gnome.settings-daemon.plugins.color", "night-light-enabled", "true"),
        ("org.gnome.desktop.peripherals.touchpad", "tap-to-click", "true"),
        ("org.gnome.desktop.peripherals.touchpad", "natural-scroll", "true"),
        ("org.gnome.desktop.peripherals.touchpad", "disable-while-typing", "true"),
        ("org.gnome.desktop.sound", "allow-volume-above-100-percent", "true"),
        ("org.gnome.nautilus.preferences", "default-folder-viewer", "'list-view'"),
        ("org.gnome.nautilus.preferences", "date-time-format", "'detailed'"),
    ]

    results = {}
    for schema, key, val in settings:
        cmd = ["gsettings", "set", schema, key, val]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        results[f"{schema}.{key}"] = res.returncode == 0
    return results


def dconf_dump_desktop(output_file: str) -> bool:
    """Dump GNOME desktop dconf state to file."""
    p = Path(output_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(p, "w", encoding="utf-8") as f:
            res = subprocess.run(["dconf", "dump", "/org/gnome/"], stdout=f, check=False)
            return res.returncode == 0
    except Exception:
        return False


def dconf_load_desktop(input_file: str) -> bool:
    """Load GNOME desktop dconf state from file."""
    p = Path(input_file)
    if not p.is_file():
        return False
    try:
        with open(p, "r", encoding="utf-8") as f:
            res = subprocess.run(["dconf", "load", "/org/gnome/"], stdin=f, check=False)
            return res.returncode == 0
    except Exception:
        return False



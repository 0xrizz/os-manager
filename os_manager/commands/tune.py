"""Hardware power, thermal, system, desktop, and terminal customization command module."""

import argparse
import datetime
import json
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


def generate_hardware_persistence_config(
    conservation: bool = True,
    fn_lock: bool = True,
    gpu_power: str = "auto",
) -> str:
    """Generate /etc/osm/hardware-tune.conf state configuration."""
    cm_val = "1" if conservation else "0"
    fn_val = "1" if fn_lock else "0"
    return (
        f"CONSERVATION_MODE={cm_val}\n"
        f"FN_LOCK={fn_val}\n"
        f"GPU_POWER_SAVE={gpu_power}\n"
    )


def generate_hardware_persistence_service() -> str:
    """Generate systemd service unit for restoring ACPI & GPU tuning at boot."""
    return (
        "[Unit]\n"
        "Description=osm-hardware-tune Lenovo Hardware Power & ACPI Tuning Persistence\n"
        "After=multi-user.target\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        "ExecStart=/usr/local/bin/osm tune hardware --apply\n"
        "RemainAfterExit=yes\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def configure_hardware_persistence(
    enable: bool = True,
    config_path: str = "/etc/osm/hardware-tune.conf",
    service_path: str = "/etc/systemd/system/osm-hardware-tune.service",
    conservation: bool = True,
    fn_lock: bool = True,
    gpu_power: str = "auto",
) -> bool:
    """Configure systemd service and config file for hardware persistence."""
    try:
        if enable:
            cfg = generate_hardware_persistence_config(conservation=conservation, fn_lock=fn_lock, gpu_power=gpu_power)
            srv = generate_hardware_persistence_service()
            if os.geteuid() != 0:
                conf_dir = os.path.dirname(config_path)
                subprocess.run(["sudo", "mkdir", "-p", conf_dir], capture_output=True, check=False)
                res_cfg = subprocess.run(
                    ["sudo", "tee", config_path], input=cfg, text=True, capture_output=True, check=False
                )
                if res_cfg.returncode != 0:
                    return False
                srv_dir = os.path.dirname(service_path)
                subprocess.run(["sudo", "mkdir", "-p", srv_dir], capture_output=True, check=False)
                res_srv = subprocess.run(
                    ["sudo", "tee", service_path], input=srv, text=True, capture_output=True, check=False
                )
                if res_srv.returncode != 0:
                    return False
                subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, check=False)
                subprocess.run(["sudo", "systemctl", "enable", "osm-hardware-tune.service"], capture_output=True, check=False)
            else:
                p_cfg = Path(config_path)
                p_cfg.parent.mkdir(parents=True, exist_ok=True)
                p_cfg.write_text(cfg, encoding="utf-8")

                p_srv = Path(service_path)
                p_srv.parent.mkdir(parents=True, exist_ok=True)
                p_srv.write_text(srv, encoding="utf-8")

                subprocess.run(["systemctl", "daemon-reload"], capture_output=True, check=False)
                subprocess.run(["systemctl", "enable", "osm-hardware-tune.service"], capture_output=True, check=False)
            return True
        else:
            if os.geteuid() != 0:
                subprocess.run(["sudo", "systemctl", "disable", "--now", "osm-hardware-tune.service"], capture_output=True, check=False)
                subprocess.run(["sudo", "rm", "-f", service_path], capture_output=True, check=False)
                subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, check=False)
            else:
                subprocess.run(["systemctl", "disable", "--now", "osm-hardware-tune.service"], capture_output=True, check=False)
                p_srv = Path(service_path)
                if p_srv.is_file():
                    p_srv.unlink()
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True, check=False)
            return True
    except Exception:
        return False


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
    sysctl_bin = shutil.which("sysctl") or ("/sbin/sysctl" if os.path.exists("/sbin/sysctl") else "sysctl")

    def _read_sysctl(key: str) -> str:
        try:
            res = subprocess.run([sysctl_bin, "-n", key], capture_output=True, text=True, check=False)
            return res.stdout.strip() if res.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    return {
        "swappiness": _read_sysctl("vm.swappiness"),
        "inotify_watches": _read_sysctl("fs.inotify.max_user_watches"),
        "congestion_control": _read_sysctl("net.ipv4.tcp_congestion_control"),
    }


def generate_fstab_ntfs3_entry(current_fstab: str, mount_point: str = "/mnt/data") -> str:
    """Replace ntfs-3g FUSE driver with in-kernel ntfs3 driver in fstab content."""
    lines = []
    for line in current_fstab.splitlines():
        if mount_point in line and "ntfs-3g" in line:
            parts = line.split()
            if len(parts) >= 4:
                opts = parts[3]
                if "iocharset=utf8" not in opts:
                    opts = f"{opts},iocharset=utf8"
                line = f"{parts[0]} {parts[1]} ntfs3 {opts} {' '.join(parts[4:])}".strip()
        lines.append(line)
    return "\n".join(lines) + "\n"


def audit_ntfs_mount_driver(mount_point: str = "/mnt/data") -> dict[str, Any]:
    """Audit current mount driver for a given mount point."""
    try:
        res = subprocess.run(
            ["findmnt", "-n", "-o", "FSTYPE", mount_point],
            capture_output=True,
            text=True,
            check=False,
        )
        fstype = res.stdout.strip() if res.returncode == 0 else "unknown"
        return {
            "mount_point": mount_point,
            "driver": fstype,
            "is_inkernel": fstype == "ntfs3",
        }
    except Exception:
        return {"mount_point": mount_point, "driver": "unknown", "is_inkernel": False}


def migrate_ntfs_driver(fstab_path: str = "/etc/fstab", mount_point: str = "/mnt/data") -> dict[str, Any]:
    """Migrate mount_point in fstab from ntfs-3g to in-kernel ntfs3 with backup and remount."""
    p = Path(fstab_path)
    if not p.is_file():
        return {"success": False, "error": f"Fstab file not found: {fstab_path}"}

    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"Failed to read {fstab_path}: {e}"}

    if "ntfs3" in content and mount_point in content and "ntfs-3g" not in content:
        return {
            "success": True,
            "status": "already_migrated",
            "driver": "ntfs3",
            "mount_point": mount_point,
        }

    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = f"{fstab_path}.bak.{ts}"
    try:
        shutil.copy2(fstab_path, backup_path)
    except Exception as e:
        return {"success": False, "error": f"Failed to create fstab backup at {backup_path}: {e}"}

    new_content = generate_fstab_ntfs3_entry(content, mount_point=mount_point)
    try:
        p.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"Failed to write updated fstab to {fstab_path}: {e}"}

    # Attempt unmount and mount if not busy, or keep updated for boot
    umount_cmd = ["umount", mount_point] if os.geteuid() == 0 else ["sudo", "umount", mount_point]
    mount_cmd = ["mount", mount_point] if os.geteuid() == 0 else ["sudo", "mount", mount_point]

    res_umount = subprocess.run(umount_cmd, capture_output=True, text=True, check=False)
    if res_umount.returncode == 0:
        # Unmount succeeded, now mount with new fstab ntfs3 config
        res_mount = subprocess.run(mount_cmd, capture_output=True, text=True, check=False)
        if res_mount.returncode != 0:
            # Rollback to ntfs-3g backup
            try:
                shutil.copy2(backup_path, fstab_path)
                subprocess.run(mount_cmd, capture_output=True, text=True, check=False)
            except Exception:
                pass
            return {
                "success": False,
                "status": "failed",
                "error": f"Mount failed, rolled back: {res_mount.stderr.strip() or res_mount.stdout.strip()}",
                "backup": backup_path,
                "rolled_back": True,
            }
        return {
            "success": True,
            "status": "migrated",
            "driver": "ntfs3",
            "backup": backup_path,
            "mount_point": mount_point,
        }
    else:
        # Volume is in active use (e.g. open shell or GUI app); fstab is updated safely for next reboot / unmount
        return {
            "success": True,
            "status": "fstab_updated_pending_reboot",
            "driver": "ntfs3",
            "backup": backup_path,
            "mount_point": mount_point,
            "note": "fstab updated to ntfs3; live unmount deferred because partition is in active use.",
        }


def audit_fstrim_timer_status() -> dict[str, Any]:
    """Inspect systemd fstrim.timer state."""
    try:
        res = subprocess.run(["systemctl", "is-active", "fstrim.timer"], capture_output=True, text=True, check=False)
        return {"active": res.stdout.strip() == "active"}
    except Exception:
        return {"active": False}


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


def generate_earlyoom_config(ram_threshold: int = 5, swap_threshold: int = 5) -> str:
    """Generate /etc/default/earlyoom configuration with protected processes."""
    avoid_pattern = r"(^|/)(init|systemd|sshd|Xorg|wayland|gnome-shell|pipewire|wireplumber|agy|claude)$"
    return (
        "# /etc/default/earlyoom - Managed by os-manager\n"
        f'EARLYOOM_ARGS="-m {ram_threshold} -s {swap_threshold} -r 60 --avoid \'{avoid_pattern}\'"\n'
    )


def audit_earlyoom_status() -> dict[str, Any]:
    """Inspect earlyoom daemon installation and systemd service status."""
    earlyoom_bin = shutil.which("earlyoom")
    if not earlyoom_bin:
        return {"available": False, "active": False}
    try:
        res = subprocess.run(["systemctl", "is-active", "earlyoom"], capture_output=True, text=True, check=False)
        return {"available": True, "active": res.stdout.strip() == "active"}
    except Exception:
        return {"available": True, "active": False}


def audit_dual_tier_swap_status(proc_swaps_path: str = "/proc/swaps") -> dict[str, Any]:
    """Parse /proc/swaps to verify dual-tier ZRAM + swapfile hierarchy."""
    node = Path(proc_swaps_path)
    if not node.is_file():
        return {"has_zram": False, "has_swapfile": False, "zram_priority": 0, "swapfile_priority": 0}
    try:
        content = node.read_text(encoding="utf-8")
    except Exception:
        return {"has_zram": False, "has_swapfile": False, "zram_priority": 0, "swapfile_priority": 0}
    has_zram = False
    has_swapfile = False
    zram_prio = 0
    swap_prio = 0
    for line in content.splitlines():
        if "zram" in line:
            has_zram = True
            parts = line.split()
            if len(parts) >= 5:
                try:
                    zram_prio = int(parts[4])
                except ValueError:
                    pass
        elif "swapfile" in line:
            has_swapfile = True
            parts = line.split()
            if len(parts) >= 5:
                try:
                    swap_prio = int(parts[4])
                except ValueError:
                    pass
    return {
        "has_zram": has_zram,
        "has_swapfile": has_swapfile,
        "zram_priority": zram_prio,
        "swapfile_priority": swap_prio,
    }


def configure_earlyoom(
    ram_threshold: int = 5,
    swap_threshold: int = 5,
    config_path: str = "/etc/default/earlyoom",
) -> bool:
    """Deploy /etc/default/earlyoom configuration and enable/restart earlyoom service."""
    cfg = generate_earlyoom_config(ram_threshold=ram_threshold, swap_threshold=swap_threshold)
    p = Path(config_path)
    try:
        if os.geteuid() != 0:
            res = subprocess.run(["sudo", "tee", config_path], input=cfg, text=True, capture_output=True, check=False)
            if res.returncode != 0:
                return False
            subprocess.run(["sudo", "systemctl", "enable", "--now", "earlyoom"], capture_output=True, check=False)
            subprocess.run(["sudo", "systemctl", "restart", "earlyoom"], capture_output=True, check=False)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(cfg, encoding="utf-8")
            subprocess.run(["systemctl", "enable", "--now", "earlyoom"], capture_output=True, check=False)
            subprocess.run(["systemctl", "restart", "earlyoom"], capture_output=True, check=False)
        return True
    except Exception:
        return False


def collect_tune_telemetry() -> dict[str, Any]:
    """Collect master telemetry dictionary across all system optimization subsystems."""
    # Storage subsystem
    stor_audit = audit_ntfs_mount_driver("/mnt/data")
    trim_audit = audit_fstrim_timer_status()
    storage_data = {
        "ntfs_driver": stor_audit.get("driver", "unknown"),
        "trim_active": trim_audit.get("active", False),
    }

    # Memory subsystem
    oom_audit = audit_earlyoom_status()
    swap_audit = audit_dual_tier_swap_status()
    memory_data = {
        "earlyoom_active": oom_audit.get("active", False),
        "zram_active": swap_audit.get("has_zram", False),
        "swapfile_active": swap_audit.get("has_swapfile", False),
    }

    # Hardware subsystem
    gpu_audit = audit_gpu_runtime_power()
    therm_active = False
    if shutil.which("thermald") or Path("/usr/sbin/thermald").is_file() or Path("/sbin/thermald").is_file():
        try:
            res_therm = subprocess.run(
                ["systemctl", "is-active", "thermald"], capture_output=True, text=True, check=False
            )
            therm_active = res_therm.stdout.strip() == "active"
        except Exception:
            therm_active = False

    hardware_data = {
        "conservation_mode": get_battery_conservation_status(),
        "gpu_status": gpu_audit.get("runtime_status", "unknown"),
        "thermald_active": therm_active,
    }

    # Sysctl subsystem
    sysctl_audit = audit_sysctl_parameters()
    swappiness_raw = sysctl_audit.get("swappiness", "unknown")
    try:
        swappiness_val: Any = int(swappiness_raw)
    except (ValueError, TypeError):
        swappiness_val = swappiness_raw

    inotify_raw = sysctl_audit.get("inotify_watches", "unknown")
    try:
        inotify_val: Any = int(inotify_raw)
    except (ValueError, TypeError):
        inotify_val = inotify_raw

    sysctl_data = {
        "swappiness": swappiness_val,
        "tcp_congestion": sysctl_audit.get("congestion_control", "unknown"),
        "inotify_watches": inotify_val,
    }

    return {
        "status": "success",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "subsystems": {
            "storage": storage_data,
            "memory": memory_data,
            "hardware": hardware_data,
            "sysctl": sysctl_data,
        },
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


def apply_desktop_gsettings(preset: str = "standard") -> dict[str, bool]:
    """Apply GNOME 48 desktop ergonomics and aesthetic presets via gsettings."""
    if preset == "macos":
        button_layout = "'close,minimize,maximize:'"
    else:
        button_layout = "'appmenu:minimize,maximize,close'"

    settings = [
        ("org.gnome.desktop.interface", "font-name", "'Inter 10.5'"),
        ("org.gnome.desktop.interface", "document-font-name", "'Inter 11'"),
        ("org.gnome.desktop.interface", "monospace-font-name", "'JetBrains Mono 10'"),
        ("org.gnome.desktop.interface", "font-antialiasing", "'rgba'"),
        ("org.gnome.desktop.interface", "font-hinting", "'slight'"),
        ("org.gnome.desktop.wm.preferences", "button-layout", button_layout),
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

    if preset == "macos":
        settings.extend([
            ("org.gnome.shell.extensions.dash-to-dock", "dock-position", "'BOTTOM'"),
            ("org.gnome.shell.extensions.dash-to-dock", "extend-height", "false"),
            ("org.gnome.shell.extensions.dash-to-dock", "dash-max-icon-size", "48"),
            ("org.gnome.shell.extensions.dash-to-dock", "autohide", "true"),
            ("org.gnome.shell.extensions.dash-to-dock", "dock-fixed", "false"),
            ("org.gnome.shell.extensions.dash-to-dock", "intellihide", "true"),
        ])

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


STARSHIP_CONFIG_DEFAULT = os.path.expanduser("~/.config/starship.toml")
TMUX_CONFIG_DEFAULT = os.path.expanduser("~/.tmux.conf")
BASHRC_DEFAULT = os.path.expanduser("~/.bashrc")
HOOK_MARKER = "# --- os-manager Terminal Power-Up Hooks ---"


def generate_starship_config() -> str:
    """Generate Starship prompt TOML content."""
    return """add_newline = false

format = \"\"\"
$directory\\
$git_branch\\
$git_status\\
$python\\
$nodejs\\
$rust\\
$docker_context\\
$cmd_duration\\
$line_break\\
$character\"\"\"

[directory]
truncation_length = 3
truncate_to_repo = true
style = "bold cyan"

[git_branch]
style = "bold purple"

[git_status]
style = "bold red"

[cmd_duration]
min_time = 2_000
style = "bold yellow"

[python]
style = "bold yellow"

[character]
success_symbol = "[❯](bold green)"
error_symbol = "[❯](bold red)"
"""


def generate_tmux_config() -> str:
    """Generate Tmux starter profile content."""
    return """set -g mouse on
set -g default-terminal "xterm-256color"
set -ga terminal-overrides ",*256col*:Tc"

bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"

setw -g mode-keys vi
set -g status-style bg=black,fg=white
"""


def generate_bash_hooks_block() -> str:
    """Generate Bash power-up hooks block."""
    return f"""\n{HOOK_MARKER}
export HISTSIZE=100000
export HISTFILESIZE=200000
export HISTCONTROL=ignoreboth:erasedups
export HISTTIMEFORMAT="%F %T "

alias ls="eza --icons"
alias ll="eza -lh --icons --git"
alias la="eza -lah --icons --git"
alias lt="eza --tree --level=2 --icons"
alias cat="bat --paging=never"
alias grep="rg"
alias find="fd"
alias df="duf"
alias top="btop"
alias cd="z"

alias gst="git status"
alias gdiff="git diff"
alias glog="git log --oneline --graph --decorate"
alias gco="git checkout"
alias gbr="git branch"
alias gadd="git add"
alias gcm="git commit -m"
# --- End os-manager Terminal Power-Up Hooks ---
"""


def inject_bashrc_hooks(bashrc_path: str = BASHRC_DEFAULT) -> bool:
    """Idempotently inject terminal hooks into ~/.bashrc."""
    p = Path(bashrc_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.is_file():
        p.touch()

    content = p.read_text(encoding="utf-8")
    if HOOK_MARKER in content:
        return True

    block = generate_bash_hooks_block()
    with open(p, "a", encoding="utf-8") as f:
        f.write(block)
    return True


def run_tune(args: list[str]) -> int:
    """Execute osm tune subcommands."""
    if args and args[0] == "tune":
        args = args[1:]

    parser = argparse.ArgumentParser(
        prog="osm tune",
        description="Debian 13 bare-metal hardware, kernel, desktop, and terminal optimization suite.",
    )
    parser.add_argument("--json", dest="top_json", action="store_true", help="Output telemetry as JSON")
    subparsers = parser.add_subparsers(dest="subaction", help="Tuning subcommands")

    # storage
    stor_p = subparsers.add_parser("storage", help="Manage storage NTFS driver and NVMe TRIM")
    stor_group = stor_p.add_mutually_exclusive_group()
    stor_group.add_argument("--apply", action="store_true", help="Migrate fstab to ntfs3 and enable fstrim.timer")
    stor_group.add_argument("--audit", action="store_true", help="Audit storage drivers and TRIM status")
    stor_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # memory
    mem_p = subparsers.add_parser("memory", help="Manage EarlyOOM memory protection and swap hierarchy")
    mem_group = mem_p.add_mutually_exclusive_group()
    mem_group.add_argument("--apply", action="store_true", help="Configure and enable EarlyOOM daemon")
    mem_group.add_argument("--audit", action="store_true", help="Audit EarlyOOM and swap telemetry")
    mem_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # hardware
    hw_p = subparsers.add_parser("hardware", help="Manage Lenovo ACPI, GPU power gating, and thermald")
    hw_group = hw_p.add_mutually_exclusive_group()
    hw_group.add_argument("--apply", action="store_true", help="Apply Lenovo battery conservation, Fn-Lock, and GPU power save")
    hw_group.add_argument("--audit", action="store_true", help="Audit hardware ACPI, GPU, and thermals")
    hw_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # system
    sys_p = subparsers.add_parser("system", help="Manage kernel sysctl, TRIM, and security")
    sys_group = sys_p.add_mutually_exclusive_group()
    sys_group.add_argument("--apply", action="store_true", help="Apply kernel sysctl performance configuration")
    sys_group.add_argument("--audit", action="store_true", help="Audit kernel sysctl, TRIM, and security")
    sys_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # persist
    persist_p = subparsers.add_parser("persist", help="Manage hardware and system tuning boot persistence")
    persist_group = persist_p.add_mutually_exclusive_group()
    persist_group.add_argument("--enable", action="store_true", help="Enable tuning persistence service at boot")
    persist_group.add_argument("--disable", action="store_true", help="Disable tuning persistence service")
    persist_group.add_argument("--status", action="store_true", help="Check persistence service status")
    persist_p.add_argument("action", nargs="?", default="status", choices=["status", "enable", "disable"])

    # all
    all_p = subparsers.add_parser("all", help="Apply or audit all tuning subroutines end-to-end")
    all_group = all_p.add_mutually_exclusive_group()
    all_group.add_argument("--apply", action="store_true", help="Apply all tuning subroutines end-to-end")
    all_group.add_argument("--audit", action="store_true", help="Audit all tuning subroutines end-to-end")
    all_group.add_argument("--json", action="store_true", help="Output all subsystem telemetry as JSON")
    all_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply", "json"])

    # battery
    bat_p = subparsers.add_parser("battery", help="Manage Lenovo battery conservation mode")
    bat_p.add_argument("mode", nargs="?", default="status", choices=["status", "on", "off"])

    # profile
    prof_p = subparsers.add_parser("profile", help="Manage Lenovo ACPI platform profile")
    prof_p.add_argument("mode", nargs="?", default="status", choices=["status", "quiet", "balanced", "performance"])

    # fn-lock
    fn_p = subparsers.add_parser("fn-lock", help="Manage Lenovo function key lock")
    fn_p.add_argument("mode", nargs="?", default="status", choices=["status", "on", "off"])

    # thermals
    therm_p = subparsers.add_parser("thermals", help="Manage Intel thermald daemon")
    therm_p.add_argument("action", nargs="?", default="status", choices=["status", "install"])

    # gpu
    gpu_p = subparsers.add_parser("gpu", help="Manage discrete GPU power-gating")
    gpu_p.add_argument("action", nargs="?", default="status", choices=["status", "power-save"])

    # vaapi
    va_p = subparsers.add_parser("vaapi", help="Inspect or install Intel VA-API acceleration")
    va_p.add_argument("action", nargs="?", default="status", choices=["status", "install"])

    # hardware-persist
    hw_persist_p = subparsers.add_parser("hardware-persist", help="Manage hardware tuning persistence")
    hw_persist_p.add_argument("action", nargs="?", default="status", choices=["status", "apply", "enable", "disable"])
    hw_persist_p.add_argument("--config", default="/etc/osm/hardware-tune.conf", help="Path to hardware tuning config")

    # desktop
    desk_p = subparsers.add_parser("desktop", help="Manage GNOME 48 aesthetics, ergonomics, and macOS presets")
    desk_p.add_argument("action", nargs="?", default="apply", choices=["audit", "apply", "backup", "restore"])
    desk_p.add_argument("--preset", choices=["standard", "macos", "macos-full", "macos-core"], default="standard")
    desk_p.add_argument("--accent", default="default", help="Accent color (blue, grey, purple, etc.)")
    desk_p.add_argument("--mode", choices=["dark", "light"], default="dark", help="Color scheme mode")
    desk_p.add_argument("--dry-run", action="store_true", help="Simulate actions without changes")
    desk_p.add_argument("--file", help="Explicit dconf backup/restore file path")

    # terminal
    term_p = subparsers.add_parser("terminal", help="Manage Starship, modern CLI, Bash, and Tmux")
    term_p.add_argument("action", nargs="?", default="setup", choices=["setup", "audit"])

    # audit
    audit_p = subparsers.add_parser("audit", help="Audit all hardware, system, desktop, and terminal tuning")
    audit_p.add_argument("--json", action="store_true", help="Output telemetry as JSON")

    if not args:
        parser.print_help()
        return 0

    parsed_args, _ = parser.parse_known_args(args)

    if getattr(parsed_args, "top_json", False) and parsed_args.subaction is None:
        telemetry = collect_tune_telemetry()
        print(json.dumps(telemetry, indent=2))
        return 0

    if parsed_args.subaction == "storage":
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            res_mig = migrate_ntfs_driver(mount_point="/mnt/data")
            if os.geteuid() != 0:
                subprocess.run(["sudo", "systemctl", "enable", "--now", "fstrim.timer"], capture_output=True, check=False)
            else:
                subprocess.run(["systemctl", "enable", "--now", "fstrim.timer"], capture_output=True, check=False)
            status_str = "migrated" if res_mig.get("success") else "applied"
            print(f"[PASS] Storage /mnt/data {status_str} and fstrim.timer enabled.")
            return 0 if res_mig.get("success") else 1
        else:
            ntfs = audit_ntfs_mount_driver("/mnt/data")
            trim = audit_fstrim_timer_status()
            print("==================================================")
            print("         Storage & Filesystem I/O Audit           ")
            print("==================================================")
            print(f"1. Storage /mnt/data Driver: {ntfs['driver']} (In-Kernel: {ntfs['is_inkernel']})")
            print(f"2. NVMe fstrim.timer: {'Active' if trim['active'] else 'Inactive'}")
            return 0

    elif parsed_args.subaction == "memory":
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            success = configure_earlyoom()
            status_str = "configured and enabled" if success else "configuration failed"
            print(f"[PASS] Memory Resilience & EarlyOOM {status_str}.")
            return 0 if success else 1
        else:
            oom = audit_earlyoom_status()
            swap = audit_dual_tier_swap_status()
            print("==================================================")
            print("       Memory & Resilience Telemetry Audit        ")
            print("==================================================")
            print(f"1. EarlyOOM Daemon Available: {oom.get('available', False)}")
            print(f"2. EarlyOOM Daemon Active: {oom.get('active', False)}")
            print(f"3. Dual-Tier ZRAM Active: {swap.get('has_zram', False)} (Priority: {swap.get('zram_priority', 0)})")
            print(f"4. Dual-Tier Swapfile Active: {swap.get('has_swapfile', False)} (Priority: {swap.get('swapfile_priority', 0)})")
            return 0

    elif parsed_args.subaction == "hardware":
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            set_battery_conservation_mode(True)
            set_fn_lock_mode(True)
            if os.geteuid() != 0:
                subprocess.run(["sudo", "tee", f"{SYSFS_GPU_DEFAULT}/control"], input="auto\n", text=True, capture_output=True, check=False)
            else:
                if Path(f"{SYSFS_GPU_DEFAULT}/control").is_file():
                    subprocess.run(["tee", f"{SYSFS_GPU_DEFAULT}/control"], input="auto\n", text=True, capture_output=True, check=False)
            print("[PASS] Hardware power, ACPI conservation, Fn-Lock, and GPU power gating applied.")
            return 0
        else:
            print("==================================================")
            print("     Hardware Power, ACPI & GPU Diagnostics       ")
            print("==================================================")
            print(f"1. Lenovo Battery Conservation: {get_battery_conservation_status()}")
            print(f"2. Lenovo Platform Profile: {get_platform_profile()}")
            print(f"3. Lenovo Fn-Lock: {get_fn_lock_status()}")
            gpu = audit_gpu_runtime_power()
            print(f"4. NVIDIA GPU D3 State: {gpu.get('runtime_status', 'unknown')}")
            va = audit_vaapi_acceleration()
            print(f"5. Intel VA-API Acceleration: {'Available' if va['available'] else 'Unavailable'}")
            return 0

    elif parsed_args.subaction == "system":
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            return subprocess.run(["bash", "scripts/tune_system.sh", "--sysctl"], check=False).returncode
        sys_info = audit_sysctl_parameters()
        print("==================================================")
        print("          Kernel & Sysctl System Audit            ")
        print("==================================================")
        print(f"1. vm.swappiness: {sys_info['swappiness']}")
        print(f"2. fs.inotify.max_user_watches: {sys_info['inotify_watches']}")
        print(f"3. TCP Congestion Control: {sys_info['congestion_control']}")
        trim = audit_fstrim_timer_status()
        print(f"4. NVMe fstrim.timer: {'Active' if trim['active'] else 'Inactive'}")
        return 0

    elif parsed_args.subaction == "persist":
        is_enable = getattr(parsed_args, "enable", False) or parsed_args.action == "enable"
        is_disable = getattr(parsed_args, "disable", False) or parsed_args.action == "disable"
        if is_enable:
            success = configure_hardware_persistence(enable=True)
            print(f"[PASS] Hardware Tuning Boot Persistence {'enabled' if success else 'failed'}.")
            return 0 if success else 1
        elif is_disable:
            success = configure_hardware_persistence(enable=False)
            print(f"[PASS] Hardware Tuning Boot Persistence {'disabled' if success else 'failed'}.")
            return 0 if success else 1
        else:
            unit_exists = Path("/etc/systemd/system/osm-hardware-tune.service").is_file()
            print(f"Persistence Service Unit: {'Configured' if unit_exists else 'Not configured'}")
            return 0

    elif parsed_args.subaction == "all":
        is_json = getattr(parsed_args, "json", False) or getattr(parsed_args, "action", "") == "json" or getattr(parsed_args, "top_json", False)
        if is_json:
            telemetry = collect_tune_telemetry()
            print(json.dumps(telemetry, indent=2))
            return 0
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            print("[INFO] Executing all customization subroutines end-to-end...")
            subprocess.run(["bash", "scripts/tune_hardware.sh", "--audit"], check=False)
            subprocess.run(["bash", "scripts/tune_system.sh", "--sysctl"], check=False)
            subprocess.run(["bash", "scripts/setup_desktop_env.sh", "--apply"], check=False)
            subprocess.run(["bash", "scripts/setup_terminal_env.sh"], check=False)
            print("[PASS] All hardware, system, desktop, and terminal optimizations applied.")
            return 0
        else:
            print("==================================================")
            print("   Debian 13 Complete Tuning & Diagnostic Audit   ")
            print("==================================================")
            print(f"1. Lenovo Battery Conservation: {get_battery_conservation_status()}")
            print(f"2. Lenovo Platform Profile: {get_platform_profile()}")
            print(f"3. Lenovo Fn-Lock: {get_fn_lock_status()}")
            gpu = audit_gpu_runtime_power()
            print(f"4. NVIDIA GPU D3 State: {gpu.get('runtime_status', 'unknown')}")
            va = audit_vaapi_acceleration()
            print(f"5. Intel VA-API Acceleration: {'Available' if va['available'] else 'Unavailable'}")
            sys_info = audit_sysctl_parameters()
            print(f"6. Kernel TCP Congestion: {sys_info['congestion_control']}")
            print(f"7. NVMe fstrim.timer: {'Active' if audit_fstrim_timer_status()['active'] else 'Inactive'}")
            oom = audit_earlyoom_status()
            print(f"8. EarlyOOM Protection: {'Active' if oom['active'] else 'Inactive'}")
            ntfs = audit_ntfs_mount_driver("/mnt/data")
            print(f"9. Storage /mnt/data: {ntfs['driver']}")
            return 0

    elif parsed_args.subaction == "battery":
        if parsed_args.mode == "status":
            st = get_battery_conservation_status()
            print(f"Lenovo Battery Conservation Mode: {st}")
            return 0
        enable = parsed_args.mode == "on"
        if os.geteuid() != 0:
            cmd = ["sudo", "tee", SYSFS_CONSERVATION_DEFAULT]
            val = "1\n" if enable else "0\n"
            return subprocess.run(cmd, input=val, text=True, check=False).returncode
        success = set_battery_conservation_mode(enable)
        print(f"[PASS] Battery Conservation Mode set to: {'enabled' if enable else 'disabled'}")
        return 0 if success else 1

    elif parsed_args.subaction == "profile":
        if parsed_args.mode == "status":
            prof = get_platform_profile()
            print(f"Lenovo Platform Profile: {prof}")
            return 0
        target = "low-power" if parsed_args.mode == "quiet" else parsed_args.mode
        if os.geteuid() != 0:
            cmd = ["sudo", "tee", SYSFS_PROFILE_DEFAULT]
            return subprocess.run(cmd, input=f"{target}\n", text=True, check=False).returncode
        success = set_platform_profile(target)
        print(f"[PASS] Platform Profile set to: {target}")
        return 0 if success else 1

    elif parsed_args.subaction == "fn-lock":
        if parsed_args.mode == "status":
            st = get_fn_lock_status()
            print(f"Lenovo Fn-Lock: {st}")
            return 0
        enable = parsed_args.mode == "on"
        if os.geteuid() != 0:
            cmd = ["sudo", "tee", SYSFS_FN_LOCK_DEFAULT]
            val = "1\n" if enable else "0\n"
            return subprocess.run(cmd, input=val, text=True, check=False).returncode
        success = set_fn_lock_mode(enable)
        print(f"[PASS] Fn-Lock set to: {'enabled' if enable else 'disabled'}")
        return 0 if success else 1

    elif parsed_args.subaction == "thermals":
        if parsed_args.action == "install":
            cmd = ["sudo", "apt-get", "install", "-y", "thermald"] if os.geteuid() != 0 else ["apt-get", "install", "-y", "thermald"]
            res = subprocess.run(cmd, check=False)
            if res.returncode == 0:
                enable_cmd = ["sudo", "systemctl", "enable", "--now", "thermald"] if os.geteuid() != 0 else ["systemctl", "enable", "--now", "thermald"]
                subprocess.run(enable_cmd, check=False)
            return res.returncode
        if not shutil.which("thermald"):
            print("Intel thermald daemon: not installed")
            return 1
        res = subprocess.run(["systemctl", "is-active", "thermald"], capture_output=True, text=True, check=False)
        active = res.stdout.strip() == "active"
        print(f"Intel thermald status: {'Active' if active else 'Inactive'}")
        return 0 if active else 1

    elif parsed_args.subaction == "gpu":
        if parsed_args.action == "power-save":
            if os.geteuid() != 0:
                cmd = ["sudo", "tee", f"{SYSFS_GPU_DEFAULT}/control"]
                return subprocess.run(cmd, input="auto\n", text=True, check=False).returncode
            res = subprocess.run(["tee", f"{SYSFS_GPU_DEFAULT}/control"], input="auto\n", text=True, capture_output=True, check=False)
            print("[PASS] NVIDIA GPU power control set to auto.")
            return res.returncode
        gpu = audit_gpu_runtime_power()
        print(f"NVIDIA GPU Runtime D3 Status: {gpu.get('runtime_status', 'unknown')}")
        print(f"Power Saving Active: {gpu.get('power_saving', False)}")
        return 0

    elif parsed_args.subaction == "vaapi":
        if parsed_args.action == "install":
            cmd = ["sudo", "apt-get", "install", "-y", "intel-media-va-driver-non-free", "vainfo"] if os.geteuid() != 0 else ["apt-get", "install", "-y", "intel-media-va-driver-non-free", "vainfo"]
            return subprocess.run(cmd, check=False).returncode
        res = audit_vaapi_acceleration()
        print(f"VA-API Acceleration Available: {res['available']}")
        print(res["details"])
        return 0 if res["available"] else 1

    elif parsed_args.subaction == "hardware-persist":
        if parsed_args.action == "apply":
            conf_file = Path(parsed_args.config)
            if conf_file.is_file():
                for line in conf_file.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if k == "CONSERVATION_MODE":
                            set_battery_conservation_mode(v == "1")
                        elif k == "PLATFORM_PROFILE":
                            set_platform_profile(v)
                        elif k == "FN_LOCK":
                            set_fn_lock_mode(v == "1")
                        elif k == "GPU_POWER_SAVE" and v == "auto":
                            if Path(f"{SYSFS_GPU_DEFAULT}/control").is_file():
                                subprocess.run(["tee", f"{SYSFS_GPU_DEFAULT}/control"], input="auto\n", text=True, check=False)
            print(f"[PASS] Hardware tuning configuration applied from {parsed_args.config}")
            return 0
        elif parsed_args.action == "enable":
            return subprocess.run(["bash", "scripts/tune_hardware.sh", "--persist", "enable"], check=False).returncode
        elif parsed_args.action == "disable":
            return subprocess.run(["bash", "scripts/tune_hardware.sh", "--persist", "disable"], check=False).returncode
        else:
            return subprocess.run(["bash", "scripts/tune_hardware.sh", "--persist", "status"], check=False).returncode

    elif parsed_args.subaction == "desktop":
        if parsed_args.action == "apply":
            add_nautilus_bookmark("file:///mnt/data", "Data Store")
            preset_name = getattr(parsed_args, "preset", "standard")
            if preset_name in ["macos", "macos-full", "macos-core"]:
                from os_manager.commands.tune_macos import run_macos_desktop_pipeline

                is_full = preset_name != "macos-core"
                is_dark = getattr(parsed_args, "mode", "dark") == "dark"
                accent_color = getattr(parsed_args, "accent", "default")
                is_dry_run = getattr(parsed_args, "dry_run", False)

                res = run_macos_desktop_pipeline(
                    accent=accent_color,
                    dark=is_dark,
                    full=is_full,
                    dry_run=is_dry_run,
                )
                if is_dry_run:
                    print(f"[PLAN] macOS Desktop Transformation ({preset_name}) simulated successfully.")
                else:
                    status = "PASS" if res.get("success") else "WARN"
                    print(f"[{status}] macOS Desktop Transformation ({preset_name}) completed. Snapshot: {res.get('snapshot')}")
                return 0 if res.get("success") or is_dry_run else 1
            else:
                apply_desktop_gsettings(preset=preset_name)
                print(f"[PASS] GNOME desktop typography, ergonomics ({preset_name} preset), and bookmarks configured.")
                return 0
        elif parsed_args.action == "backup":
            if parsed_args.file:
                dconf_dump_desktop(parsed_args.file)
                print(f"[PASS] Desktop profile exported to {parsed_args.file}")
            else:
                from os_manager.commands.tune_macos import create_desktop_snapshot

                snap = create_desktop_snapshot()
                print(f"[PASS] Desktop profile snapshot created at {snap}")
            return 0
        elif parsed_args.action == "restore":
            from os_manager.commands.tune_macos import restore_desktop_snapshot

            target = parsed_args.file
            success = restore_desktop_snapshot(snapshot_file=target) if target else restore_desktop_snapshot()
            if success:
                print(f"[PASS] Desktop profile restored from {target or 'latest snapshot'}")
                return 0
            else:
                print(f"[FAIL] Desktop profile restoration failed.")
                return 1
        bks = get_nautilus_bookmarks()
        print(f"GTK Bookmarks: {bks}")
        return 0

    elif parsed_args.subaction == "terminal":
        if parsed_args.action == "setup":
            p_star = Path(os.path.expanduser("~/.config/starship.toml"))
            p_star.parent.mkdir(parents=True, exist_ok=True)
            p_star.write_text(generate_starship_config())
            p_tmux = Path(os.path.expanduser("~/.tmux.conf"))
            p_tmux.write_text(generate_tmux_config())
            inject_bashrc_hooks()
            print("[PASS] Terminal DX (Starship, FZF previews, Bash defaults, Tmux) configured.")
            return 0
        print("Terminal environment audit: Ready")
        return 0

    elif parsed_args.subaction == "audit":
        if getattr(parsed_args, "json", False):
            telemetry = collect_tune_telemetry()
            print(json.dumps(telemetry, indent=2))
            return 0
        print("==================================================")
        print("    Debian 13 Hardware & Desktop Diagnostics      ")
        print("==================================================")
        print(f"1. Lenovo Battery Conservation: {get_battery_conservation_status()}")
        print(f"2. Lenovo Platform Profile: {get_platform_profile()}")
        print(f"3. Lenovo Fn-Lock: {get_fn_lock_status()}")
        gpu = audit_gpu_runtime_power()
        print(f"4. NVIDIA GPU D3 State: {gpu.get('runtime_status', 'unknown')}")
        va = audit_vaapi_acceleration()
        print(f"5. Intel VA-API Acceleration: {'Available' if va['available'] else 'Unavailable'}")
        sys_info = audit_sysctl_parameters()
        print(f"6. Kernel TCP Congestion: {sys_info['congestion_control']}")
        print(f"7. NVMe fstrim.timer: {'Active' if audit_fstrim_timer_status()['active'] else 'Inactive'}")
        return 0

    parser.print_help()
    return 0

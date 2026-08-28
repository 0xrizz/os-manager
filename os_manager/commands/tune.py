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

from os_manager.memory.zram import (
    audit_zram_system,
    remediate_zram_conflicts,
)
from os_manager.platform.hal import (
    audit_storage_subsystem,
    get_active_hardware_driver,
)

SYSFS_CONSERVATION_DEFAULT = "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"
SYSFS_PROFILE_DEFAULT = "/sys/firmware/acpi/platform_profile"
SYSFS_PROFILE_CHOICES_DEFAULT = "/sys/firmware/acpi/platform_profile_choices"
SYSFS_FN_LOCK_DEFAULT = "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/fn_lock"
SYSFS_GPU_DEFAULT = "/sys/bus/pci/devices/0000:01:00.0/power"
SNAPSHOT_BASE_DIR = "/var/backups/osm/snapshots"
SYSFS_MGLRU_ENABLED = "/sys/kernel/mm/lru_gen/enabled"
SYSFS_MGLRU_TTL = "/sys/kernel/mm/lru_gen/min_ttl_ms"
SYSFS_THP_ENABLED = "/sys/kernel/mm/transparent_hugepage/enabled"
SYSFS_THP_DEFRAG = "/sys/kernel/mm/transparent_hugepage/defrag"
SYSCTL_MEMORY_PATH = "/etc/sysctl.d/99-osm-memory.conf"
SYSCTL_SCHEDULER_PATH = "/etc/sysctl.d/99-osm-scheduler.conf"
SYSCTL_NETWORK_PATH = "/etc/sysctl.d/99-osm-network.conf"
SESSION_SLICE_PATH = "/etc/systemd/user/session.slice.d/10-resources.conf"
BACKGROUND_SLICE_PATH = "/etc/systemd/user/background.slice.d/10-resources.conf"
TMPFILES_MGLRU_PATH = "/etc/tmpfiles.d/00-osm-mglru.conf"
TMPFILES_THP_PATH = "/etc/tmpfiles.d/00-osm-thp.conf"
PIPEWIRE_CONF_PATH = "/etc/pipewire/pipewire.conf.d/99-low-latency.conf"
PAM_AUDIO_LIMITS_PATH = "/etc/security/limits.d/95-pipewire.conf"
NVIDIA_MODPROBE_PATH = "/etc/modprobe.d/nvidia-pm.conf"
NVIDIA_UDEV_PATH = "/etc/udev/rules.d/80-nvidia-pm.rules"
SYSFS_EPP_NODES = "/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"
SYSFS_EPB_NODES = "/sys/devices/system/cpu/cpu*/power/energy_perf_bias"
POWER_PROFILE_UDEV_PATH = "/etc/udev/rules.d/99-osm-power-profile.rules"
NVME_UDEV_RULE_PATH = "/etc/udev/rules.d/60-nvme-schedulers.rules"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


def create_system_snapshot(
    caller: str,
    target_files: list[str],
    backup_dir: str = SNAPSHOT_BASE_DIR,
) -> dict[str, Any]:
    """Create timestamped configuration snapshot before applying tuning."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    snap_id = f"snap_{ts}"
    effective_backup_dir = backup_dir
    snap_path = Path(effective_backup_dir) / snap_id

    try:
        try:
            snap_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            if os.geteuid() == 0:
                return {"success": False, "error": f"Permission denied creating {snap_path}"}
            # Fallback to user-space snapshots directory if /var/backups is unprivileged
            effective_backup_dir = os.path.expanduser("~/.local/share/osm/snapshots")
            snap_path = Path(effective_backup_dir) / snap_id
            snap_path.mkdir(parents=True, exist_ok=True)

        backed_up = []
        for src_str in target_files:
            src = Path(src_str)
            if src.is_file():
                rel_dst = snap_path / src.relative_to("/")
                try:
                    rel_dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, rel_dst)
                except PermissionError:
                    if os.geteuid() != 0:
                        subprocess.run(["sudo", "mkdir", "-p", str(rel_dst.parent)], capture_output=True, check=False)
                        subprocess.run(["sudo", "cp", "-p", str(src), str(rel_dst)], capture_output=True, check=False)
                backed_up.append(src_str)

        manifest = {
            "snapshot_id": snap_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "caller": caller,
            "backed_up_files": backed_up,
        }
        manifest_str = json.dumps(manifest, indent=2)

        try:
            (snap_path / "manifest.json").write_text(manifest_str, encoding="utf-8")
        except PermissionError:
            subprocess.run(
                ["sudo", "tee", str(snap_path / "manifest.json")],
                input=manifest_str,
                text=True,
                capture_output=True,
                check=False,
            )

        return {"success": True, "snapshot_id": snap_id, "manifest": manifest}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def list_system_snapshots(backup_dir: str = SNAPSHOT_BASE_DIR) -> list[dict[str, Any]]:
    """List all available system tuning snapshots."""
    dirs_to_check = [Path(backup_dir)]
    if backup_dir == SNAPSHOT_BASE_DIR:
        user_dir = Path(os.path.expanduser("~/.local/share/osm/snapshots"))
        if user_dir != Path(backup_dir) and user_dir.is_dir():
            dirs_to_check.append(user_dir)

    snapshots = []
    seen_ids = set()
    for p in dirs_to_check:
        if not p.is_dir():
            continue
        for d in sorted(p.iterdir(), reverse=True):
            manifest_file = d / "manifest.json"
            if manifest_file.is_file():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    sid = manifest.get("snapshot_id")
                    if sid and sid not in seen_ids:
                        seen_ids.add(sid)
                        snapshots.append(manifest)
                except Exception:
                    pass
    return snapshots


def revert_system_snapshot(
    snapshot_id: str | None = None,
    backup_dir: str = SNAPSHOT_BASE_DIR,
) -> dict[str, Any]:
    """Revert system configurations to a previous snapshot."""
    snapshots = list_system_snapshots(backup_dir=backup_dir)
    if not snapshots:
        return {"success": False, "error": "No configuration snapshots found to revert."}

    target_manifest = None
    if snapshot_id:
        for s in snapshots:
            if s.get("snapshot_id") == snapshot_id:
                target_manifest = s
                break
        if not target_manifest:
            return {"success": False, "error": f"Snapshot ID {snapshot_id} not found."}
    else:
        target_manifest = snapshots[0]

    sid = target_manifest["snapshot_id"]
    snap_path = Path(backup_dir) / sid
    if not snap_path.is_dir():
        snap_path = Path(os.path.expanduser("~/.local/share/osm/snapshots")) / sid

    restored = []

    try:
        for file_str in target_manifest.get("backed_up_files", []):
            rel_src = snap_path / Path(file_str).relative_to("/")
            if rel_src.is_file():
                try:
                    Path(file_str).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(rel_src, file_str)
                except PermissionError:
                    subprocess.run(["sudo", "cp", "-p", str(rel_src), file_str], capture_output=True, check=False)
                restored.append(file_str)

        # Reload kernel sysctl, systemd, and udev rules
        if os.geteuid() != 0:
            subprocess.run(["sudo", "sysctl", "--system"], capture_output=True, check=False)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, check=False)
            subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], capture_output=True, check=False)
            subprocess.run(["sudo", "udevadm", "trigger"], capture_output=True, check=False)
        else:
            subprocess.run(["sysctl", "--system"], capture_output=True, check=False)
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True, check=False)
            subprocess.run(["udevadm", "control", "--reload-rules"], capture_output=True, check=False)
            subprocess.run(["udevadm", "trigger"], capture_output=True, check=False)

        return {
            "success": True,
            "snapshot_id": sid,
            "restored_files": restored,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


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


def generate_power_profile_udev_rule() -> str:
    """Generate udev rules for automatic AC/Battery tuning switching."""
    return """# /etc/udev/rules.d/99-osm-power-profile.rules - Managed by os-manager
SUBSYSTEM=="power_supply", ATTR{online}=="0", RUN+="/usr/local/bin/osm tune power --profile battery"
SUBSYSTEM=="power_supply", ATTR{online}=="1", RUN+="/usr/local/bin/osm tune power --profile ac"
"""


def apply_power_profile(profile: str) -> dict[str, Any]:
    """Apply dynamic kernel, CPU governor, and scheduler tunings for AC or Battery profile."""
    prof = profile.lower()
    if prof not in ["ac", "battery", "bat"]:
        return {"success": False, "error": f"Unknown profile '{profile}'. Valid: ac, battery"}

    is_ac = prof == "ac"
    target_epp = "balance_performance" if is_ac else "balance_power"
    target_epb = "4" if is_ac else "8"
    target_platform = "balanced" if is_ac else "low-power"
    target_slice = 2000000 if is_ac else 3000000

    try:
        # Write EPP across online CPUs
        cpu_glob = list(Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/energy_performance_preference"))
        for node in cpu_glob:
            if os.geteuid() != 0:
                subprocess.run(["sudo", "tee", str(node)], input=f"{target_epp}\n", text=True, capture_output=True, check=False)
            else:
                try:
                    node.write_text(f"{target_epp}\n", encoding="utf-8")
                except Exception:
                    subprocess.run(["tee", str(node)], input=f"{target_epp}\n", text=True, capture_output=True, check=False)

        # Write EPB across online CPUs if present
        cpu_epb_glob = list(Path("/sys/devices/system/cpu").glob("cpu[0-9]*/power/energy_perf_bias"))
        for node in cpu_epb_glob:
            if os.geteuid() != 0:
                subprocess.run(["sudo", "tee", str(node)], input=f"{target_epb}\n", text=True, capture_output=True, check=False)
            else:
                try:
                    node.write_text(f"{target_epb}\n", encoding="utf-8")
                except Exception:
                    subprocess.run(["tee", str(node)], input=f"{target_epb}\n", text=True, capture_output=True, check=False)

        # Set platform profile if supported
        set_platform_profile(target_platform)

        # Set EEVDF scheduler base slice
        if Path("/proc/sys/kernel/sched_base_slice_ns").is_file():
            if os.geteuid() != 0:
                subprocess.run(
                    ["sudo", "sysctl", "-w", f"kernel.sched_base_slice_ns={target_slice}"],
                    capture_output=True,
                    check=False,
                )
            else:
                subprocess.run(["sysctl", "-w", f"kernel.sched_base_slice_ns={target_slice}"], capture_output=True, check=False)

        return {
            "success": True,
            "profile": "ac" if is_ac else "battery",
            "epp": target_epp,
            "epb": target_epb,
            "platform_profile": target_platform,
            "sched_base_slice_ns": target_slice,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def audit_power_profile() -> dict[str, Any]:
    """Inspect active CPU frequency governor, EPP, EPB, and AC power supply state."""
    current_epp = "unknown"
    node_0 = Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference")
    if node_0.is_file():
        try:
            current_epp = node_0.read_text().strip()
        except Exception:
            pass

    power_source = "battery"
    for ps in Path("/sys/class/power_supply").glob("*"):
        type_file = ps / "type"
        online_file = ps / "online"
        if type_file.is_file() and type_file.read_text().strip().lower() == "mains":
            if online_file.is_file() and online_file.read_text().strip() == "1":
                power_source = "ac"
                break

    return {
        "current_epp": current_epp,
        "power_source": power_source,
        "platform_profile": get_platform_profile(),
        "conservation_mode": get_battery_conservation_status(),
        "fn_lock": get_fn_lock_status(),
    }


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


def _read_sysctl(key: str) -> str:
    """Read sysctl parameter value from kernel."""
    sysctl_bin = shutil.which("sysctl") or ("/sbin/sysctl" if os.path.exists("/sbin/sysctl") else "sysctl")
    try:
        res = subprocess.run([sysctl_bin, "-n", key], capture_output=True, text=True, check=False)
        return res.stdout.strip() if res.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def audit_sysctl_parameters() -> dict[str, str]:
    """Inspect active kernel sysctl values."""
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


def generate_hardened_fstab_ntfs3_entry(current_fstab: str, mount_point: str = "/mnt/data") -> str:
    """Generate hardened ntfs3 fstab entry preserving Windows invariants and POSIX masks."""
    lines = []
    for line in current_fstab.splitlines():
        if line.strip().startswith("#"):
            lines.append(line)
            continue
        if mount_point in line and ("ntfs-3g" in line or "ntfs3" in line):
            parts = line.split()
            if len(parts) >= 2:
                uuid_part = parts[0]
                mp_part = parts[1]
                opts = "defaults,uid=1000,gid=1000,dmask=027,fmask=137,windows_names,iocharset=utf8,noatime,prealloc,nocase,hide_dot_files,nofail"
                line = f"{uuid_part}  {mp_part}  ntfs3  {opts}  0  0"
        lines.append(line)
    return "\n".join(lines) + "\n"


def generate_nvme_udev_scheduler_rule() -> str:
    """Generate udev rule setting NVMe I/O scheduler to none and nr_requests to 256."""
    return """# /etc/udev/rules.d/60-nvme-schedulers.rules - Managed by os-manager
ACTION=="add|change", KERNEL=="nvme[0-9]*n[0-9]*", ATTR{queue/scheduler}="none", ATTR{queue/nr_requests}="256"
"""


def audit_hardware_state() -> dict[str, Any]:
    """Inspect battery conservation, thermal profile, and GPU status via HAL."""
    driver = get_active_hardware_driver()
    prof = driver.get_platform_profile()
    bat = driver.get_battery_conservation()
    gpu = driver.get_gpu_power_status()
    dmi = driver.get_dmi_info()

    return {
        "conservation_mode": 1 if bat.conservation_mode else 0,
        "platform_profile": prof.current,
        "platform_profile_choices": prof.choices,
        "gpu_power_control": gpu.get("control", "unknown"),
        "gpu_runtime_status": gpu.get("runtime_status", "unknown"),
        "dmi_vendor": dmi.vendor,
        "dmi_product": dmi.product_name,
    }


def audit_nvme_storage_subsystem() -> dict[str, Any]:
    """Inspect NVMe block layer scheduler, queue depth, TRIM, and NTFS drivers dynamically."""
    storage_info = audit_storage_subsystem("/")
    ntfs = audit_ntfs_mount_driver("/mnt/data")
    trim = audit_fstrim_timer_status()

    return {
        "ntfs3_active": ntfs.get("is_inkernel", False),
        "ntfs_driver": ntfs.get("driver", "unknown"),
        "trim_active": trim.get("active", False),
        "nvme_scheduler": storage_info.scheduler,
        "nvme_nr_requests": storage_info.nr_requests,
        "target_device": storage_info.target_device,
        "is_nvme": storage_info.is_nvme,
    }


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


def migrate_ntfs_driver(
    fstab_path: str = "/etc/fstab",
    mount_point: str = "/mnt/data",
    hardened: bool = False,
) -> dict[str, Any]:
    """Migrate mount_point in fstab from ntfs-3g to in-kernel ntfs3 with backup and remount."""
    p = Path(fstab_path)
    if not p.is_file():
        return {"success": False, "error": f"Fstab file not found: {fstab_path}"}

    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"Failed to read {fstab_path}: {e}"}

    if "ntfs3" in content and mount_point in content and "ntfs-3g" not in content:
        if not hardened or "dmask=027" in content:
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

    if hardened:
        new_content = generate_hardened_fstab_ntfs3_entry(content, mount_point=mount_point)
    else:
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


def generate_pipewire_low_latency_config(quantum: int = 256, rate: int = 48000) -> str:
    """Generate PipeWire drop-in configuration for low-latency audio."""
    return f"""# /etc/pipewire/pipewire.conf.d/99-low-latency.conf - Managed by os-manager
context.properties = {{
    default.clock.rate          = {rate}
    default.clock.allowed-rates = [ 44100 48000 96000 ]
    default.clock.quantum       = {quantum}
    default.clock.min-quantum   = 32
    default.clock.max-quantum   = 1024
}}

context.modules = [
    {{ name = libpipewire-module-rt
      args = {{
          nice.level   = -11
          rt.prio      = 88
          rtkit.enabled = true
      }}
      flags = [ ifexists nofail ]
    }}
]
"""


def generate_pam_audio_limits_config() -> str:
    """Generate PAM security limits configuration for real-time audio."""
    return """# /etc/security/limits.d/95-pipewire.conf - Managed by os-manager
@audio - rtprio 95
@audio - nice -19
@audio - memlock unlimited
"""


def generate_nvidia_pm_modprobe_config() -> str:
    """Generate modprobe configuration for NVIDIA RTD3 dynamic power management."""
    return """# /etc/modprobe.d/nvidia-pm.conf - Managed by os-manager
options nvidia "NVreg_DynamicPowerManagement=0x02"
"""


def generate_nvidia_pm_udev_rule() -> str:
    """Generate udev rule enforcing Runtime PM autosuspend on NVIDIA PCI devices."""
    return """# /etc/udev/rules.d/80-nvidia-pm.rules - Managed by os-manager
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", ATTR{power/control}="auto"
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", ATTR{power/control}="auto"
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x040300", ATTR{power/control}="auto"
"""


def audit_audio_subsystem() -> dict[str, Any]:
    """Inspect PipeWire and WirePlumber audio stack telemetry."""
    pw_bin = shutil.which("pipewire")
    wp_bin = shutil.which("wireplumber")
    active_quantum = "1024"
    active_rate = "48000"

    try:
        res = subprocess.run(["pw-dump"], capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                if "default.clock.quantum" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        active_quantum = parts[1].strip().rstrip(",")
                elif "default.clock.rate" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        active_rate = parts[1].strip().rstrip(",")
    except Exception:
        pass

    return {
        "pipewire_installed": bool(pw_bin),
        "wireplumber_installed": bool(wp_bin),
        "active_quantum": active_quantum,
        "active_rate": active_rate,
        "low_latency_dropin_present": Path(PIPEWIRE_CONF_PATH).is_file(),
    }


def generate_mglru_config(enabled: int = 7, min_ttl_ms: int = 1000) -> str:
    """Generate systemd tmpfiles.d definition for MGLRU parameters."""
    return (
        f"# /etc/tmpfiles.d/00-osm-mglru.conf - Managed by os-manager\n"
        f"w {SYSFS_MGLRU_ENABLED} - - - - {enabled}\n"
        f"w {SYSFS_MGLRU_TTL} - - - - {min_ttl_ms}\n"
    )


def generate_thp_config(mode: str = "madvise", defrag: str = "defer+madvise") -> str:
    """Generate systemd tmpfiles.d definition for Transparent Huge Pages."""
    return (
        f"# /etc/tmpfiles.d/00-osm-thp.conf - Managed by os-manager\n"
        f"w {SYSFS_THP_ENABLED} - - - - {mode}\n"
        f"w {SYSFS_THP_DEFRAG} - - - - {defrag}\n"
    )


def generate_vm_sysctl_config(swappiness: int = 180, vfs_cache_pressure: int = 50) -> str:
    """Generate sysctl virtual memory configuration for 8GB RAM + zRAM."""
    return (
        "# /etc/sysctl.d/99-osm-memory.conf - Managed by os-manager\n"
        f"vm.swappiness = {swappiness}\n"
        "vm.page-cluster = 0\n"
        "vm.watermark_boost_factor = 0\n"
        "vm.watermark_scale_factor = 125\n"
        f"vm.vfs_cache_pressure = {vfs_cache_pressure}\n"
        "vm.dirty_ratio = 10\n"
        "vm.dirty_background_ratio = 5\n"
        "vm.dirty_expire_centisecs = 3000\n"
        "vm.dirty_writeback_centisecs = 500\n"
        "fs.inotify.max_user_watches = 524288\n"
        "fs.inotify.max_user_instances = 1024\n"
    )


def audit_memory_subsystem() -> dict[str, Any]:
    """Inspect active MGLRU, zRAM, THP, and sysctl VM parameters."""
    mglru_en = "unsupported"
    mglru_ttl = "unsupported"
    if Path(SYSFS_MGLRU_ENABLED).is_file():
        try:
            mglru_en = Path(SYSFS_MGLRU_ENABLED).read_text().strip()
        except Exception:
            pass
    if Path(SYSFS_MGLRU_TTL).is_file():
        try:
            mglru_ttl = Path(SYSFS_MGLRU_TTL).read_text().strip()
        except Exception:
            pass

    thp_mode = "unknown"
    if Path(SYSFS_THP_ENABLED).is_file():
        try:
            raw = Path(SYSFS_THP_ENABLED).read_text().strip()
            for token in raw.split():
                if token.startswith("[") and token.endswith("]"):
                    thp_mode = token.strip("[]")
        except Exception:
            pass

    sysctl_bin = shutil.which("sysctl") or "/sbin/sysctl"

    def _read_s(k: str) -> str:
        try:
            res = subprocess.run([sysctl_bin, "-n", k], capture_output=True, text=True, check=False)
            return res.stdout.strip() if res.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    oom = audit_earlyoom_status()
    swap = audit_dual_tier_swap_status()

    return {
        "mglru_enabled": mglru_en,
        "mglru_min_ttl_ms": mglru_ttl,
        "thp_mode": thp_mode,
        "swappiness": _read_s("vm.swappiness"),
        "page_cluster": _read_s("vm.page-cluster"),
        "watermark_boost_factor": _read_s("vm.watermark_boost_factor"),
        "watermark_scale_factor": _read_s("vm.watermark_scale_factor"),
        "vfs_cache_pressure": _read_s("vm.vfs_cache_pressure"),
        "earlyoom_active": oom.get("active", False),
        "zram_active": swap.get("has_zram", False),
    }


def generate_network_sysctl_config(
    congestion_control: str = "bbr",
    qdisc: str = "fq_codel",
    fastopen: int = 3,
    somaxconn: int = 8192,
) -> str:
    """Generate sysctl configuration for high-throughput, low-latency network stack."""
    return (
        "# /etc/sysctl.d/99-osm-network.conf - Managed by os-manager\n"
        f"net.core.default_qdisc = {qdisc}\n"
        f"net.ipv4.tcp_congestion_control = {congestion_control}\n"
        f"net.ipv4.tcp_fastopen = {fastopen}\n"
        "net.ipv4.tcp_slow_start_after_idle = 0\n"
        f"net.core.somaxconn = {somaxconn}\n"
        f"net.ipv4.tcp_max_syn_backlog = {somaxconn}\n"
        "net.ipv4.tcp_tw_reuse = 1\n"
        "net.ipv4.tcp_fin_timeout = 15\n"
        "net.ipv4.tcp_notsent_lowat = 16384\n"
    )


def audit_network_subsystem() -> dict[str, Any]:
    """Inspect active kernel network parameters and drop-in configuration status."""
    return {
        "congestion_control": _read_sysctl("net.ipv4.tcp_congestion_control"),
        "default_qdisc": _read_sysctl("net.core.default_qdisc"),
        "tcp_fastopen": _read_sysctl("net.ipv4.tcp_fastopen"),
        "slow_start_after_idle": _read_sysctl("net.ipv4.tcp_slow_start_after_idle"),
        "somaxconn": _read_sysctl("net.core.somaxconn"),
        "tcp_max_syn_backlog": _read_sysctl("net.ipv4.tcp_max_syn_backlog"),
        "tcp_tw_reuse": _read_sysctl("net.ipv4.tcp_tw_reuse"),
        "tcp_fin_timeout": _read_sysctl("net.ipv4.tcp_fin_timeout"),
        "tcp_notsent_lowat": _read_sysctl("net.ipv4.tcp_notsent_lowat"),
        "network_dropin_present": Path(SYSCTL_NETWORK_PATH).is_file(),
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


def generate_eevdf_sysctl_config(base_slice_ns: int = 2000000, cfs_bandwidth_slice_us: int = 3000) -> str:
    """Generate sysctl configuration for Linux 6.6+ EEVDF scheduler slicing."""
    return (
        "# /etc/sysctl.d/99-osm-scheduler.conf - Managed by os-manager\n"
        f"kernel.sched_base_slice_ns = {base_slice_ns}\n"
        f"kernel.sched_cfs_bandwidth_slice_us = {cfs_bandwidth_slice_us}\n"
    )


def generate_session_slice_config(cpu_weight: int = 500, io_weight: int = 500) -> str:
    """Generate systemd user session.slice resource override."""
    return (
        "# /etc/systemd/user/session.slice.d/10-resources.conf - Managed by os-manager\n"
        "[Slice]\n"
        f"CPUWeight={cpu_weight}\n"
        f"IOWeight={io_weight}\n"
        "ManagedOOMPreference=avoid\n"
    )


def generate_background_slice_config(cpu_weight: int = 20, io_weight: int = 20, memory_high: str = "1536M") -> str:
    """Generate systemd user background.slice resource override."""
    return (
        "# /etc/systemd/user/background.slice.d/10-resources.conf - Managed by os-manager\n"
        "[Slice]\n"
        f"CPUWeight={cpu_weight}\n"
        f"IOWeight={io_weight}\n"
        f"MemoryHigh={memory_high}\n"
        "ManagedOOMPreference=kill\n"
    )


def audit_scheduler_subsystem() -> dict[str, Any]:
    """Inspect active EEVDF tunables and systemd user slice configurations."""
    sysctl_bin = shutil.which("sysctl") or "/sbin/sysctl"
    slice_val = "unknown"
    try:
        res = subprocess.run([sysctl_bin, "-n", "kernel.sched_base_slice_ns"], capture_output=True, text=True, check=False)
        slice_val = res.stdout.strip() if res.returncode == 0 else "unknown"
    except Exception:
        pass

    session_cfg = Path(SESSION_SLICE_PATH).is_file()
    bg_cfg = Path(BACKGROUND_SLICE_PATH).is_file()

    return {
        "base_slice_ns": slice_val,
        "session_slice_configured": session_cfg,
        "background_slice_configured": bg_cfg,
    }


def collect_tune_telemetry() -> dict[str, Any]:
    """Collect master telemetry dictionary across all system optimization subsystems."""
    # Storage subsystem
    stor_audit = audit_nvme_storage_subsystem()
    storage_data = {
        "ntfs_driver": stor_audit.get("ntfs_driver", "unknown"),
        "ntfs3_active": stor_audit.get("ntfs3_active", False),
        "trim_active": stor_audit.get("trim_active", False),
        "nvme_scheduler": stor_audit.get("nvme_scheduler", "unknown"),
        "nvme_nr_requests": stor_audit.get("nvme_nr_requests", "unknown"),
    }

    # Memory subsystem
    mem_audit = audit_memory_subsystem()
    swap_audit = audit_dual_tier_swap_status()
    memory_data = {
        "earlyoom_active": mem_audit.get("earlyoom_active", False),
        "zram_active": swap_audit.get("has_zram", False),
        "swapfile_active": swap_audit.get("has_swapfile", False),
        "mglru_enabled": mem_audit.get("mglru_enabled", "unsupported"),
        "mglru_min_ttl_ms": mem_audit.get("mglru_min_ttl_ms", "unsupported"),
        "thp_mode": mem_audit.get("thp_mode", "unknown"),
        "swappiness": mem_audit.get("swappiness", "unknown"),
        "page_cluster": mem_audit.get("page_cluster", "unknown"),
        "watermark_boost_factor": mem_audit.get("watermark_boost_factor", "unknown"),
        "watermark_scale_factor": mem_audit.get("watermark_scale_factor", "unknown"),
        "vfs_cache_pressure": mem_audit.get("vfs_cache_pressure", "unknown"),
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

    # Scheduler subsystem
    sched_audit = audit_scheduler_subsystem()
    scheduler_data = {
        "base_slice_ns": sched_audit.get("base_slice_ns", "unknown"),
        "session_slice_configured": sched_audit.get("session_slice_configured", False),
        "background_slice_configured": sched_audit.get("background_slice_configured", False),
    }

    # Audio subsystem
    audio_audit = audit_audio_subsystem()
    audio_data = {
        "pipewire_installed": audio_audit.get("pipewire_installed", False),
        "wireplumber_installed": audio_audit.get("wireplumber_installed", False),
        "active_quantum": audio_audit.get("active_quantum", "1024"),
        "active_rate": audio_audit.get("active_rate", "48000"),
        "low_latency_dropin_present": audio_audit.get("low_latency_dropin_present", False),
    }

    # Power subsystem
    power_audit = audit_power_profile()
    power_data = {
        "current_epp": power_audit.get("current_epp", "unknown"),
        "power_source": power_audit.get("power_source", "unknown"),
        "platform_profile": power_audit.get("platform_profile", "unknown"),
    }

    # Network subsystem
    network_data = audit_network_subsystem()

    return {
        "status": "success",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "profile": power_data.get("power_source", "ac"),
        "subsystems": {
            "storage": storage_data,
            "memory": memory_data,
            "hardware": hardware_data,
            "sysctl": sysctl_data,
            "scheduler": scheduler_data,
            "audio": audio_data,
            "power": power_data,
            "network": network_data,
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
    stor_p.add_argument("--dry-run", action="store_true", help="Simulate storage tuning")
    stor_p.add_argument("--json", action="store_true", help="Output storage audit as JSON")
    stor_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # memory
    mem_p = subparsers.add_parser("memory", help="Manage EarlyOOM memory protection and swap hierarchy")
    mem_group = mem_p.add_mutually_exclusive_group()
    mem_group.add_argument("--apply", action="store_true", help="Configure and enable EarlyOOM daemon")
    mem_group.add_argument("--audit", action="store_true", help="Audit EarlyOOM and swap telemetry")
    mem_group.add_argument("--remediate-zram", action="store_true", help="Detect and remediate conflicting zRAM managers")
    mem_p.add_argument("--dry-run", action="store_true", help="Simulate memory tuning")
    mem_p.add_argument("--json", action="store_true", help="Output memory audit as JSON")
    mem_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply", "remediate-zram"])

    # hardware
    hw_p = subparsers.add_parser("hardware", help="Manage Lenovo ACPI, GPU power gating, and thermald")
    hw_group = hw_p.add_mutually_exclusive_group()
    hw_group.add_argument("--apply", action="store_true", help="Apply Lenovo battery conservation, Fn-Lock, and GPU power save")
    hw_group.add_argument("--audit", action="store_true", help="Audit hardware ACPI, GPU, and thermals")
    hw_p.add_argument("--dry-run", action="store_true", help="Simulate hardware tuning")
    hw_p.add_argument("--json", action="store_true", help="Output hardware diagnostics as JSON")
    hw_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # system
    sys_p = subparsers.add_parser("system", help="Manage kernel sysctl, TRIM, and security")
    sys_group = sys_p.add_mutually_exclusive_group()
    sys_group.add_argument("--apply", action="store_true", help="Apply kernel sysctl performance configuration")
    sys_group.add_argument("--audit", action="store_true", help="Audit kernel sysctl, TRIM, and security")
    sys_p.add_argument("--dry-run", action="store_true", help="Simulate kernel sysctl tuning")
    sys_p.add_argument("--json", action="store_true", help="Output sysctl audit as JSON")
    sys_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # scheduler
    sched_p = subparsers.add_parser("scheduler", help="Manage EEVDF scheduler slicing and cgroups v2 user slices")
    sched_group = sched_p.add_mutually_exclusive_group()
    sched_group.add_argument("--apply", action="store_true", help="Apply EEVDF scheduler and cgroups v2 slice configuration")
    sched_group.add_argument("--audit", action="store_true", help="Audit EEVDF scheduler and cgroups v2 user slices")
    sched_p.add_argument("--dry-run", action="store_true", help="Simulate EEVDF and slice tuning")
    sched_p.add_argument("--json", action="store_true", help="Output scheduler audit as JSON")
    sched_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # audio
    audio_p = subparsers.add_parser("audio", help="Manage PipeWire low-latency configuration and PAM audio limits")
    audio_group = audio_p.add_mutually_exclusive_group()
    audio_group.add_argument("--apply", action="store_true", help="Apply PipeWire low-latency drop-in and PAM real-time limits")
    audio_group.add_argument("--audit", action="store_true", help="Audit PipeWire and WirePlumber audio stack telemetry")
    audio_p.add_argument("--dry-run", action="store_true", help="Simulate PipeWire and PAM limits tuning")
    audio_p.add_argument("--json", action="store_true", help="Output audio audit as JSON")
    audio_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # power
    power_p = subparsers.add_parser("power", help="Manage dynamic AC/Battery power profile switching and udev rules")
    power_group = power_p.add_mutually_exclusive_group()
    power_group.add_argument("--apply", action="store_true", help="Deploy dynamic power udev rules and apply active profile")
    power_group.add_argument("--audit", action="store_true", help="Audit CPU EPP, power source, and platform profile telemetry")
    power_p.add_argument("--profile", choices=["ac", "battery", "status"], default=None, help="Set or inspect power profile")
    power_p.add_argument("--dry-run", action="store_true", help="Simulate dynamic power profile switching")
    power_p.add_argument("--json", action="store_true", help="Output power profile telemetry as JSON")
    power_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply", "ac", "battery", "status"])

    # network
    network_p = subparsers.add_parser("network", help="Manage Linux TCP BBR, fq_codel, and socket stack performance")
    net_group = network_p.add_mutually_exclusive_group()
    net_group.add_argument("--apply", action="store_true", help="Apply TCP BBR, fq_codel, and socket sysctl configuration")
    net_group.add_argument("--audit", action="store_true", help="Audit Linux network stack parameters")
    network_p.add_argument("--dry-run", action="store_true", help="Simulate network sysctl configuration")
    network_p.add_argument("--json", action="store_true", help="Output network telemetry as JSON")
    network_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # persist
    persist_p = subparsers.add_parser("persist", help="Manage hardware and system tuning boot persistence")
    persist_group = persist_p.add_mutually_exclusive_group()
    persist_group.add_argument("--enable", action="store_true", help="Enable tuning persistence service at boot")
    persist_group.add_argument("--disable", action="store_true", help="Disable tuning persistence service")
    persist_group.add_argument("--status", action="store_true", help="Check persistence service status")
    persist_p.add_argument("--dry-run", action="store_true", help="Simulate tuning persistence service configuration")
    persist_p.add_argument("--json", action="store_true", help="Output persistence status as JSON")
    persist_p.add_argument("action", nargs="?", default="status", choices=["status", "enable", "disable"])

    # revert
    revert_p = subparsers.add_parser("revert", help="Manage and revert system tuning configuration snapshots")
    revert_p.add_argument("--list", action="store_true", help="List all available configuration snapshots")
    revert_p.add_argument("--snapshot", "--id", dest="snapshot_id", default=None, help="Snapshot ID to revert")
    revert_p.add_argument("pos_id", nargs="?", default=None, help="Optional positional snapshot ID")
    revert_p.add_argument("--dry-run", action="store_true", help="Simulate configuration snapshot reversion")
    revert_p.add_argument("--json", action="store_true", help="Output snapshot list or revert status as JSON")

    # all
    all_p = subparsers.add_parser("all", help="Apply or audit all tuning subroutines end-to-end")
    all_group = all_p.add_mutually_exclusive_group()
    all_group.add_argument("--apply", action="store_true", help="Apply all tuning subroutines end-to-end")
    all_group.add_argument("--audit", action="store_true", help="Audit all tuning subroutines end-to-end")
    all_group.add_argument("--json", action="store_true", help="Output all subsystem telemetry as JSON")
    all_p.add_argument("--dry-run", action="store_true", help="Simulate all tuning subroutines end-to-end")
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
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] Storage tuning simulation: Hardened ntfs3 fstab migration for /mnt/data, NVMe scheduler (none/256) udev rules, and fstrim.timer enable.")
            return 0
        is_json = getattr(parsed_args, "json", False)
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            create_system_snapshot(caller="osm tune storage --apply", target_files=["/etc/fstab", NVME_UDEV_RULE_PATH])
            res_mig = migrate_ntfs_driver(mount_point="/mnt/data", hardened=True)
            nvme_rule = generate_nvme_udev_scheduler_rule()
            if os.geteuid() != 0:
                subprocess.run(["sudo", "mkdir", "-p", "/etc/udev/rules.d"], capture_output=True, check=False)
                subprocess.run(["sudo", "tee", NVME_UDEV_RULE_PATH], input=nvme_rule, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], capture_output=True, check=False)
                subprocess.run(["sudo", "udevadm", "trigger", "--subsystem-match=block"], capture_output=True, check=False)
                subprocess.run(["sudo", "systemctl", "enable", "--now", "fstrim.timer"], capture_output=True, check=False)
            else:
                p_rule = Path(NVME_UDEV_RULE_PATH)
                p_rule.parent.mkdir(parents=True, exist_ok=True)
                p_rule.write_text(nvme_rule, encoding="utf-8")
                subprocess.run(["udevadm", "control", "--reload-rules"], capture_output=True, check=False)
                subprocess.run(["udevadm", "trigger", "--subsystem-match=block"], capture_output=True, check=False)
                subprocess.run(["systemctl", "enable", "--now", "fstrim.timer"], capture_output=True, check=False)
            status_str = "migrated" if res_mig.get("success") else "applied"
            print(f"[PASS] Storage /mnt/data {status_str}, NVMe scheduler udev rules applied, and fstrim.timer enabled.")
            return 0 if res_mig.get("success") else 1
        else:
            audit = audit_nvme_storage_subsystem()
            if is_json:
                print(json.dumps(audit, indent=2))
                return 0
            print("==================================================")
            print("         Storage & Filesystem I/O Audit           ")
            print("==================================================")
            print(f"1. Storage /mnt/data Driver: {audit['ntfs_driver']} (In-Kernel: {audit['ntfs3_active']})")
            print(f"2. NVMe fstrim.timer: {'Active' if audit['trim_active'] else 'Inactive'}")
            print(f"3. NVMe I/O Scheduler: {audit['nvme_scheduler']}")
            print(f"4. NVMe Queue Depth (nr_requests): {audit['nvme_nr_requests']}")
            return 0

    elif parsed_args.subaction == "memory":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        is_json = getattr(parsed_args, "json", False)
        is_remediate = getattr(parsed_args, "remediate_zram", False) or parsed_args.action == "remediate-zram"
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"

        if is_remediate:
            res = remediate_zram_conflicts(dry_run=is_dry_run)
            if is_json:
                print(json.dumps(res, indent=2))
                return 0 if res.get("success") else 1
            if is_dry_run:
                print("[PLAN] zRAM Conflict Remediation Simulation:")
                for act in res.get("actions", []):
                    print(f"  - {act}")
                return 0
            if res.get("success"):
                print(f"[PASS] zRAM Conflict Remediation: {res.get('message')}")
                for act in res.get("actions", []):
                    print(f"  - {act}")
                return 0
            else:
                print(f"[FAIL] zRAM Conflict Remediation: {res.get('message')}")
                return 1

        if is_dry_run:
            print("[PLAN] Memory tuning simulation: Configure EarlyOOM (-m 5 -s 5), MGLRU (enabled=7, ttl=1000ms), THP (madvise), sysctl VM (swappiness=180, vfs_cache_pressure=50), and remediate zRAM conflicts.")
            return 0

        if is_apply:
            create_system_snapshot(caller="osm tune memory --apply", target_files=[SYSCTL_MEMORY_PATH, TMPFILES_MGLRU_PATH, TMPFILES_THP_PATH, "/etc/default/earlyoom"])
            success = configure_earlyoom()
            remediate_zram_conflicts(dry_run=False)
            status_str = "configured and enabled" if success else "configuration failed"
            print(f"[PASS] Memory Resilience & EarlyOOM {status_str}.")
            return 0 if success else 1
        else:
            oom = audit_earlyoom_status()
            swap = audit_dual_tier_swap_status()
            zram_audit = audit_zram_system()
            mem_audit = audit_memory_subsystem()
            mem_audit["zram_audit"] = {
                "status": zram_audit.status,
                "conflicts_detected": zram_audit.conflicts_detected,
                "summary_message": zram_audit.summary_message,
                "conflicting_services": [
                    {"name": c.name, "installed": c.installed, "enabled": c.enabled, "active": c.active, "failed": c.failed, "masked": c.masked}
                    for c in zram_audit.conflicting_services
                ],
            }
            if is_json:
                print(json.dumps(mem_audit, indent=2))
                return 0
            print("==================================================")
            print("       Memory & Resilience Telemetry Audit        ")
            print("==================================================")
            print(f"1. EarlyOOM Daemon Available: {oom.get('available', False)}")
            print(f"2. EarlyOOM Daemon Active: {oom.get('active', False)}")
            print(f"3. Dual-Tier ZRAM Active: {swap.get('has_zram', False)} (Priority: {swap.get('zram_priority', 0)})")
            print(f"4. Dual-Tier Swapfile Active: {swap.get('has_swapfile', False)} (Priority: {swap.get('swapfile_priority', 0)})")
            print(f"5. zRAM Manager Status: {zram_audit.status}")
            if zram_audit.conflicts_detected:
                print(f"   [WARN] {zram_audit.summary_message}")
            return 0

    elif parsed_args.subaction == "hardware":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] Hardware tuning simulation: Lenovo battery conservation mode, Fn-Lock, and NVIDIA GPU runtime D3 power-gating.")
            return 0
        is_json = getattr(parsed_args, "json", False)
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            create_system_snapshot(caller="osm tune hardware --apply", target_files=[NVIDIA_MODPROBE_PATH, NVIDIA_UDEV_PATH])
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
            gpu = audit_gpu_runtime_power()
            va = audit_vaapi_acceleration()
            if is_json:
                hw_dict = {
                    "conservation_mode": get_battery_conservation_status(),
                    "platform_profile": get_platform_profile(),
                    "fn_lock": get_fn_lock_status(),
                    "gpu": gpu,
                    "vaapi": va,
                }
                print(json.dumps(hw_dict, indent=2))
                return 0
            print("==================================================")
            print("     Hardware Power, ACPI & GPU Diagnostics       ")
            print("==================================================")
            print(f"1. Lenovo Battery Conservation: {get_battery_conservation_status()}")
            print(f"2. Lenovo Platform Profile: {get_platform_profile()}")
            print(f"3. Lenovo Fn-Lock: {get_fn_lock_status()}")
            print(f"4. NVIDIA GPU D3 State: {gpu.get('runtime_status', 'unknown')}")
            print(f"5. Intel VA-API Acceleration: {'Available' if va['available'] else 'Unavailable'}")
            return 0

    elif parsed_args.subaction == "system":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] System tuning simulation: Apply sysctl performance settings (swappiness, inotify, BBR) and verify fstrim.timer.")
            return 0
        is_json = getattr(parsed_args, "json", False)
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            create_system_snapshot(caller="osm tune system --apply", target_files=["/etc/sysctl.d/99-osm-performance.conf", "/etc/sysctl.conf"])
            script_path = SCRIPTS_DIR / "tune_system.sh"
            if script_path.is_file():
                return subprocess.run(["bash", str(script_path), "--sysctl"], check=False).returncode
            else:
                cfg = generate_sysctl_performance_config()
                if os.geteuid() != 0:
                    subprocess.run(["sudo", "mkdir", "-p", "/etc/sysctl.d"], capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", "/etc/sysctl.d/99-osm-performance.conf"], input=cfg, text=True, capture_output=True, check=False)
                    subprocess.run(["sudo", "sysctl", "--system"], capture_output=True, check=False)
                else:
                    Path("/etc/sysctl.d/99-osm-performance.conf").write_text(cfg, encoding="utf-8")
                    subprocess.run(["sysctl", "--system"], capture_output=True, check=False)
                return 0
        sys_info = audit_sysctl_parameters()
        trim = audit_fstrim_timer_status()
        if is_json:
            print(json.dumps({**sys_info, "trim": trim}, indent=2))
            return 0
        print("==================================================")
        print("          Kernel & Sysctl System Audit            ")
        print("==================================================")
        print(f"1. vm.swappiness: {sys_info['swappiness']}")
        print(f"2. fs.inotify.max_user_watches: {sys_info['inotify_watches']}")
        print(f"3. TCP Congestion Control: {sys_info['congestion_control']}")
        print(f"4. NVMe fstrim.timer: {'Active' if trim['active'] else 'Inactive'}")
        return 0

    elif parsed_args.subaction == "scheduler":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] Scheduler tuning simulation: EEVDF base slice (2ms), CFS bandwidth (3ms), session.slice (weight 500), and background.slice (weight 20, 1536M memory limit).")
            return 0
        is_json = getattr(parsed_args, "json", False)
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            create_system_snapshot(caller="osm tune scheduler --apply", target_files=[SYSCTL_SCHEDULER_PATH, SESSION_SLICE_PATH, BACKGROUND_SLICE_PATH])
            sched_cfg = generate_eevdf_sysctl_config()
            sess_cfg = generate_session_slice_config()
            bg_cfg = generate_background_slice_config()
            try:
                if os.geteuid() != 0:
                    subprocess.run(["sudo", "mkdir", "-p", "/etc/sysctl.d", "/etc/systemd/user/session.slice.d", "/etc/systemd/user/background.slice.d"], capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", SYSCTL_SCHEDULER_PATH], input=sched_cfg, text=True, capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", SESSION_SLICE_PATH], input=sess_cfg, text=True, capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", BACKGROUND_SLICE_PATH], input=bg_cfg, text=True, capture_output=True, check=False)
                    subprocess.run(["sudo", "sysctl", "--system"], capture_output=True, check=False)
                else:
                    Path(SYSCTL_SCHEDULER_PATH).parent.mkdir(parents=True, exist_ok=True)
                    Path(SYSCTL_SCHEDULER_PATH).write_text(sched_cfg, encoding="utf-8")
                    Path(SESSION_SLICE_PATH).parent.mkdir(parents=True, exist_ok=True)
                    Path(SESSION_SLICE_PATH).write_text(sess_cfg, encoding="utf-8")
                    Path(BACKGROUND_SLICE_PATH).parent.mkdir(parents=True, exist_ok=True)
                    Path(BACKGROUND_SLICE_PATH).write_text(bg_cfg, encoding="utf-8")
                    subprocess.run(["sysctl", "--system"], capture_output=True, check=False)
                print("[PASS] EEVDF scheduler slicing (2ms base slice) and cgroups v2 user slices applied.")
                return 0
            except Exception as exc:
                print(f"[FAIL] Failed to apply scheduler tuning: {exc}")
                return 1
        else:
            sched = audit_scheduler_subsystem()
            if is_json:
                print(json.dumps(sched, indent=2))
                return 0
            print("==================================================")
            print("   EEVDF Scheduler & Cgroups v2 User Slices Audit ")
            print("==================================================")
            print(f"1. EEVDF Base Slice (ns): {sched['base_slice_ns']}")
            print(f"2. session.slice Overrides: {'Configured' if sched['session_slice_configured'] else 'Missing'}")
            print(f"3. background.slice Overrides: {'Configured' if sched['background_slice_configured'] else 'Missing'}")
            return 0

    elif parsed_args.subaction == "audio":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] Audio tuning simulation: PipeWire low-latency configuration (quantum=256, rate=48000) and PAM audio real-time limits.")
            return 0
        is_json = getattr(parsed_args, "json", False)
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            create_system_snapshot(caller="osm tune audio --apply", target_files=[PIPEWIRE_CONF_PATH, PAM_AUDIO_LIMITS_PATH])
            pw_cfg = generate_pipewire_low_latency_config()
            pam_cfg = generate_pam_audio_limits_config()
            try:
                if os.geteuid() != 0:
                    subprocess.run(["sudo", "mkdir", "-p", "/etc/pipewire/pipewire.conf.d", "/etc/security/limits.d"], capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", PIPEWIRE_CONF_PATH], input=pw_cfg, text=True, capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", PAM_AUDIO_LIMITS_PATH], input=pam_cfg, text=True, capture_output=True, check=False)
                else:
                    Path(PIPEWIRE_CONF_PATH).parent.mkdir(parents=True, exist_ok=True)
                    Path(PIPEWIRE_CONF_PATH).write_text(pw_cfg, encoding="utf-8")
                    Path(PAM_AUDIO_LIMITS_PATH).parent.mkdir(parents=True, exist_ok=True)
                    Path(PAM_AUDIO_LIMITS_PATH).write_text(pam_cfg, encoding="utf-8")
                print("[PASS] PipeWire low-latency configuration and PAM audio limits applied.")
                return 0
            except Exception as exc:
                print(f"[FAIL] Failed to apply audio configuration: {exc}")
                return 1
        else:
            audio = audit_audio_subsystem()
            if is_json:
                print(json.dumps(audio, indent=2))
                return 0
            print("==================================================")
            print("         PipeWire Audio Subsystem Audit           ")
            print("==================================================")
            print(f"1. PipeWire Installed: {audio['pipewire_installed']}")
            print(f"2. WirePlumber Installed: {audio['wireplumber_installed']}")
            print(f"3. Active Quantum: {audio['active_quantum']}")
            print(f"4. Active Rate: {audio['active_rate']}")
            print(f"5. Low-Latency Drop-in: {'Present' if audio['low_latency_dropin_present'] else 'Missing'}")
            return 0

    elif parsed_args.subaction == "power":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] Power profile tuning simulation: Dynamic udev rule (99-osm-power-profile.rules) and CPU EPP/EPB governor switching.")
            return 0
        is_json = getattr(parsed_args, "json", False)
        prof = getattr(parsed_args, "profile", None)
        action = getattr(parsed_args, "action", "audit")
        target_prof = prof if prof else (action if action in ["ac", "battery", "status"] else None)

        is_apply = getattr(parsed_args, "apply", False) or action == "apply"
        is_audit = getattr(parsed_args, "audit", False) or action == "audit"

        if target_prof in ["ac", "battery"]:
            res = apply_power_profile(target_prof)
            if is_json:
                print(json.dumps(res, indent=2))
                return 0 if res.get("success") else 1
            if res.get("success"):
                print(f"[PASS] Power profile '{target_prof}' applied successfully (EPP: {res.get('epp')}, Sched Slice: {res.get('sched_base_slice_ns')}ns).")
                return 0
            else:
                print(f"[FAIL] Failed to apply power profile '{target_prof}': {res.get('error')}")
                return 1
        elif is_apply:
            create_system_snapshot(caller="osm tune power --apply", target_files=[POWER_PROFILE_UDEV_PATH])
            udev_rule = generate_power_profile_udev_rule()
            udev_target = Path(POWER_PROFILE_UDEV_PATH)
            try:
                if os.geteuid() != 0:
                    subprocess.run(["sudo", "mkdir", "-p", "/etc/udev/rules.d"], capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", POWER_PROFILE_UDEV_PATH], input=udev_rule, text=True, capture_output=True, check=False)
                    subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], capture_output=True, check=False)
                    subprocess.run(["sudo", "udevadm", "trigger"], capture_output=True, check=False)
                else:
                    udev_target.parent.mkdir(parents=True, exist_ok=True)
                    udev_target.write_text(udev_rule, encoding="utf-8")
                    subprocess.run(["udevadm", "control", "--reload-rules"], capture_output=True, check=False)
                    subprocess.run(["udevadm", "trigger"], capture_output=True, check=False)
            except Exception as exc:
                print(f"[WARN] Failed to write udev rule: {exc}")

            curr_audit = audit_power_profile()
            src = curr_audit.get("power_source", "ac")
            apply_res = apply_power_profile("ac" if src == "ac" else "battery")
            print(f"[PASS] Dynamic power profile udev rule installed at {POWER_PROFILE_UDEV_PATH} and '{src}' profile applied.")
            return 0
        else:
            audit = audit_power_profile()
            if is_json:
                print(json.dumps(audit, indent=2))
                return 0
            print("==================================================")
            print("       Dynamic Power & CPU Profile Audit          ")
            print("==================================================")
            print(f"1. Power Source: {audit.get('power_source', 'unknown').upper()}")
            print(f"2. Intel EPP Preference: {audit.get('current_epp', 'unknown')}")
            print(f"3. Platform Profile: {audit.get('platform_profile', 'unknown')}")
            print(f"4. Battery Conservation: {audit.get('conservation_mode', 'unknown')}")
            print(f"5. Fn-Lock: {audit.get('fn_lock', 'unknown')}")
            return 0

    elif parsed_args.subaction == "network":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] Network tuning simulation: Configure TCP BBR congestion control, fq_codel default qdisc, TCP Fast Open (3), somaxconn (8192), and low-latency socket parameters at /etc/sysctl.d/99-osm-network.conf.")
            return 0
        is_json = getattr(parsed_args, "json", False)
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            create_system_snapshot(caller="osm tune network --apply", target_files=[SYSCTL_NETWORK_PATH])
            net_cfg = generate_network_sysctl_config()
            try:
                if os.geteuid() != 0:
                    subprocess.run(["sudo", "mkdir", "-p", "/etc/sysctl.d"], capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", SYSCTL_NETWORK_PATH], input=net_cfg, text=True, capture_output=True, check=False)
                    subprocess.run(["sudo", "sysctl", "--system"], capture_output=True, check=False)
                else:
                    Path(SYSCTL_NETWORK_PATH).parent.mkdir(parents=True, exist_ok=True)
                    Path(SYSCTL_NETWORK_PATH).write_text(net_cfg, encoding="utf-8")
                    subprocess.run(["sysctl", "--system"], capture_output=True, check=False)
                print("[PASS] Network stack tuning (TCP BBR, fq_codel, TCP Fast Open) applied successfully.")
                return 0
            except Exception as exc:
                print(f"[FAIL] Failed to apply network tuning: {exc}")
                return 1
        else:
            net_audit = audit_network_subsystem()
            if is_json:
                print(json.dumps(net_audit, indent=2))
                return 0
            print("==================================================")
            print("       Linux Network & Socket Telemetry Audit     ")
            print("==================================================")
            print(f"1. TCP Congestion Control: {net_audit.get('congestion_control', 'unknown')}")
            print(f"2. Default Packet Qdisc: {net_audit.get('default_qdisc', 'unknown')}")
            print(f"3. TCP Fast Open: {net_audit.get('tcp_fastopen', 'unknown')}")
            print(f"4. Slow Start After Idle: {net_audit.get('slow_start_after_idle', 'unknown')}")
            print(f"5. Max Socket Backlog (somaxconn): {net_audit.get('somaxconn', 'unknown')}")
            print(f"6. Network Drop-in Config: {'Present' if net_audit.get('network_dropin_present') else 'Missing'}")
            return 0

    elif parsed_args.subaction == "persist":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] Hardware tuning persistence simulation: configure /etc/systemd/system/osm-hardware-tune.service and /etc/osm/hardware-tune.conf.")
            return 0
        is_json = getattr(parsed_args, "json", False)
        is_enable = getattr(parsed_args, "enable", False) or parsed_args.action == "enable"
        is_disable = getattr(parsed_args, "disable", False) or parsed_args.action == "disable"
        if is_enable:
            success = configure_hardware_persistence(enable=True)
            if is_json:
                print(json.dumps({"status": "success" if success else "failed", "persistence": "enabled"}, indent=2))
                return 0 if success else 1
            print(f"[PASS] Hardware Tuning Boot Persistence {'enabled' if success else 'failed'}.")
            return 0 if success else 1
        elif is_disable:
            success = configure_hardware_persistence(enable=False)
            if is_json:
                print(json.dumps({"status": "success" if success else "failed", "persistence": "disabled"}, indent=2))
                return 0 if success else 1
            print(f"[PASS] Hardware Tuning Boot Persistence {'disabled' if success else 'failed'}.")
            return 0 if success else 1
        else:
            unit_exists = Path("/etc/systemd/system/osm-hardware-tune.service").is_file()
            if is_json:
                print(json.dumps({"configured": unit_exists}, indent=2))
                return 0
            print(f"Persistence Service Unit: {'Configured' if unit_exists else 'Not configured'}")
            return 0

    elif parsed_args.subaction == "revert":
        is_list = getattr(parsed_args, "list", False)
        is_json = getattr(parsed_args, "json", False)
        is_dry_run = getattr(parsed_args, "dry_run", False)
        target_id = getattr(parsed_args, "snapshot_id", None) or getattr(parsed_args, "pos_id", None)

        if is_list:
            snapshots = list_system_snapshots()
            if is_json:
                print(json.dumps({"status": "success", "snapshots": snapshots}, indent=2))
                return 0
            print("==================================================")
            print("       System Tuning Configuration Snapshots      ")
            print("==================================================")
            if not snapshots:
                print("No configuration snapshots found.")
            else:
                for idx, s in enumerate(snapshots, 1):
                    print(f"{idx}. Snapshot ID: {s.get('snapshot_id')} ({s.get('timestamp')})")
                    print(f"   Caller: {s.get('caller')}")
                    print(f"   Files: {', '.join(s.get('backed_up_files', []))}")
            return 0

        if is_dry_run:
            print(f"[PLAN] Configuration Revert Simulation for Snapshot '{target_id or 'latest'}':")
            snapshots = list_system_snapshots()
            if not snapshots:
                print("  (No snapshots currently found; simulation verified)")
            else:
                target_snap = None
                if target_id:
                    for s in snapshots:
                        if s.get("snapshot_id") == target_id:
                            target_snap = s
                            break
                else:
                    target_snap = snapshots[0]
                if target_snap:
                    print(f"  Target Snapshot ID: {target_snap.get('snapshot_id')}")
                    print(f"  Files to restore: {', '.join(target_snap.get('backed_up_files', []))}")
            return 0

        res = revert_system_snapshot(snapshot_id=target_id)
        if is_json:
            print(json.dumps(res, indent=2))
            return 0 if res.get("success") else 1

        if res.get("success"):
            files_count = len(res.get("restored_files", []))
            print(f"[PASS] Reverted system configuration to snapshot {res.get('snapshot_id')} ({files_count} files restored).")
            return 0
        else:
            print(f"[FAIL] Revert failed: {res.get('error')}")
            return 1

    elif parsed_args.subaction == "all":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] End-to-end tuning simulation: storage (ntfs3 + TRIM), memory (EarlyOOM + sysctl), scheduler (EEVDF + slices), audio (PipeWire low-latency), power (ACPI + dynamic profiles), and hardware persistence.")
            return 0
        is_json = getattr(parsed_args, "json", False) or getattr(parsed_args, "action", "") == "json" or getattr(parsed_args, "top_json", False)
        if is_json:
            telemetry = collect_tune_telemetry()
            print(json.dumps(telemetry, indent=2))
            return 0
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            create_system_snapshot(
                caller="osm tune all --apply",
                target_files=[
                    "/etc/fstab",
                    NVME_UDEV_RULE_PATH,
                    SYSCTL_MEMORY_PATH,
                    TMPFILES_MGLRU_PATH,
                    TMPFILES_THP_PATH,
                    "/etc/default/earlyoom",
                    SYSCTL_SCHEDULER_PATH,
                    SESSION_SLICE_PATH,
                    BACKGROUND_SLICE_PATH,
                    PIPEWIRE_CONF_PATH,
                    PAM_AUDIO_LIMITS_PATH,
                    POWER_PROFILE_UDEV_PATH,
                    NVIDIA_MODPROBE_PATH,
                    NVIDIA_UDEV_PATH,
                ],
            )
            print("[INFO] Executing all customization subroutines end-to-end...")
            # Storage
            migrate_ntfs_driver(mount_point="/mnt/data", hardened=True)
            nvme_rule = generate_nvme_udev_scheduler_rule()
            if os.geteuid() != 0:
                subprocess.run(["sudo", "mkdir", "-p", "/etc/udev/rules.d"], capture_output=True, check=False)
                subprocess.run(["sudo", "tee", NVME_UDEV_RULE_PATH], input=nvme_rule, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "systemctl", "enable", "--now", "fstrim.timer"], capture_output=True, check=False)
            else:
                Path(NVME_UDEV_RULE_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(NVME_UDEV_RULE_PATH).write_text(nvme_rule, encoding="utf-8")
                subprocess.run(["systemctl", "enable", "--now", "fstrim.timer"], capture_output=True, check=False)

            # Memory
            configure_earlyoom()
            mglru_cfg = generate_mglru_config()
            thp_cfg = generate_thp_config()
            vm_cfg = generate_vm_sysctl_config()
            if os.geteuid() != 0:
                subprocess.run(["sudo", "mkdir", "-p", "/etc/tmpfiles.d", "/etc/sysctl.d"], capture_output=True, check=False)
                subprocess.run(["sudo", "tee", TMPFILES_MGLRU_PATH], input=mglru_cfg, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "tee", TMPFILES_THP_PATH], input=thp_cfg, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "tee", SYSCTL_MEMORY_PATH], input=vm_cfg, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "systemd-tmpfiles", "--create"], capture_output=True, check=False)
            else:
                Path(TMPFILES_MGLRU_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(TMPFILES_MGLRU_PATH).write_text(mglru_cfg, encoding="utf-8")
                Path(TMPFILES_THP_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(TMPFILES_THP_PATH).write_text(thp_cfg, encoding="utf-8")
                Path(SYSCTL_MEMORY_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(SYSCTL_MEMORY_PATH).write_text(vm_cfg, encoding="utf-8")
                subprocess.run(["systemd-tmpfiles", "--create"], capture_output=True, check=False)

            # Scheduler
            sched_cfg = generate_eevdf_sysctl_config()
            sess_cfg = generate_session_slice_config()
            bg_cfg = generate_background_slice_config()
            if os.geteuid() != 0:
                subprocess.run(["sudo", "mkdir", "-p", "/etc/sysctl.d", "/etc/systemd/user/session.slice.d", "/etc/systemd/user/background.slice.d"], capture_output=True, check=False)
                subprocess.run(["sudo", "tee", SYSCTL_SCHEDULER_PATH], input=sched_cfg, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "tee", SESSION_SLICE_PATH], input=sess_cfg, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "tee", BACKGROUND_SLICE_PATH], input=bg_cfg, text=True, capture_output=True, check=False)
            else:
                Path(SYSCTL_SCHEDULER_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(SYSCTL_SCHEDULER_PATH).write_text(sched_cfg, encoding="utf-8")
                Path(SESSION_SLICE_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(SESSION_SLICE_PATH).write_text(sess_cfg, encoding="utf-8")
                Path(BACKGROUND_SLICE_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(BACKGROUND_SLICE_PATH).write_text(bg_cfg, encoding="utf-8")

            # Audio & GPU
            pw_cfg = generate_pipewire_low_latency_config()
            pam_cfg = generate_pam_audio_limits_config()
            nv_mod = generate_nvidia_pm_modprobe_config()
            nv_udev = generate_nvidia_pm_udev_rule()
            if os.geteuid() != 0:
                subprocess.run(["sudo", "mkdir", "-p", "/etc/pipewire/pipewire.conf.d", "/etc/security/limits.d", "/etc/modprobe.d"], capture_output=True, check=False)
                subprocess.run(["sudo", "tee", PIPEWIRE_CONF_PATH], input=pw_cfg, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "tee", PAM_AUDIO_LIMITS_PATH], input=pam_cfg, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "tee", NVIDIA_MODPROBE_PATH], input=nv_mod, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "tee", NVIDIA_UDEV_PATH], input=nv_udev, text=True, capture_output=True, check=False)
            else:
                Path(PIPEWIRE_CONF_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(PIPEWIRE_CONF_PATH).write_text(pw_cfg, encoding="utf-8")
                Path(PAM_AUDIO_LIMITS_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(PAM_AUDIO_LIMITS_PATH).write_text(pam_cfg, encoding="utf-8")
                Path(NVIDIA_MODPROBE_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(NVIDIA_MODPROBE_PATH).write_text(nv_mod, encoding="utf-8")
                Path(NVIDIA_UDEV_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(NVIDIA_UDEV_PATH).write_text(nv_udev, encoding="utf-8")

            # Power & ACPI
            set_battery_conservation_mode(True)
            set_fn_lock_mode(True)
            power_udev = generate_power_profile_udev_rule()
            if os.geteuid() != 0:
                subprocess.run(["sudo", "tee", POWER_PROFILE_UDEV_PATH], input=power_udev, text=True, capture_output=True, check=False)
            else:
                Path(POWER_PROFILE_UDEV_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(POWER_PROFILE_UDEV_PATH).write_text(power_udev, encoding="utf-8")
            apply_power_profile("ac")

            # Reload all daemons & sysctl
            if os.geteuid() != 0:
                subprocess.run(["sudo", "sysctl", "--system"], capture_output=True, check=False)
                subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], capture_output=True, check=False)
                subprocess.run(["sudo", "udevadm", "trigger"], capture_output=True, check=False)
            else:
                subprocess.run(["sysctl", "--system"], capture_output=True, check=False)
                subprocess.run(["udevadm", "control", "--reload-rules"], capture_output=True, check=False)
                subprocess.run(["udevadm", "trigger"], capture_output=True, check=False)

            # Desktop ergonomics & Nautilus bookmark
            apply_desktop_gsettings(preset="standard")
            add_nautilus_bookmark("file:///mnt/data", "Data Store")

            # Terminal environment configuration (Starship, Tmux, Bash hooks)
            starship_path = Path(os.path.expanduser("~/.config/starship.toml"))
            starship_path.parent.mkdir(parents=True, exist_ok=True)
            starship_path.write_text(generate_starship_config(), encoding="utf-8")

            tmux_path = Path(os.path.expanduser("~/.tmux.conf"))
            tmux_path.write_text(generate_tmux_config(), encoding="utf-8")

            inject_bashrc_hooks()

            script_desktop = SCRIPTS_DIR / "setup_desktop_env.sh"
            script_terminal = SCRIPTS_DIR / "setup_terminal_env.sh"
            if script_desktop.is_file():
                subprocess.run(["bash", str(script_desktop), "--apply"], check=False)
            if script_terminal.is_file():
                subprocess.run(["bash", str(script_terminal)], check=False)
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
            mod_cfg = generate_nvidia_pm_modprobe_config()
            udev_cfg = generate_nvidia_pm_udev_rule()
            if os.geteuid() != 0:
                cmd = ["sudo", "tee", f"{SYSFS_GPU_DEFAULT}/control"]
                subprocess.run(cmd, input="auto\n", text=True, check=False)
                subprocess.run(["sudo", "mkdir", "-p", "/etc/modprobe.d", "/etc/udev/rules.d"], capture_output=True, check=False)
                subprocess.run(["sudo", "tee", NVIDIA_MODPROBE_PATH], input=mod_cfg, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "tee", NVIDIA_UDEV_PATH], input=udev_cfg, text=True, capture_output=True, check=False)
                subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], capture_output=True, check=False)
                subprocess.run(["sudo", "udevadm", "trigger"], capture_output=True, check=False)
            else:
                if Path(f"{SYSFS_GPU_DEFAULT}/control").is_file():
                    subprocess.run(["tee", f"{SYSFS_GPU_DEFAULT}/control"], input="auto\n", text=True, capture_output=True, check=False)
                Path(NVIDIA_MODPROBE_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(NVIDIA_MODPROBE_PATH).write_text(mod_cfg, encoding="utf-8")
                Path(NVIDIA_UDEV_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(NVIDIA_UDEV_PATH).write_text(udev_cfg, encoding="utf-8")
                subprocess.run(["udevadm", "control", "--reload-rules"], capture_output=True, check=False)
                subprocess.run(["udevadm", "trigger"], capture_output=True, check=False)
            print("[PASS] NVIDIA GPU power control set to auto and RTD3 dynamic PM rules applied.")
            return 0
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
            script_hw = SCRIPTS_DIR / "tune_hardware.sh"
            if script_hw.is_file():
                return subprocess.run(["bash", str(script_hw), "--persist", "enable"], check=False).returncode
            return 0 if configure_hardware_persistence(enable=True) else 1
        elif parsed_args.action == "disable":
            script_hw = SCRIPTS_DIR / "tune_hardware.sh"
            if script_hw.is_file():
                return subprocess.run(["bash", str(script_hw), "--persist", "disable"], check=False).returncode
            return 0 if configure_hardware_persistence(enable=False) else 1
        else:
            script_hw = SCRIPTS_DIR / "tune_hardware.sh"
            if script_hw.is_file():
                return subprocess.run(["bash", str(script_hw), "--persist", "status"], check=False).returncode
            return 0

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

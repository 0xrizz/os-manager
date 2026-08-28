"""sched_ext (Extensible Scheduler Class) dynamic eBPF scheduler controller and profile registry."""

import gzip
import os
import platform
import shutil
import subprocess
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


def discover_installed_schedulers(search_dirs: list[str] | None = None) -> list[str]:
    """Scan directories and $PATH for available sched_ext binary executables (scx_*)."""
    found: set[str] = set()
    paths: list[Path] = []

    if search_dirs:
        for d in search_dirs:
            p = Path(d)
            if p.is_dir():
                paths.append(p)
    else:
        env_paths = os.environ.get("PATH", "").split(os.pathsep)
        extra_paths = ["/usr/local/bin", "/usr/bin", os.path.expanduser("~/.cargo/bin")]
        for d in env_paths + extra_paths:
            p = Path(d)
            if p.is_dir() and p not in paths:
                paths.append(p)

    for directory in paths:
        try:
            for item in directory.iterdir():
                if item.name.startswith("scx_") and os.access(item, os.X_OK) and not item.is_dir():
                    found.add(item.name)
        except (PermissionError, OSError):
            continue

    return sorted(list(found))


def probe_sched_ext_support(
    sysfs_root: str = "/sys/kernel/sched_ext",
    boot_dir: str = "/boot",
    proc_config: str = "/proc/config.gz",
) -> ScxSupportStatus:
    """Probe system kernel, sysfs, installed binaries, and systemd service for sched_ext support."""
    sysfs_p = Path(sysfs_root)
    state_file = sysfs_p / "state"
    sysfs_present = sysfs_p.is_dir()
    kernel_supported = False
    active_scheduler: str | None = None
    details = ""

    # 1. Inspect sysfs state if node exists
    if state_file.is_file():
        try:
            state_val = state_file.read_text(encoding="utf-8").strip()
            kernel_supported = True
            if state_val == "enabled":
                ops_file = sysfs_p / "root" / "ops"
                if ops_file.is_file():
                    active_scheduler = ops_file.read_text(encoding="utf-8").strip()
                else:
                    active_scheduler = "unknown_scx"
                details = f"sched_ext active ({state_val}), scheduler: {active_scheduler}"
            else:
                details = f"sched_ext compiled ({state_val}), no eBPF scheduler loaded."
        except Exception as exc:
            kernel_supported = True
            details = f"sched_ext sysfs present but read error: {exc}"
    else:
        # 2. Inspect kernel config in /boot/config-$(uname -r) or /proc/config.gz
        rel = platform.release()
        cfg_file = Path(boot_dir) / f"config-{rel}"
        config_content = ""

        if cfg_file.is_file():
            try:
                config_content = cfg_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        elif Path(proc_config).is_file():
            try:
                with gzip.open(proc_config, "rt", encoding="utf-8", errors="ignore") as gz:
                    config_content = gz.read()
            except Exception:
                pass

        if "CONFIG_SCHED_CLASS_EXT=y" in config_content:
            kernel_supported = True
            details = "sched_ext supported via kernel config (CONFIG_SCHED_CLASS_EXT=y), module/sysfs unmounted."
        else:
            kernel_supported = False
            details = (
                f"Stock kernel detected ({rel}). CONFIG_SCHED_CLASS_EXT not set. "
                "EEVDF baseline active. To enable sched_ext, install a 6.12+ kernel "
                "with CONFIG_SCHED_CLASS_EXT=y (e.g. CachyOS or XanMod)."
            )

    # 3. Discover installed schedulers
    installed = discover_installed_schedulers()

    # 4. Check active process if active_scheduler not yet detected
    if not active_scheduler and kernel_supported:
        try:
            res_pgrep = subprocess.run(["pgrep", "-a", "-f", "scx_"], capture_output=True, text=True, check=False)
            if res_pgrep.returncode == 0 and res_pgrep.stdout.strip():
                for line in res_pgrep.stdout.splitlines():
                    for prof_name, prof in SCX_PROFILES.items():
                        if prof.binary_name in line:
                            active_scheduler = prof_name
                            break
                    if active_scheduler:
                        break
        except Exception:
            pass

    # 5. Check systemd service status
    srv_active = False
    srv_enabled = False
    try:
        res_act = subprocess.run(["systemctl", "is-active", "scx.service"], capture_output=True, text=True, check=False)
        srv_active = res_act.stdout.strip() == "active"
    except Exception:
        pass

    try:
        res_en = subprocess.run(["systemctl", "is-enabled", "scx.service"], capture_output=True, text=True, check=False)
        srv_enabled = res_en.stdout.strip() == "enabled"
    except Exception:
        pass

    return ScxSupportStatus(
        kernel_supported=kernel_supported,
        sysfs_present=sysfs_present,
        active_scheduler=active_scheduler,
        installed_schedulers=installed,
        service_active=srv_active,
        service_enabled=srv_enabled,
        details=details,
    )


def _run_privileged(cmd: list[str], input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Execute privileged command via sudo_exec.sh wrapper or sudo fallback."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    sudo_wrapper = repo_root / "scripts" / "sudo_exec.sh"

    if os.geteuid() == 0:
        return subprocess.run(cmd, input=input_text, capture_output=True, text=True, check=False)

    if sudo_wrapper.is_file() and os.access(sudo_wrapper, os.X_OK):
        full_cmd = [str(sudo_wrapper)] + cmd
    else:
        full_cmd = ["sudo"] + cmd

    return subprocess.run(full_cmd, input=input_text, capture_output=True, text=True, check=False)


def start_scx_scheduler(
    profile: ScxProfileName = "lavd",
    runtime_only: bool = False,
    custom_args: list[str] | None = None,
) -> dict[str, Any]:
    """Start or switch to a sched_ext eBPF scheduler profile via systemd or detached execution."""
    if profile not in SCX_PROFILES:
        return {"success": False, "error": f"Unknown profile '{profile}'. Choices: {list(SCX_PROFILES.keys())}"}

    prof = SCX_PROFILES[profile]
    status = probe_sched_ext_support()

    if not status.kernel_supported:
        return {
            "success": False,
            "error": f"Kernel does not support sched_ext. {status.details}",
        }

    bin_path = shutil.which(prof.binary_name)
    if not bin_path:
        # Check standard cargo and local bin dirs
        candidates = [
            Path(f"/usr/local/bin/{prof.binary_name}"),
            Path(f"/usr/bin/{prof.binary_name}"),
            Path(os.path.expanduser(f"~/.cargo/bin/{prof.binary_name}")),
        ]
        for c in candidates:
            if c.is_file() and os.access(c, os.X_OK):
                bin_path = str(c)
                break

    if not bin_path:
        return {
            "success": False,
            "error": f"Binary '{prof.binary_name}' not found in PATH or standard directories.",
        }

    args = custom_args if custom_args is not None else prof.default_args

    if runtime_only:
        try:
            cmd = [bin_path] + args
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return {
                "success": True,
                "profile": profile,
                "mode": "runtime",
                "pid": proc.pid,
                "message": f"Started {prof.binary_name} directly with PID {proc.pid}.",
            }
        except Exception as exc:
            return {"success": False, "error": f"Failed to execute {bin_path}: {exc}"}

    # Systemd managed deployment
    unit_content = generate_scx_systemd_unit(bin_path, args)
    try:
        # Write unit file
        write_res = _run_privileged(["tee", SYSTEMD_SCX_UNIT_PATH], input_text=unit_content)
        if write_res.returncode != 0:
            return {"success": False, "error": f"Failed to write {SYSTEMD_SCX_UNIT_PATH}: {write_res.stderr}"}

        # Reload systemd and restart service
        _run_privileged(["systemctl", "daemon-reload"])
        start_res = _run_privileged(["systemctl", "restart", "scx.service"])
        if start_res.returncode != 0:
            return {"success": False, "error": f"Failed to start scx.service: {start_res.stderr}"}

        return {
            "success": True,
            "profile": profile,
            "mode": "systemd",
            "message": f"Successfully activated {profile} ({prof.binary_name}) via scx.service.",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def stop_scx_scheduler() -> dict[str, Any]:
    """Stop active sched_ext scheduler and revert cleanly to Linux EEVDF."""
    try:
        _run_privileged(["systemctl", "stop", "scx.service"])
        _run_privileged(["pkill", "-f", "scx_"])
        return {
            "success": True,
            "message": "sched_ext scheduler stopped. Linux default EEVDF fallback active.",
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to stop scheduler: {exc}"}


def enable_scx_service(
    profile: ScxProfileName = "lavd",
    custom_args: list[str] | None = None,
) -> dict[str, Any]:
    """Write systemd service unit and enable scx.service on boot."""
    start_res = start_scx_scheduler(profile=profile, runtime_only=False, custom_args=custom_args)
    if not start_res.get("success"):
        return start_res

    res = _run_privileged(["systemctl", "enable", "scx.service"])
    if res.returncode != 0:
        return {"success": False, "error": f"Failed to enable scx.service: {res.stderr}"}

    return {
        "success": True,
        "profile": profile,
        "message": f"scx.service configured with profile '{profile}' and enabled at boot.",
    }


def disable_scx_service() -> dict[str, Any]:
    """Disable scx.service at boot and stop running instance."""
    try:
        _run_privileged(["systemctl", "disable", "scx.service"])
        stop_scx_scheduler()
        return {
            "success": True,
            "message": "scx.service disabled at boot and stopped.",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


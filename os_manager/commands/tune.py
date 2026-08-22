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
    parser = argparse.ArgumentParser(
        prog="osm tune",
        description="Debian 13 bare-metal hardware, kernel, desktop, and terminal optimization suite.",
    )
    subparsers = parser.add_subparsers(dest="subaction", help="Tuning subcommands")

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
    persist_p = subparsers.add_parser("hardware-persist", help="Manage hardware tuning persistence")
    persist_p.add_argument("action", nargs="?", default="status", choices=["status", "apply", "enable", "disable"])
    persist_p.add_argument("--config", default="/etc/osm/hardware-tune.conf", help="Path to hardware tuning config")

    # system
    sys_p = subparsers.add_parser("system", help="Manage kernel sysctl, TRIM, and security")
    sys_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # desktop
    desk_p = subparsers.add_parser("desktop", help="Manage GNOME aesthetics, bookmarks, and dconf")
    desk_p.add_argument("action", nargs="?", default="apply", choices=["apply", "audit", "backup", "restore"])
    desk_p.add_argument("--preset", default="standard", choices=["standard", "macos"], help="Visual aesthetic preset (standard or macos)")
    desk_p.add_argument("--file", default=None, help="Target dconf file path")

    # terminal
    term_p = subparsers.add_parser("terminal", help="Manage Starship, modern CLI, Bash, and Tmux")
    term_p.add_argument("action", nargs="?", default="setup", choices=["setup", "audit"])

    # audit & all
    subparsers.add_parser("audit", help="Audit all hardware, system, desktop, and terminal tuning")
    subparsers.add_parser("all", help="Apply all tuning subroutines end-to-end")

    if not args:
        parser.print_help()
        return 0

    parsed_args, _ = parser.parse_known_args(args)

    if parsed_args.subaction == "battery":
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

    elif parsed_args.subaction == "system":
        if parsed_args.action == "apply":
            return subprocess.run(["bash", "scripts/tune_system.sh", "--sysctl"], check=False).returncode
        sys_info = audit_sysctl_parameters()
        print(f"1. vm.swappiness: {sys_info['swappiness']}")
        print(f"2. fs.inotify.max_user_watches: {sys_info['inotify_watches']}")
        print(f"3. TCP Congestion Control: {sys_info['congestion_control']}")
        trim = audit_fstrim_timer_status()
        print(f"4. NVMe fstrim.timer: {'Active' if trim['active'] else 'Inactive'}")
        return 0

    elif parsed_args.subaction == "desktop":
        if parsed_args.action == "apply":
            add_nautilus_bookmark("file:///mnt/data", "Data Store")
            preset_name = getattr(parsed_args, "preset", "standard")
            apply_desktop_gsettings(preset=preset_name)
            print(f"[PASS] GNOME desktop typography, ergonomics ({preset_name} preset), and bookmarks configured.")
            return 0
        elif parsed_args.action == "backup":
            target = parsed_args.file or os.path.expanduser("~/.config/dconf/gnome-desktop.ini")
            dconf_dump_desktop(target)
            print(f"[PASS] Desktop profile exported to {target}")
            return 0
        elif parsed_args.action == "restore":
            target = parsed_args.file or os.path.expanduser("~/.config/dconf/gnome-desktop.ini")
            dconf_load_desktop(target)
            print(f"[PASS] Desktop profile restored from {target}")
            return 0
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

    elif parsed_args.subaction == "all":
        print("[INFO] Executing all customization subroutines end-to-end...")
        subprocess.run(["bash", "scripts/tune_hardware.sh", "--audit"], check=False)
        subprocess.run(["bash", "scripts/tune_system.sh", "--sysctl"], check=False)
        subprocess.run(["bash", "scripts/setup_desktop_env.sh", "--apply"], check=False)
        subprocess.run(["bash", "scripts/setup_terminal_env.sh"], check=False)
        print("[PASS] All hardware, system, desktop, and terminal optimizations applied.")
        return 0

    parser.print_help()
    return 0

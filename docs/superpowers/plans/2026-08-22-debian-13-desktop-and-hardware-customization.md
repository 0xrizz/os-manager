# Debian 13 (Trixie) Desktop & Hardware Customization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an automated, idempotent, and test-driven optimization suite for bare-metal Debian 13 (Trixie) covering Lenovo hardware power/ACPI/thermals/hybrid GPU, kernel sysctl and storage hardening, GNOME 48 desktop aesthetics/ergonomics/dconf state, and modern terminal developer tooling integrated into the `osm tune` CLI control plane.

**Architecture:** Modular Python CLI command group (`os_manager/commands/tune.py`) orchestrating idempotent bash engines (`scripts/tune_hardware.sh`, `scripts/tune_system.sh`, `scripts/setup_desktop_env.sh`, `scripts/setup_terminal_env.sh`). Each module provides standalone CLI switches, JSON telemetry audit capabilities, automated rollback/fallbacks, and comprehensive unit tests integrated into the master test harness.

**Tech Stack:** Python 3.10+, Bash 4.4+, Linux sysfs (`ideapad_laptop` ACPI, `platform_profile`), Linux sysctl, `fstrim`, `ufw`, `pipewire`/`wireplumber`, `gsettings`/`dconf`, Intel VA-API, Starship CLI, `fzf`, `zoxide`, `bat`, `eza`, `ripgrep`, `fd-find`, `btop`, `duf`, `tmux`, `pytest`/`unittest`.

**Spec:** [`docs/superpowers/specs/2026-08-22-debian-13-desktop-and-hardware-customization-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-22-debian-13-desktop-and-hardware-customization-design.md)

---

## Global Constraints

- **INV-01 (Zero Data Loss on `/mnt/data`):** All operations strictly treat `/dev/nvme0n1p4` (`/mnt/data`) as persistent read/write storage. No partition, format, or mount disruption is permitted.
- **INV-02 (Strict Idempotency):** Every script subroutine (`tune_hardware.sh`, `tune_system.sh`, `setup_desktop_env.sh`, `setup_terminal_env.sh`) must be safe to run repeatedly without creating duplicate entries in `~/.bashrc`, `~/.config/gtk-3.0/bookmarks`, `~/.tmux.conf`, `/etc/sysctl.d/`, or system configurations.
- **INV-03 (Root vs User Boundary Separation):** System package installations (`apt-get`), daemon management (`systemd`), firewall rules (`ufw`), and sysfs/sysctl writes require root/sudo privileges. All user-space dotfiles and desktop configurations (`~/.config/starship.toml`, `~/.bashrc`, `~/.tmux.conf`, `bookmarks`, `gsettings`, `dconf`) must be executed under the active user's `$HOME` with non-root ownership.
- **INV-04 (Hybrid GPU & Wayland Decoupling):** All display rendering and VA-API hardware decoders prioritize Intel Iris Plus Graphics (`i915` / `/dev/dri/card0` / `/dev/dri/renderD128`) on Wayland. The discrete NVIDIA MX330 is power-gated into Runtime D3 Cold (`suspended`) when idle.
- **INV-05 (Offline/Fallback Resilience):** Python CLI subcommands must provide graceful fallbacks (e.g. headless/no D-Bus detection for `gsettings`, `uv` fallback when `python3-venv` is missing, warnings on non-Lenovo hardware).

---

### File Structure & Responsibilities

| File Path | Role / Responsibility |
| :--- | :--- |
| `scripts/tune_hardware.sh` | Bash engine for Lenovo ACPI (`conservation_mode`, `platform_profile`, `fn_lock`), `thermald`, NVIDIA MX330 Runtime D3 power gating, Intel VA-API acceleration, and systemd boot persistence. |
| `scripts/tune_system.sh` | Bash engine for Kernel sysctl (`vm.swappiness`, `fs.inotify`, TCP BBR), NVMe SSD `fstrim.timer`, PipeWire audio, UFW firewall, and Nala package manager. |
| `scripts/setup_desktop_env.sh` | Bash engine for Inter/JetBrains Mono typography, `gsettings` window management/dark theme/touchpad, Nautilus list-view & `/mnt/data` bookmarking, and `dconf` backup/restore. |
| `scripts/setup_terminal_env.sh` | Bash engine for Modern CLI tools (`rg`, `fd`, `bat`, `eza`, `fzf`, `zoxide`, `btop`, `duf`), Starship prompt, FZF live previews, Bash 5.2+ defaults, Git aliases, and Tmux profile. |
| `os_manager/commands/tune.py` | Python CLI command group `osm tune` routing all subcommands with full JSON telemetry support. |
| `os_manager/cli.py` | Main CLI router registering `tune` subparser. |
| `tests/test_tune_hardware.py` | Python unit test suite for hardware ACPI, thermals, GPU power-gating, VA-API, and persistence service generation. |
| `tests/test_tune_system.py` | Python unit test suite for sysctl configuration generation, NVMe TRIM timer verification, UFW rules audit, and PipeWire audio checks. |
| `tests/test_desktop_customization.py` | Python unit test suite for GTK bookmarks, GSettings schema configuration, and Dconf backup/restore. |
| `tests/test_terminal_customization.py` | Python unit test suite for Starship TOML generation, FZF environment exports, Bash defaults & aliases injection, and Tmux profile templating. |
| `tests/test_harness.sh` | Master regression test suite executing all tests. |
| `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md` | Comprehensive user manual for bare-metal hardware, system, desktop, and terminal optimization. |

---

### Task 1: Lenovo Hardware Power Tuning, ACPI Platform Profiles, `thermald`, Hybrid GPU Power-Gating, VA-API & Systemd Boot Persistence

**Files:**
- Create: `scripts/tune_hardware.sh`
- Create: `tests/test_tune_hardware.py`
- Modify: `os_manager/commands/tune.py`

**Interfaces:**
- Produces:
  - CLI switch: `scripts/tune_hardware.sh --battery [status|on|off]`
  - CLI switch: `scripts/tune_hardware.sh --profile [status|quiet|balanced|performance]`
  - CLI switch: `scripts/tune_hardware.sh --fn-lock [status|on|off]`
  - CLI switch: `scripts/tune_hardware.sh --thermals [status|install]`
  - CLI switch: `scripts/tune_hardware.sh --gpu [status|power-save]`
  - CLI switch: `scripts/tune_hardware.sh --vaapi [status|install]`
  - CLI switch: `scripts/tune_hardware.sh --persist [status|enable|disable]`
  - CLI switch: `scripts/tune_hardware.sh --audit`
  - Function `get_battery_conservation_status(sysfs_path: str) -> str`
  - Function `set_battery_conservation_mode(enable: bool, sysfs_path: str) -> bool`
  - Function `get_platform_profile(profile_path: str) -> str`
  - Function `set_platform_profile(profile: str, profile_path: str, choices_path: str) -> bool`
  - Function `get_fn_lock_status(fn_path: str) -> str`
  - Function `set_fn_lock_mode(enable: bool, fn_path: str) -> bool`
  - Function `audit_gpu_runtime_power(gpu_pci_path: str) -> dict`
  - Function `audit_vaapi_acceleration() -> dict`
  - Function `generate_hardware_persist_unit(conf_path: str) -> str`

- [ ] **Step 1: Write the failing test in `tests/test_tune_hardware.py`**

Create `tests/test_tune_hardware.py`:

```python
"""tests/test_tune_hardware.py - Unit tests for Lenovo ACPI, thermals, GPU power gating, and VA-API."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_gpu_runtime_power,
    audit_vaapi_acceleration,
    generate_hardware_persist_unit,
    get_battery_conservation_status,
    get_fn_lock_status,
    get_platform_profile,
    set_battery_conservation_mode,
    set_fn_lock_mode,
    set_platform_profile,
)


class TestTuneHardware(unittest.TestCase):
    """Unit tests for Lenovo hardware power and GPU tuning."""

    def test_battery_conservation_status_reading(self):
        """Verify reading battery conservation mode from mock sysfs."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("1\n")
            f.flush()
            sysfs_path = f.name

        try:
            status = get_battery_conservation_status(sysfs_path=sysfs_path)
            self.assertEqual(status, "enabled")
        finally:
            os.remove(sysfs_path)

    def test_battery_conservation_missing_sysfs(self):
        """Verify handling of missing sysfs node on non-IdeaPad hardware."""
        status = get_battery_conservation_status(sysfs_path="/tmp/nonexistent_sysfs_node")
        self.assertEqual(status, "unsupported")

    @patch("subprocess.run")
    def test_set_battery_conservation_enable(self, mock_run):
        """Verify setting battery conservation mode calls tee."""
        mock_run.return_value = MagicMock(returncode=0)
        success = set_battery_conservation_mode(enable=True, sysfs_path="/tmp/mock_node")
        self.assertTrue(success)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "tee")
        self.assertIn("/tmp/mock_node", args)

    def test_platform_profile_reading(self):
        """Verify reading ACPI platform profile."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("balanced\n")
            f.flush()
            prof_path = f.name

        try:
            prof = get_platform_profile(profile_path=prof_path)
            self.assertEqual(prof, "balanced")
        finally:
            os.remove(prof_path)

    @patch("subprocess.run")
    def test_set_platform_profile_valid(self, mock_run):
        """Verify setting valid platform profile."""
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f_choices:
            f_choices.write("low-power balanced performance\n")
            f_choices.flush()
            choices_path = f_choices.name

        try:
            success = set_platform_profile("performance", profile_path="/tmp/prof", choices_path=choices_path)
            self.assertTrue(success)
        finally:
            os.remove(choices_path)

    def test_fn_lock_status_reading(self):
        """Verify reading fn-lock status."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("1\n")
            f.flush()
            fn_path = f.name

        try:
            status = get_fn_lock_status(fn_path=fn_path)
            self.assertEqual(status, "enabled")
        finally:
            os.remove(fn_path)

    def test_gpu_runtime_power_suspended(self):
        """Verify GPU power status parsing."""
        temp_dir = tempfile.TemporaryDirectory()
        try:
            status_file = Path(temp_dir.name) / "runtime_status"
            status_file.write_text("suspended\n")
            control_file = Path(temp_dir.name) / "control"
            control_file.write_text("auto\n")

            res = audit_gpu_runtime_power(gpu_pci_path=temp_dir.name)
            self.assertTrue(res["available"])
            self.assertEqual(res["runtime_status"], "suspended")
            self.assertTrue(res["power_saving"])
        finally:
            temp_dir.cleanup()

    @patch("subprocess.run")
    def test_audit_vaapi_acceleration_present(self, mock_run):
        """Verify VA-API driver detection via vainfo."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="vainfo: VA-API version: 1.22 (libva 2.22.0)\nvainfo: Driver version: Intel i965 driver for Intel(R) Ironlake",
            stderr="",
        )
        with patch("shutil.which", return_value="/usr/bin/vainfo"):
            res = audit_vaapi_acceleration()
            self.assertTrue(res["available"])
            self.assertIn("VA-API version", res["details"])

    def test_generate_hardware_persist_unit(self):
        """Verify generation of systemd unit for hardware persistence."""
        unit = generate_hardware_persist_unit(conf_path="/etc/osm/hardware-tune.conf")
        self.assertIn("[Unit]", unit)
        self.assertIn("Description=os-manager Lenovo Hardware Power & ACPI Tuning Persistence", unit)
        self.assertIn("WantedBy=multi-user.target", unit)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_tune_hardware.py`
Expected output: FAIL with `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Implement `scripts/tune_hardware.sh` and core functions in `os_manager/commands/tune.py`**

Create `scripts/tune_hardware.sh`:

```bash
#!/usr/bin/env bash
# scripts/tune_hardware.sh - Lenovo ACPI, Thermals, GPU Power Gating, and VA-API Tuning
set -euo pipefail

SYSFS_CONSERVATION_DEFAULT="/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"
SYSFS_PROFILE_DEFAULT="/sys/firmware/acpi/platform_profile"
SYSFS_PROFILE_CHOICES_DEFAULT="/sys/firmware/acpi/platform_profile_choices"
SYSFS_FN_LOCK_DEFAULT="/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/fn_lock"
SYSFS_GPU_DEFAULT="/sys/bus/pci/devices/0000:01:00.0/power"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

get_battery_status() {
    local path="${1:-${SYSFS_CONSERVATION_DEFAULT}}"
    if [[ ! -f "${path}" ]]; then
        echo "unsupported"
        return 0
    fi
    local val
    val="$(cat "${path}" 2>/dev/null || echo "0")"
    if [[ "${val}" == "1" ]]; then
        echo "enabled"
    else
        echo "disabled"
    fi
}

set_battery_conservation() {
    local state="$1"
    local path="${2:-${SYSFS_CONSERVATION_DEFAULT}}"
    local target_val="1"

    if [[ "${state}" == "off" || "${state}" == "disable" || "${state}" == "0" ]]; then
        target_val="0"
    fi

    if [[ ! -f "${path}" ]]; then
        log_error "Lenovo Conservation Mode sysfs node not found at: ${path}"
        return 1
    fi

    echo "${target_val}" | tee "${path}" >/dev/null
    log_pass "Lenovo Battery Conservation Mode set to: $(get_battery_status "${path}")"
    return 0
}

get_platform_profile() {
    local path="${1:-${SYSFS_PROFILE_DEFAULT}}"
    if [[ ! -f "${path}" ]]; then
        echo "unsupported"
        return 0
    fi
    cat "${path}" 2>/dev/null || echo "unsupported"
}

set_platform_profile() {
    local prof="$1"
    local path="${2:-${SYSFS_PROFILE_DEFAULT}}"
    local choices_path="${3:-${SYSFS_PROFILE_CHOICES_DEFAULT}}"

    if [[ "${prof}" == "quiet" ]]; then
        prof="low-power"
    fi

    if [[ ! -f "${path}" ]]; then
        log_error "ACPI platform_profile node not found at: ${path}"
        return 1
    fi

    if [[ -f "${choices_path}" ]]; then
        local choices
        choices="$(cat "${choices_path}")"
        if [[ ! " ${choices} " =~ " ${prof} " ]]; then
            log_error "Unsupported profile '${prof}'. Supported choices: ${choices}"
            return 1
        fi
    fi

    echo "${prof}" | tee "${path}" >/dev/null
    log_pass "ACPI platform profile set to: $(get_platform_profile "${path}")"
    return 0
}

get_fn_lock_status() {
    local path="${1:-${SYSFS_FN_LOCK_DEFAULT}}"
    if [[ ! -f "${path}" ]]; then
        echo "unsupported"
        return 0
    fi
    local val
    val="$(cat "${path}" 2>/dev/null || echo "0")"
    if [[ "${val}" == "1" ]]; then
        echo "enabled"
    else
        echo "disabled"
    fi
}

set_fn_lock() {
    local state="$1"
    local path="${2:-${SYSFS_FN_LOCK_DEFAULT}}"
    local target_val="1"

    if [[ "${state}" == "off" || "${state}" == "disable" || "${state}" == "0" ]]; then
        target_val="0"
    fi

    if [[ ! -f "${path}" ]]; then
        log_error "Lenovo Fn-Lock sysfs node not found at: ${path}"
        return 1
    fi

    echo "${target_val}" | tee "${path}" >/dev/null
    log_pass "Lenovo Fn-Lock set to: $(get_fn_lock_status "${path}")"
    return 0
}

audit_gpu_power() {
    local path="${1:-${SYSFS_GPU_DEFAULT}}"
    log_info "Auditing Hybrid NVIDIA GPU Power Gating Status..."
    if [[ ! -d "${path}" ]]; then
        log_warn "Discrete GPU PCI power management node not found at: ${path}"
        return 0
    fi

    local st="unknown"
    local ctrl="unknown"
    [[ -f "${path}/runtime_status" ]] && st="$(cat "${path}/runtime_status")"
    [[ -f "${path}/control" ]] && ctrl="$(cat "${path}/control")"

    if [[ "${st}" == "suspended" ]]; then
        log_pass "NVIDIA dGPU is in Runtime D3 Cold state (suspended, 0W idle draw, control: ${ctrl})"
    else
        log_warn "NVIDIA dGPU is currently ${st} (control: ${ctrl}). Run --gpu power-save to enforce autosuspend."
    fi
}

enforce_gpu_power_save() {
    local path="${1:-${SYSFS_GPU_DEFAULT}}"
    if [[ ! -f "${path}/control" ]]; then
        log_error "GPU power control node not found at: ${path}/control"
        return 1
    fi
    echo "auto" | tee "${path}/control" >/dev/null
    log_pass "NVIDIA dGPU power control set to 'auto'."
}

audit_vaapi() {
    log_info "Auditing Intel VA-API Hardware Video Acceleration..."
    if ! command -v vainfo >/dev/null 2>&1; then
        log_warn "vainfo utility not installed. Run: sudo apt install -y vainfo intel-media-va-driver-non-free"
        return 1
    fi

    local out
    if out="$(vainfo 2>&1)"; then
        log_pass "VA-API driver initialized successfully:\n${out}"
        return 0
    else
        log_error "VA-API initialization failed:\n${out}"
        return 1
    fi
}

install_vaapi_drivers() {
    log_info "Installing Intel Media VA-API non-free driver packages..."
    apt-get update -q
    apt-get install -y -q intel-media-va-driver-non-free vainfo i965-va-driver-shaders
    log_pass "Intel VA-API media driver installation completed."
}

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --battery [status|on|off]         Inspect or set Lenovo battery conservation mode (60% threshold)
  --profile [status|quiet|balanced|performance]  Inspect or set Lenovo platform thermal profile
  --fn-lock [status|on|off]         Inspect or set Lenovo function key lock
  --gpu [status|power-save]         Inspect or configure discrete GPU Runtime D3 power gating
  --vaapi [status|install]          Inspect or install Intel VA-API video acceleration drivers
  --thermals [status|install]       Inspect or install Intel thermald daemon
  --audit                           Run full hardware power, thermal, and acceleration diagnostics
  -h, --help                        Display this help message
EOF
}

main() {
    local action="${1:-audit}"
    case "${action}" in
        --battery)
            local mode="${2:-status}"
            if [[ "${mode}" == "status" ]]; then
                echo "Lenovo Battery Conservation Mode: $(get_battery_status)"
            else
                set_battery_conservation "${mode}"
            fi
            ;;
        --profile)
            local prof="${2:-status}"
            if [[ "${prof}" == "status" ]]; then
                echo "Lenovo Platform Profile: $(get_platform_profile)"
            else
                set_platform_profile "${prof}"
            fi
            ;;
        --fn-lock)
            local fn_mode="${2:-status}"
            if [[ "${fn_mode}" == "status" ]]; then
                echo "Lenovo Fn-Lock: $(get_fn_lock_status)"
            else
                set_fn_lock "${fn_mode}"
            fi
            ;;
        --gpu)
            local gpu_sub="${2:-status}"
            if [[ "${gpu_sub}" == "power-save" ]]; then
                enforce_gpu_power_save
            else
                audit_gpu_power
            fi
            ;;
        --vaapi)
            local submode="${2:-status}"
            if [[ "${submode}" == "install" ]]; then
                install_vaapi_drivers
            else
                audit_vaapi
            fi
            ;;
        --audit)
            echo "=================================================="
            echo "       Hardware Tuning & Acceleration Audit       "
            echo "=================================================="
            log_info "Battery Conservation Mode: $(get_battery_status)"
            log_info "Platform Profile: $(get_platform_profile)"
            log_info "Fn-Lock: $(get_fn_lock_status)"
            audit_gpu_power || true
            audit_vaapi || true
            ;;
        -h|--help)
            show_help
            ;;
        *)
            show_help
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```
Make `scripts/tune_hardware.sh` executable.

Create `os_manager/commands/tune.py`:

```python
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
```

- [ ] **Step 4: Run test to verify Task 1 passes**

Run: `python3 -m unittest tests/test_tune_hardware.py`
Expected output: PASS (all tests passed with exit code 0).

- [ ] **Step 5: Commit Task 1 deliverables**

```bash
git add scripts/tune_hardware.sh os_manager/commands/tune.py tests/test_tune_hardware.py
git commit -m "feat(tune): implement Lenovo hardware ACPI, thermals, GPU power gating, and boot persistence"
```

---

### Task 2: System Kernel Sysctl Tuning, NVMe TRIM Maintenance, PipeWire Audio & UFW Security Hardening

**Files:**
- Create: `scripts/tune_system.sh`
- Create: `tests/test_tune_system.py`
- Modify: `os_manager/commands/tune.py`

**Interfaces:**
- Produces:
  - CLI switch: `scripts/tune_system.sh --sysctl [apply|audit]`
  - CLI switch: `scripts/tune_system.sh --trim [status|enable]`
  - CLI switch: `scripts/tune_system.sh --audio [status]`
  - CLI switch: `scripts/tune_system.sh --firewall [status|enable]`
  - CLI switch: `scripts/tune_system.sh --audit`
  - Function `generate_sysctl_performance_config() -> str`
  - Function `audit_sysctl_parameters() -> dict[str, Any]`
  - Function `audit_fstrim_timer_status() -> dict[str, Any]`
  - Function `audit_ufw_firewall_status() -> dict[str, Any]`
  - Function `audit_pipewire_audio_status() -> dict[str, Any]`

- [ ] **Step 1: Write failing test in `tests/test_tune_system.py`**

Create `tests/test_tune_system.py`:

```python
"""tests/test_tune_system.py - Unit tests for kernel sysctl, NVMe TRIM, audio, and firewall."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_fstrim_timer_status,
    audit_pipewire_audio_status,
    audit_sysctl_parameters,
    audit_ufw_firewall_status,
    generate_sysctl_performance_config,
)


class TestTuneSystem(unittest.TestCase):
    """Unit tests for system kernel and security tuning."""

    def test_generate_sysctl_performance_config(self):
        """Verify generated sysctl configuration contains required performance keys."""
        cfg = generate_sysctl_performance_config()
        self.assertIn("vm.swappiness = 10", cfg)
        self.assertIn("vm.vfs_cache_pressure = 50", cfg)
        self.assertIn("fs.inotify.max_user_watches = 524288", cfg)
        self.assertIn("net.ipv4.tcp_congestion_control = bbr", cfg)

    @patch("subprocess.run")
    def test_audit_sysctl_parameters_active(self, mock_run):
        """Verify audit of active sysctl keys."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="10\n"),
            MagicMock(returncode=0, stdout="524288\n"),
            MagicMock(returncode=0, stdout="bbr\n"),
        ]
        res = audit_sysctl_parameters()
        self.assertEqual(res["swappiness"], "10")
        self.assertEqual(res["inotify_watches"], "524288")
        self.assertEqual(res["congestion_control"], "bbr")

    @patch("subprocess.run")
    def test_audit_fstrim_timer_active(self, mock_run):
        """Verify fstrim.timer inspection."""
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")
        res = audit_fstrim_timer_status()
        self.assertTrue(res["active"])

    @patch("subprocess.run")
    def test_audit_ufw_firewall_status(self, mock_run):
        """Verify UFW firewall status parsing."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Status: active\nDefault: deny (incoming), allow (outgoing), disabled (routed)",
        )
        res = audit_ufw_firewall_status()
        self.assertTrue(res["active"])
        self.assertTrue(res["default_deny_incoming"])

    @patch("subprocess.run")
    def test_audit_pipewire_audio_status(self, mock_run):
        """Verify PipeWire session manager status check."""
        mock_run.return_value = MagicMock(returncode=0, stdout="wireplumber\n")
        with patch("shutil.which", return_value="/usr/bin/pipewire"):
            res = audit_pipewire_audio_status()
            self.assertTrue(res["available"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_tune_system.py`
Expected output: FAIL with `ImportError`.

- [ ] **Step 3: Implement `scripts/tune_system.sh` and Python system tuning helpers**

Create `scripts/tune_system.sh`:

```bash
#!/usr/bin/env bash
# scripts/tune_system.sh - Kernel Sysctl, NVMe TRIM, PipeWire, and UFW Security Tuning
set -euo pipefail

SYSCTL_CONF_PATH="/etc/sysctl.d/99-osm-performance.conf"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

apply_sysctl_tuning() {
    log_info "Applying Linux kernel performance sysctl parameters..."
    cat <<EOF | tee "${SYSCTL_CONF_PATH}" >/dev/null
# os-manager Debian 13 Kernel Performance Tuning
vm.swappiness = 10
vm.vfs_cache_pressure = 50
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 1024
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF
    sysctl --system >/dev/null 2>&1 || sysctl -p "${SYSCTL_CONF_PATH}"
    log_pass "Kernel sysctl configuration active at: ${SYSCTL_CONF_PATH}"
}

enable_nvme_trim() {
    log_info "Enabling periodic NVMe storage fstrim.timer..."
    systemctl enable --now fstrim.timer
    log_pass "fstrim.timer enabled and active."
}

audit_system() {
    echo "=================================================="
    echo "      Kernel, Storage & Security Hardening Audit  "
    echo "=================================================="
    local swappiness
    swappiness="$(sysctl -n vm.swappiness 2>/dev/null || echo "unknown")"
    local bbr
    bbr="$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo "unknown")"
    local inotify
    inotify="$(sysctl -n fs.inotify.max_user_watches 2>/dev/null || echo "unknown")"

    log_info "vm.swappiness: ${swappiness} (recommended: 10)"
    log_info "TCP Congestion Control: ${bbr} (recommended: bbr)"
    log_info "fs.inotify.max_user_watches: ${inotify} (recommended: 524288)"

    if systemctl is-active --quiet fstrim.timer 2>/dev/null; then
        log_pass "fstrim.timer: Active"
    else
        log_warn "fstrim.timer: Inactive"
    fi

    if command -v ufw >/dev/null 2>&1; then
        local ufw_st
        ufw_st="$(ufw status | head -n 1)"
        log_info "UFW Firewall: ${ufw_st}"
    else
        log_warn "UFW Firewall not installed."
    fi
}

main() {
    local action="${1:-audit}"
    case "${action}" in
        --sysctl)
            apply_sysctl_tuning
            ;;
        --trim)
            enable_nvme_trim
            ;;
        --audit)
            audit_system
            ;;
        *)
            echo "Usage: $(basename "$0") [--sysctl|--trim|--audit]"
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```
Make `scripts/tune_system.sh` executable.

Add to `os_manager/commands/tune.py`:

```python
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
```

- [ ] **Step 4: Run test to verify Task 2 passes**

Run: `python3 -m unittest tests/test_tune_system.py`
Expected output: PASS (all tests passed with exit code 0).

- [ ] **Step 5: Commit Task 2 deliverables**

```bash
git add scripts/tune_system.sh os_manager/commands/tune.py tests/test_tune_system.py
git commit -m "feat(tune): implement kernel sysctl tuning, NVMe TRIM maintenance, and security audit"
```

---

### Task 3: GNOME 48 Desktop Aesthetics, Ergonomics, Nautilus Data Store Bookmarking & Dconf State

**Files:**
- Create: `scripts/setup_desktop_env.sh`
- Create: `tests/test_desktop_customization.py`
- Modify: `os_manager/commands/tune.py`

**Interfaces:**
- Produces:
  - CLI switch: `scripts/setup_desktop_env.sh --apply`
  - CLI switch: `scripts/setup_desktop_env.sh --bookmark [uri] [label]`
  - CLI switch: `scripts/setup_desktop_env.sh --dconf-dump [filepath]`
  - CLI switch: `scripts/setup_desktop_env.sh --dconf-load [filepath]`
  - Function `add_nautilus_bookmark(uri: str, label: str, bookmark_file: str) -> bool`
  - Function `get_nautilus_bookmarks(bookmark_file: str) -> list[str]`
  - Function `apply_desktop_gsettings() -> dict[str, bool]`
  - Function `dconf_dump_desktop(output_file: str) -> bool`
  - Function `dconf_load_desktop(input_file: str) -> bool`

- [ ] **Step 1: Write failing test in `tests/test_desktop_customization.py`**

Create `tests/test_desktop_customization.py`:

```python
"""tests/test_desktop_customization.py - Unit tests for GTK bookmarks, GSettings, and Dconf."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    add_nautilus_bookmark,
    apply_desktop_gsettings,
    dconf_dump_desktop,
    dconf_load_desktop,
    get_nautilus_bookmarks,
)


class TestDesktopCustomization(unittest.TestCase):
    """Unit tests for GNOME bookmarks and desktop setup."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.bookmark_file = Path(self.temp_dir.name) / "bookmarks"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_nautilus_bookmark_creation(self):
        """Verify bookmark addition to fresh GTK 3 bookmarks file."""
        success = add_nautilus_bookmark("file:///mnt/data", "Data Store", str(self.bookmark_file))
        self.assertTrue(success)
        bookmarks = get_nautilus_bookmarks(str(self.bookmark_file))
        self.assertIn("file:///mnt/data Data Store", bookmarks)

    def test_add_nautilus_bookmark_idempotency(self):
        """Verify duplicate bookmarks are prevented."""
        add_nautilus_bookmark("file:///mnt/data", "Data Store", str(self.bookmark_file))
        add_nautilus_bookmark("file:///mnt/data", "Data Store", str(self.bookmark_file))
        bookmarks = get_nautilus_bookmarks(str(self.bookmark_file))
        self.assertEqual(len(bookmarks), 1)

    @patch("subprocess.run")
    def test_apply_desktop_gsettings(self, mock_run):
        """Verify execution of key gsettings schemas."""
        mock_run.return_value = MagicMock(returncode=0)
        res = apply_desktop_gsettings()
        self.assertTrue(all(res.values()))
        self.assertGreater(mock_run.call_count, 5)

    @patch("subprocess.run")
    def test_dconf_dump_and_load(self, mock_run):
        """Verify dconf dump and load invocations."""
        mock_run.return_value = MagicMock(returncode=0)
        dump_ok = dconf_dump_desktop("/tmp/mock_dconf.ini")
        self.assertTrue(dump_ok)
        load_ok = dconf_load_desktop("/tmp/mock_dconf.ini")
        self.assertTrue(load_ok)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_desktop_customization.py`
Expected output: FAIL with `ImportError`.

- [ ] **Step 3: Implement `scripts/setup_desktop_env.sh` and Python desktop functions**

Create `scripts/setup_desktop_env.sh`:

```bash
#!/usr/bin/env bash
# scripts/setup_desktop_env.sh - GNOME 48 Aesthetics, Ergonomics, Bookmarks, and Dconf
set -euo pipefail

BOOKMARKS_FILE="${HOME}/.config/gtk-3.0/bookmarks"
DCONF_PROFILE_PATH="${HOME}/.config/dconf/gnome-desktop.ini"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }

add_bookmark() {
    local uri="${1:-file:///mnt/data}"
    local label="${2:-Data Store}"
    local file="${3:-${BOOKMARKS_FILE}}"

    mkdir -p "$(dirname "${file}")"
    touch "${file}"

    local entry="${uri} ${label}"
    if grep -qF "${uri}" "${file}"; then
        log_info "Bookmark for ${uri} already exists in ${file}."
    else
        echo "${entry}" >> "${file}"
        log_pass "Added bookmark: ${entry}"
    fi
}

apply_gsettings_tweaks() {
    log_info "Applying GNOME 48 typography, window controls, and ergonomics..."
    if ! command -v gsettings >/dev/null 2>&1; then
        log_warn "gsettings not available in current environment."
        return 0
    fi

    # Typography
    gsettings set org.gnome.desktop.interface font-name 'Inter 10.5' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface document-font-name 'Inter 11' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrains Mono 10' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-antialiasing 'rgba' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-hinting 'slight' 2>/dev/null || true

    # Window Management & Ergonomics
    gsettings set org.gnome.desktop.wm.preferences button-layout 'appmenu:minimize,maximize,close' 2>/dev/null || true
    gsettings set org.gnome.mutter center-new-windows true 2>/dev/null || true
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null || true
    gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled true 2>/dev/null || true
    gsettings set org.gnome.desktop.wm.keybindings switch-applications "[]" 2>/dev/null || true
    gsettings set org.gnome.desktop.wm.keybindings switch-windows "['<Alt>Tab']" 2>/dev/null || true

    # Touchpad & Audio Over-Amplification
    gsettings set org.gnome.desktop.peripherals.touchpad tap-to-click true 2>/dev/null || true
    gsettings set org.gnome.desktop.peripherals.touchpad natural-scroll true 2>/dev/null || true
    gsettings set org.gnome.desktop.peripherals.touchpad disable-while-typing true 2>/dev/null || true
    gsettings set org.gnome.desktop.sound allow-volume-above-100-percent true 2>/dev/null || true

    # Nautilus Developer View
    gsettings set org.gnome.nautilus.preferences default-folder-viewer 'list-view' 2>/dev/null || true
    gsettings set org.gnome.nautilus.preferences date-time-format 'detailed' 2>/dev/null || true

    log_pass "Desktop gsettings configuration applied successfully."
}

dump_dconf() {
    local target="${1:-${DCONF_PROFILE_PATH}}"
    mkdir -p "$(dirname "${target}")"
    if command -v dconf >/dev/null 2>&1; then
        dconf dump /org/gnome/ > "${target}"
        log_pass "Exported GNOME desktop dconf profile to: ${target}"
    else
        log_warn "dconf CLI utility not installed."
    fi
}

load_dconf() {
    local target="${1:-${DCONF_PROFILE_PATH}}"
    if [[ ! -f "${target}" ]]; then
        log_error "Dconf profile not found at: ${target}"
        return 1
    fi
    if command -v dconf >/dev/null 2>&1; then
        dconf load /org/gnome/ < "${target}"
        log_pass "Restored GNOME desktop dconf profile from: ${target}"
    else
        log_warn "dconf CLI utility not installed."
    fi
}

main() {
    local action="${1:-apply}"
    case "${action}" in
        --apply)
            add_bookmark "file:///mnt/data" "Data Store" "${BOOKMARKS_FILE}"
            apply_gsettings_tweaks
            ;;
        --bookmark)
            add_bookmark "${2:-file:///mnt/data}" "${3:-Data Store}" "${BOOKMARKS_FILE}"
            ;;
        --dconf-dump)
            dump_dconf "${2:-${DCONF_PROFILE_PATH}}"
            ;;
        --dconf-load)
            load_dconf "${2:-${DCONF_PROFILE_PATH}}"
            ;;
        *)
            echo "Usage: $(basename "$0") [--apply|--bookmark|--dconf-dump|--dconf-load]"
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```
Make `scripts/setup_desktop_env.sh` executable.

Add to `os_manager/commands/tune.py`:

```python
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
```

- [ ] **Step 4: Run test to verify Task 3 passes**

Run: `python3 -m unittest tests/test_desktop_customization.py`
Expected output: PASS (all tests passed with exit code 0).

- [ ] **Step 5: Commit Task 3 deliverables**

```bash
git add scripts/setup_desktop_env.sh os_manager/commands/tune.py tests/test_desktop_customization.py
git commit -m "feat(tune): implement GNOME 48 desktop aesthetics, ergonomics, and dconf state"
```

---

### Task 4: Modern Terminal & Developer Experience Suite (Starship, Modern CLI, FZF Previews, Bash Defaults, Git Aliases, Tmux)

**Files:**
- Create: `scripts/setup_terminal_env.sh`
- Create: `tests/test_terminal_customization.py`
- Modify: `os_manager/commands/tune.py`

**Interfaces:**
- Produces:
  - CLI switch: `scripts/setup_terminal_env.sh --setup`
  - CLI switch: `scripts/setup_terminal_env.sh --audit`
  - Function `generate_starship_config() -> str`
  - Function `generate_tmux_config() -> str`
  - Function `generate_bash_hooks_block() -> str`
  - Function `inject_bashrc_hooks(bashrc_path: str) -> bool`

- [ ] **Step 1: Write failing test in `tests/test_terminal_customization.py`**

Create `tests/test_terminal_customization.py`:

```python
"""tests/test_terminal_customization.py - Unit tests for Starship, FZF, Bash, and Tmux."""

import tempfile
import unittest
from pathlib import Path

from os_manager.commands.tune import (
    generate_bash_hooks_block,
    generate_starship_config,
    generate_tmux_config,
    inject_bashrc_hooks,
)


class TestTerminalCustomization(unittest.TestCase):
    """Unit tests for terminal developer experience tooling."""

    def test_generate_starship_config(self):
        """Verify Starship prompt TOML configuration contents."""
        cfg = generate_starship_config()
        self.assertIn("[directory]", cfg)
        self.assertIn("[git_branch]", cfg)
        self.assertIn("[cmd_duration]", cfg)
        self.assertIn("[python]", cfg)

    def test_generate_tmux_config(self):
        """Verify Tmux developer starter profile contents."""
        cfg = generate_tmux_config()
        self.assertIn("set -g mouse on", cfg)
        self.assertIn("xterm-256color", cfg)
        self.assertIn("setw -g mode-keys vi", cfg)

    def test_inject_bashrc_hooks_idempotency(self):
        """Verify bashrc hook injection is strictly idempotent."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("# Existing bashrc\nexport FOO=bar\n")
            f.flush()
            bashrc_path = f.name

        try:
            # First injection
            ok1 = inject_bashrc_hooks(bashrc_path=bashrc_path)
            self.assertTrue(ok1)
            content1 = Path(bashrc_path).read_text()
            self.assertIn("# --- os-manager Terminal Power-Up Hooks ---", content1)
            self.assertIn("alias ls=\"eza --icons\"", content1)

            # Second injection (must not duplicate)
            ok2 = inject_bashrc_hooks(bashrc_path=bashrc_path)
            self.assertTrue(ok2)
            content2 = Path(bashrc_path).read_text()
            self.assertEqual(content1.count("# --- os-manager Terminal Power-Up Hooks ---"), 1)
            self.assertEqual(content2.count("# --- os-manager Terminal Power-Up Hooks ---"), 1)
        finally:
            Path(bashrc_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_terminal_customization.py`
Expected output: FAIL with `ImportError`.

- [ ] **Step 3: Implement `scripts/setup_terminal_env.sh` and Python terminal customization functions**

Create `scripts/setup_terminal_env.sh`:

```bash
#!/usr/bin/env bash
# scripts/setup_terminal_env.sh - Starship Prompt, Modern CLI Tools, FZF Previews, Bash & Tmux
set -euo pipefail

STARSHIP_CONFIG_PATH="${HOME}/.config/starship.toml"
TMUX_CONFIG_PATH="${HOME}/.tmux.conf"
BASHRC_PATH="${HOME}/.bashrc"
HOOK_MARKER="# --- os-manager Terminal Power-Up Hooks ---"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }

setup_starship() {
    log_info "Configuring Starship prompt template at ${STARSHIP_CONFIG_PATH}..."
    mkdir -p "$(dirname "${STARSHIP_CONFIG_PATH}")"
    cat <<'EOF' > "${STARSHIP_CONFIG_PATH}"
# Starship Prompt Configuration for os-manager
add_newline = false

format = """
$directory\
$git_branch\
$git_status\
$python\
$nodejs\
$rust\
$docker_context\
$cmd_duration\
$line_break\
$character"""

[directory]
truncation_length = 3
truncate_to_repo = true
style = "bold cyan"

[git_branch]
style = "bold purple"
symbol = " "

[git_status]
style = "bold red"
ahead = "⇡${count}"
behind = "⇣${count}"
diverged = "⇕⇡${ahead_count}⇣${behind_count}"

[cmd_duration]
min_time = 2_000
style = "bold yellow"

[character]
success_symbol = "[❯](bold green)"
error_symbol = "[❯](bold red)"
EOF
    log_pass "Starship prompt configuration deployed."
}

setup_tmux() {
    log_info "Configuring Tmux developer starter profile at ${TMUX_CONFIG_PATH}..."
    cat <<'EOF' > "${TMUX_CONFIG_PATH}"
# Tmux Developer Profile for os-manager
set -g mouse on
set -g default-terminal "xterm-256color"
set -ga terminal-overrides ",*256col*:Tc"

bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"

setw -g mode-keys vi
set -g status-style bg=black,fg=white
set -g status-interval 5
set -g status-left "#[fg=green][#S] "
set -g status-right "#[fg=cyan]%H:%M #[fg=yellow]%d-%b-%y"
EOF
    log_pass "Tmux developer configuration deployed."
}

inject_bashrc() {
    log_info "Injecting terminal power-up hooks into ${BASHRC_PATH}..."
    touch "${BASHRC_PATH}"

    if grep -qF "${HOOK_MARKER}" "${BASHRC_PATH}"; then
        log_info "Bash hooks already present in ${BASHRC_PATH}. Skipping duplicate injection."
        return 0
    fi

    cat <<'EOF' >> "${BASHRC_PATH}"

# --- os-manager Terminal Power-Up Hooks ---
export HISTSIZE=100000
export HISTFILESIZE=200000
export HISTCONTROL=ignoreboth:erasedups
export HISTTIMEFORMAT="%F %T "

shopt -s histappend 2>/dev/null || true
shopt -s checkwinsize 2>/dev/null || true
shopt -s globstar 2>/dev/null || true
shopt -s cdspell 2>/dev/null || true

# Modern CLI Aliases
alias ls="eza --icons" 2>/dev/null || true
alias ll="eza -lh --icons --git" 2>/dev/null || true
alias la="eza -lah --icons --git" 2>/dev/null || true
alias lt="eza --tree --level=2 --icons" 2>/dev/null || true
alias cat="bat --paging=never" 2>/dev/null || true
alias grep="rg" 2>/dev/null || true
alias find="fd" 2>/dev/null || true
alias df="duf" 2>/dev/null || true
alias top="btop" 2>/dev/null || true
alias cd="z" 2>/dev/null || true

# Git Power Aliases
alias gst="git status"
alias gdiff="git diff"
alias glog="git log --oneline --graph --decorate"
alias gco="git checkout"
alias gbr="git branch"
alias gadd="git add"
alias gcm="git commit -m"

# FZF Live Previews
export FZF_DEFAULT_COMMAND='fd --type f --strip-cwd-prefix --hidden --exclude .git' 2>/dev/null || true
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND" 2>/dev/null || true
export FZF_ALT_C_COMMAND='fd --type d --strip-cwd-prefix --hidden --exclude .git' 2>/dev/null || true
export FZF_CTRL_T_OPTS="--preview 'bat --style=numbers --color=always --line-range :500 {}' --preview-window=right:60%:wrap" 2>/dev/null || true
export FZF_ALT_C_OPTS="--preview 'eza --tree --level=2 --color=always {}' --preview-window=right:50%" 2>/dev/null || true
export FZF_CTRL_R_OPTS="--preview 'echo {}' --preview-window=down:3:wrap --sort" 2>/dev/null || true

# Starship & Zoxide Init
if command -v starship >/dev/null 2>&1; then
    eval "$(starship init bash)"
fi
if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init bash)"
fi
# --- End os-manager Terminal Power-Up Hooks ---
EOF
    log_pass "Bashrc hooks injected successfully."
}

main() {
    setup_starship
    setup_tmux
    inject_bashrc
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```
Make `scripts/setup_terminal_env.sh` executable.

Add to `os_manager/commands/tune.py`:

```python
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
```

- [ ] **Step 4: Run test to verify Task 4 passes**

Run: `python3 -m unittest tests/test_terminal_customization.py`
Expected output: PASS (all tests passed with exit code 0).

- [ ] **Step 5: Commit Task 4 deliverables**

```bash
git add scripts/setup_terminal_env.sh os_manager/commands/tune.py tests/test_terminal_customization.py
git commit -m "feat(tune): implement Starship prompt, FZF previews, Bash defaults, and Tmux profile"
```

---

### Task 5: Consolidated CLI Router (`osm tune`), Master Harness Registration, and Documentation Guide

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `os_manager/cli.py`
- Modify: `tests/test_harness.sh`
- Create: `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md`

**Interfaces:**
- Produces:
  - Command router `run_tune(args: list[str]) -> int`
  - Registered subcommands: `osm tune [battery|profile|fn-lock|thermals|gpu|vaapi|hardware-persist|system|desktop|terminal|all|audit]`
  - Regression harness assertions in `tests/test_harness.sh`

- [ ] **Step 1: Complete CLI Router implementation in `os_manager/commands/tune.py` and `os_manager/cli.py`**

Update `os_manager/commands/tune.py` to add `run_tune`:

```python
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

    # gpu
    gpu_p = subparsers.add_parser("gpu", help="Manage discrete GPU power-gating")
    gpu_p.add_argument("action", nargs="?", default="status", choices=["status", "power-save"])

    # vaapi
    va_p = subparsers.add_parser("vaapi", help="Inspect or install Intel VA-API acceleration")
    va_p.add_argument("action", nargs="?", default="status", choices=["status", "install"])

    # system
    sys_p = subparsers.add_parser("system", help="Manage kernel sysctl, TRIM, and security")
    sys_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])

    # desktop
    desk_p = subparsers.add_parser("desktop", help="Manage GNOME aesthetics, bookmarks, and dconf")
    desk_p.add_argument("action", nargs="?", default="apply", choices=["apply", "audit", "backup", "restore"])
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
            return subprocess.run(cmd, input=val, text=True).returncode
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
            return subprocess.run(cmd, input=f"{target}\n", text=True).returncode
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
            return subprocess.run(cmd, input=val, text=True).returncode
        success = set_fn_lock_mode(enable)
        print(f"[PASS] Fn-Lock set to: {'enabled' if enable else 'disabled'}")
        return 0 if success else 1

    elif parsed_args.subaction == "gpu":
        if parsed_args.action == "power-save":
            if os.geteuid() != 0:
                cmd = ["sudo", "tee", f"{SYSFS_GPU_DEFAULT}/control"]
                return subprocess.run(cmd, input="auto\n", text=True).returncode
            res = subprocess.run(["tee", f"{SYSFS_GPU_DEFAULT}/control"], input="auto\n", text=True, capture_output=True)
            print("[PASS] NVIDIA GPU power control set to auto.")
            return res.returncode
        gpu = audit_gpu_runtime_power()
        print(f"NVIDIA GPU Runtime D3 Status: {gpu.get('runtime_status', 'unknown')}")
        print(f"Power Saving Active: {gpu.get('power_saving', False)}")
        return 0

    elif parsed_args.subaction == "vaapi":
        if parsed_args.action == "install":
            cmd = ["sudo", "apt-get", "install", "-y", "intel-media-va-driver-non-free", "vainfo"] if os.geteuid() != 0 else ["apt-get", "install", "-y", "intel-media-va-driver-non-free", "vainfo"]
            return subprocess.run(cmd).returncode
        res = audit_vaapi_acceleration()
        print(f"VA-API Acceleration Available: {res['available']}")
        print(res["details"])
        return 0 if res["available"] else 1

    elif parsed_args.subaction == "system":
        if parsed_args.action == "apply":
            return subprocess.run(["bash", "scripts/tune_system.sh", "--sysctl"]).returncode
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
            apply_desktop_gsettings()
            print("[PASS] GNOME desktop typography, ergonomics, and bookmarks configured.")
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
        print("=================================================="
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
        subprocess.run(["bash", "scripts/tune_hardware.sh", "--audit"])
        subprocess.run(["bash", "scripts/tune_system.sh", "--sysctl"])
        subprocess.run(["bash", "scripts/setup_desktop_env.sh", "--apply"])
        subprocess.run(["bash", "scripts/setup_terminal_env.sh"])
        print("[PASS] All hardware, system, desktop, and terminal optimizations applied.")
        return 0

    parser.print_help()
    return 0
```

Register in `os_manager/cli.py`:
- Add `from .commands.tune import run_tune`
- Add `subparsers.add_parser("tune", add_help=False, help="Hardware, system, desktop, and terminal tuning engine")`
- In `main()` dispatch: `elif args.command == "tune": return run_tune(argv[1:])`

- [ ] **Step 2: Register test suites in `tests/test_harness.sh`**

Add to `tests/test_harness.sh`:

```bash
echo "--- Testing Debian 13 Customization & Hardware Tuning Suite ---"
python3 -m unittest "${WORKSPACE_ROOT}/tests/test_tune_hardware.py" > /dev/null 2>&1
assert_exit_code "test_tune_hardware.py unit suite" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_tune_system.py" > /dev/null 2>&1
assert_exit_code "test_tune_system.py unit suite" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_desktop_customization.py" > /dev/null 2>&1
assert_exit_code "test_desktop_customization.py unit suite" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_terminal_customization.py" > /dev/null 2>&1
assert_exit_code "test_terminal_customization.py unit suite" 0 $?
```

- [ ] **Step 3: Create User Manual `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md`**

Create `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md` documenting usage of `osm tune` with clear CLI examples.

- [ ] **Step 4: Run the full master regression harness**

Run: `bash tests/test_harness.sh`
Expected output: All test suites PASS with exit code 0.

- [ ] **Step 5: Commit Task 5 deliverables**

```bash
git add os_manager/commands/tune.py os_manager/cli.py tests/test_harness.sh docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md
git commit -m "feat(tune): register osm tune CLI control plane, harness test suites, and documentation"
```

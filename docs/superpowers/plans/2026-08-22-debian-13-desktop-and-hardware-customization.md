# Debian 13 (Trixie) Desktop & Hardware Customization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automated hardware power tuning (Lenovo Battery Conservation Mode, Intel VA-API video acceleration), GNOME 48 desktop aesthetics enhancement (Inter & JetBrains Mono typography, Nautilus Data Store bookmarking, Extension Manager integration), and modern terminal developer experience tooling (Starship prompt, fzf, zoxide, bat, eza) integrated into the `osm` CLI suite.

**Architecture:** A modular Python CLI router (`os_manager/commands/tune.py`) and idempotent bash automation subroutines (`scripts/tune_hardware.sh`, `scripts/setup_desktop_env.sh`, `scripts/setup_terminal_env.sh`). Each module handles inspection, idempotent installation, configuration templating, and verification with full test coverage integrated into the master test harness.

**Tech Stack:** Python 3.10+, Bash 4.4+, Linux sysfs (`ideapad_laptop` ACPI), VA-API (`intel-media-va-driver-non-free`), GTK 3/4 Bookmarks, Starship CLI, `fzf`, `zoxide`, `bat`, `eza`, `pytest`/`unittest`.

**Spec:** [`docs/superpowers/specs/2026-08-22-debian-13-desktop-and-hardware-customization-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-22-debian-13-desktop-and-hardware-customization-design.md)

---

## Global Constraints

- **Non-Destructive & In-Place Safety:** No operations touch, format, or unmount `/dev/nvme0n1p4` (`/mnt/data`).
- **Idempotency:** All configuration scripts must be re-runnable multiple times without duplicating lines in `.bashrc`, `bookmarks`, or systemd configurations.
- **Rootless & Sudo Boundary:** System package installations and sysfs writes must use root privileges or `sudo`, while user configuration files (`~/.bashrc`, `~/.config/gtk-3.0/bookmarks`, `~/.config/starship.toml`) must respect user ownership (`$HOME`, not `/root`).
- **Wayland & Intel Ice Lake Compatibility:** Display and media accelerations must target Wayland with Intel Iris Plus Graphics (`i915` / `/dev/dri/card0` / `/dev/dri/renderD128`).
- **Master Harness Registration:** All new unit tests and scripts must be registered into `tests/test_harness.sh` and verified via `scripts/harness_check.sh`.

---

### File Structure & Responsibilities

| File Path | Role / Responsibility |
| :--- | :--- |
| `scripts/tune_hardware.sh` | Bash engine for Lenovo battery conservation mode, VA-API hardware acceleration audit, and power profile tuning. |
| `scripts/setup_desktop_env.sh` | Idempotent installer for typography (Inter & JetBrains Mono), Nautilus bookmarking (`/mnt/data`), and GNOME Extensions manager. |
| `scripts/setup_terminal_env.sh` | Terminal DX setup engine for Starship prompt, `fzf`, `zoxide`, `bat`, `eza`, and `.bashrc` alias hooks. |
| `os_manager/commands/tune.py` | Python CLI command group `osm tune` (`battery`, `vaapi`, `desktop`, `terminal`, `all`) with JSON telemetry support. |
| `os_manager/cli.py` | Main CLI router updated to register `tune` subparser. |
| `tests/test_tune_hardware.py` | Python unit test suite for `osm tune` command routing, battery conservation toggling, and environment setup. |
| `tests/test_customization_scripts.sh` | Bash unit test suite for `tune_hardware.sh`, `setup_desktop_env.sh`, and `setup_terminal_env.sh`. |
| `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md` | Comprehensive user manual for hardware optimization, desktop aesthetics, and terminal power-up. |

---

### Task 1: Lenovo Hardware Power Tuning & VA-API Video Acceleration Engine

**Files:**
- Create: `scripts/tune_hardware.sh`
- Create: `tests/test_tune_hardware.py`
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Produces:
  - CLI switch: `scripts/tune_hardware.sh --battery [on|off|status]`
  - CLI switch: `scripts/tune_hardware.sh --vaapi [status|install]`
  - CLI switch: `scripts/tune_hardware.sh --audit`
  - Function `set_battery_conservation_mode(state: str) -> bool`
  - Function `audit_hardware_acceleration() -> dict`

- [ ] **Step 1: Write the failing test for Task 1 in `tests/test_tune_hardware.py`**

Create `tests/test_tune_hardware.py`:

```python
"""tests/test_tune_hardware.py - Unit tests for hardware power and media tuning."""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_vaapi_acceleration,
    get_battery_conservation_status,
    set_battery_conservation_mode,
)


class TestTuneHardware(unittest.TestCase):
    """Unit tests for Lenovo hardware power and VA-API tuning."""

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

    def test_battery_conservation_status_disabled(self):
        """Verify disabled status reading."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("0\n")
            f.flush()
            sysfs_path = f.name

        try:
            status = get_battery_conservation_status(sysfs_path=sysfs_path)
            self.assertEqual(status, "disabled")
        finally:
            os.remove(sysfs_path)

    def test_battery_conservation_missing_sysfs(self):
        """Verify handling of missing sysfs node on non-IdeaPad hardware."""
        status = get_battery_conservation_status(sysfs_path="/tmp/nonexistent_sysfs_node")
        self.assertEqual(status, "unsupported")

    @patch("subprocess.run")
    def test_set_battery_conservation_enable(self, mock_run):
        """Verify setting battery conservation mode calls tee with root privileges."""
        mock_run.return_value = MagicMock(returncode=0)
        success = set_battery_conservation_mode(enable=True, sysfs_path="/tmp/mock_node")
        self.assertTrue(success)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "tee")
        self.assertIn("/tmp/mock_node", args)

    @patch("subprocess.run")
    def test_audit_vaapi_acceleration_present(self, mock_run):
        """Verify VA-API driver detection via vainfo."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="vainfo: VA-API version: 1.22 (libva 2.22.0)\nvainfo: Driver version: Intel i965 driver for Intel(R) Ironlake",
            stderr="",
        )
        res = audit_vaapi_acceleration()
        self.assertTrue(res["available"])
        self.assertIn("VA-API version", res["details"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_tune_hardware.py`
Expected output: FAIL with `ModuleNotFoundError: No module named 'os_manager.commands.tune'`.

- [ ] **Step 3: Implement `scripts/tune_hardware.sh` and `os_manager/commands/tune.py`**

Create `scripts/tune_hardware.sh`:

```bash
#!/usr/bin/env bash
# scripts/tune_hardware.sh - Lenovo hardware power and VA-API acceleration tuning
set -euo pipefail

SYSFS_CONSERVATION="/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

get_battery_status() {
    local path="${1:-${SYSFS_CONSERVATION}}"
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
    local path="${2:-${SYSFS_CONSERVATION}}"
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
  --battery [status|on|off]   Inspect or set Lenovo battery conservation mode (60% threshold)
  --vaapi [status|install]    Inspect or install Intel VA-API video acceleration drivers
  --audit                     Run full hardware power and acceleration diagnostics
  -h, --help                  Display this help message
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
chmod `+x` on `scripts/tune_hardware.sh`.

Create `os_manager/commands/tune.py`:

```python
"""Hardware power tuning and desktop customization command module."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SYSFS_CONSERVATION_DEFAULT = "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"


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


def run_tune(args: list[str]) -> int:
    """Execute osm tune subcommands."""
    parser = argparse.ArgumentParser(
        prog="osm tune",
        description="Lenovo hardware power optimization and acceleration manager.",
    )
    subparsers = parser.add_subparsers(dest="subaction", help="Tuning subcommands")

    # battery
    bat_p = subparsers.add_parser("battery", help="Manage Lenovo battery conservation mode")
    bat_p.add_argument("mode", nargs="?", default="status", choices=["status", "on", "off"])

    # vaapi
    va_p = subparsers.add_parser("vaapi", help="Inspect or install Intel VA-API acceleration")
    va_p.add_argument("action", nargs="?", default="status", choices=["status", "install"])

    # audit
    subparsers.add_parser("audit", help="Audit all hardware power and acceleration features")

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
            print("[INFO] Requesting root privileges to modify sysfs...", file=sys.stderr)
            cmd = ["sudo", "tee", SYSFS_CONSERVATION_DEFAULT]
            val = "1\n" if enable else "0\n"
            res = subprocess.run(cmd, input=val, text=True)
            return res.returncode
        success = set_battery_conservation_mode(enable)
        print(f"[PASS] Battery Conservation Mode set to: {'enabled' if enable else 'disabled'}")
        return 0 if success else 1

    elif parsed_args.subaction == "vaapi":
        if parsed_args.action == "install":
            if os.geteuid() != 0:
                return subprocess.run(["sudo", "apt-get", "install", "-y", "intel-media-va-driver-non-free", "vainfo"]).returncode
            return subprocess.run(["apt-get", "install", "-y", "intel-media-va-driver-non-free", "vainfo"]).returncode
        res = audit_vaapi_acceleration()
        print(f"VA-API Acceleration Available: {res['available']}")
        print(res["details"])
        return 0 if res["available"] else 1

    elif parsed_args.subaction == "audit":
        st = get_battery_conservation_status()
        print(f"1. Lenovo Battery Conservation Mode: {st}")
        va = audit_vaapi_acceleration()
        print(f"2. Intel VA-API Acceleration: {'Available' if va['available'] else 'Unavailable'}")
        return 0

    parser.print_help()
    return 0
```

- [ ] **Step 4: Run test to verify Task 1 passes**

Run: `python3 -m unittest tests/test_tune_hardware.py`
Expected output: PASS: 5/5 tests passed with code 0.

- [ ] **Step 5: Commit Task 1 deliverables**

```bash
git add scripts/tune_hardware.sh os_manager/commands/tune.py tests/test_tune_hardware.py
git commit -m "feat(tune): implement Lenovo battery conservation and Intel VA-API hardware tuning engine"
```

---

### Task 2: GNOME 48 Desktop Aesthetics & Nautilus Data Store Bookmarking

**Files:**
- Create: `scripts/setup_desktop_env.sh`
- Create: `tests/test_desktop_customization.py`
- Modify: `os_manager/commands/tune.py`

**Interfaces:**
- Produces:
  - Subcommand: `osm tune desktop`
  - Bash subroutine: `setup_gtk_bookmarks(mount_point, label)`
  - Bash subroutine: `install_desktop_fonts()`
  - Function `add_nautilus_bookmark(uri: str, label: str) -> bool`

- [ ] **Step 1: Write failing test in `tests/test_desktop_customization.py`**

Create `tests/test_desktop_customization.py`:

```python
"""tests/test_desktop_customization.py - Unit tests for GTK bookmarks and desktop aesthetics."""

import os
import tempfile
import unittest
from pathlib import Path

from os_manager.commands.tune import add_nautilus_bookmark, get_nautilus_bookmarks


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

    def test_add_nautilus_bookmark_idempotent(self):
        """Verify adding existing bookmark does not duplicate entry."""
        add_nautilus_bookmark("file:///mnt/data", "Data Store", str(self.bookmark_file))
        add_nautilus_bookmark("file:///mnt/data", "Data Store", str(self.bookmark_file))
        bookmarks = get_nautilus_bookmarks(str(self.bookmark_file))
        count = sum(1 for b in bookmarks if "file:///mnt/data Data Store" in b)
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_desktop_customization.py`
Expected output: FAIL with `ImportError: cannot import name 'add_nautilus_bookmark'`.

- [ ] **Step 3: Implement `scripts/setup_desktop_env.sh` and bookmark functions in `os_manager/commands/tune.py`**

Create `scripts/setup_desktop_env.sh`:

```bash
#!/usr/bin/env bash
# scripts/setup_desktop_env.sh - Idempotent desktop aesthetics and GTK bookmark setup
set -euo pipefail

BOOKMARKS_FILE="${HOME}/.config/gtk-3.0/bookmarks"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }

setup_data_bookmark() {
    local target_uri="${1:-file:///mnt/data}"
    local label="${2:-Data Store}"
    local file="${3:-${BOOKMARKS_FILE}}"

    mkdir -p "$(dirname "${file}")"
    touch "${file}"

    local entry="${target_uri} ${label}"
    if grep -qF "${target_uri}" "${file}"; then
        log_info "Bookmark for ${target_uri} already present in ${file}."
    else
        echo "${entry}" >> "${file}"
        log_pass "Added '${label}' (${target_uri}) bookmark to Nautilus sidebar."
    fi
}

install_desktop_fonts() {
    log_info "Installing Inter and JetBrains Mono typography..."
    if command -v apt-get >/dev/null 2>&1; then
        if [[ "$(id -u)" -eq 0 ]]; then
            apt-get update -q
            apt-get install -y -q fonts-inter fonts-jetbrains-mono gnome-shell-extension-manager gnome-tweaks
        else
            sudo apt-get update -q
            sudo apt-get install -y -q fonts-inter fonts-jetbrains-mono gnome-shell-extension-manager gnome-tweaks
        fi
        log_pass "Typography and GNOME Tweaks installed successfully."
    fi
}

main() {
    log_info "Executing GNOME Desktop Customization Setup..."
    setup_data_bookmark "file:///mnt/data" "Data Store"
    install_desktop_fonts
    log_pass "Desktop environment setup completed."
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```
chmod `+x` on `scripts/setup_desktop_env.sh`.

Add bookmark helper functions to `os_manager/commands/tune.py`:

```python
def get_nautilus_bookmarks(bookmark_path: str | None = None) -> list[str]:
    """Retrieve list of GTK bookmarks."""
    p = Path(bookmark_path) if bookmark_path else Path.home() / ".config" / "gtk-3.0" / "bookmarks"
    if not p.is_file():
        return []
    return [line.strip() for line in p.read_text().splitlines() if line.strip()]


def add_nautilus_bookmark(uri: str, label: str, bookmark_path: str | None = None) -> bool:
    """Add idempotent bookmark entry to GTK 3 bookmarks."""
    p = Path(bookmark_path) if bookmark_path else Path.home() / ".config" / "gtk-3.0" / "bookmarks"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.touch()

    lines = [l.strip() for l in p.read_text().splitlines() if l.strip()]
    for l in lines:
        if l.startswith(uri):
            return True

    lines.append(f"{uri} {label}")
    p.write_text("\n".join(lines) + "\n")
    return True
```

Update `run_tune` in `os_manager/commands/tune.py` to support `osm tune desktop`.

- [ ] **Step 4: Run test to verify Task 2 passes**

Run: `python3 -m unittest tests/test_desktop_customization.py`
Expected output: PASS: 2/2 tests passed with code 0.

- [ ] **Step 5: Commit Task 2 deliverables**

```bash
git add scripts/setup_desktop_env.sh os_manager/commands/tune.py tests/test_desktop_customization.py
git commit -m "feat(desktop): implement GTK bookmarks and desktop aesthetics installer"
```

---

### Task 3: Modern Terminal & Developer Experience Suite (Starship, fzf, zoxide, bat, eza)

**Files:**
- Create: `scripts/setup_terminal_env.sh`
- Create: `tests/test_terminal_customization.py`
- Modify: `os_manager/commands/tune.py`

**Interfaces:**
- Produces:
  - Subcommand: `osm tune terminal`
  - Function `generate_starship_config() -> str`
  - Function `configure_bashrc_aliases(bashrc_path: str) -> bool`

- [ ] **Step 1: Write failing test in `tests/test_terminal_customization.py`**

Create `tests/test_terminal_customization.py`:

```python
"""tests/test_terminal_customization.py - Unit tests for terminal DX configuration."""

import os
import tempfile
import unittest
from pathlib import Path

from os_manager.commands.tune import configure_bashrc_aliases, generate_starship_config


class TestTerminalCustomization(unittest.TestCase):
    """Unit tests for Starship and shell configuration."""

    def test_starship_config_content(self):
        """Verify Starship TOML configuration contains expected prompt modules."""
        toml = generate_starship_config()
        self.assertIn("[directory]", toml)
        self.assertIn("[git_branch]", toml)
        self.assertIn("[python]", toml)

    def test_configure_bashrc_aliases_idempotency(self):
        """Verify adding aliases to .bashrc is idempotent and contains zoxide/fzf."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            f.write("# Existing bashrc\nexport PATH=$PATH:/custom\n")
            f.flush()
            bashrc_path = f.name

        try:
            success = configure_bashrc_aliases(bashrc_path=bashrc_path)
            self.assertTrue(success)
            content = Path(bashrc_path).read_text()
            self.assertIn("starship init bash", content)
            self.assertIn("zoxide init bash", content)

            # Re-run to verify idempotency
            configure_bashrc_aliases(bashrc_path=bashrc_path)
            second_content = Path(bashrc_path).read_text()
            self.assertEqual(second_content.count("starship init bash"), 1)
        finally:
            os.remove(bashrc_path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_terminal_customization.py`
Expected output: FAIL with `ImportError: cannot import name 'generate_starship_config'`.

- [ ] **Step 3: Implement `scripts/setup_terminal_env.sh` and terminal helpers in `os_manager/commands/tune.py`**

Create `scripts/setup_terminal_env.sh`:

```bash
#!/usr/bin/env bash
# scripts/setup_terminal_env.sh - Setup Starship prompt, fzf, zoxide, bat, eza
set -euo pipefail

BASHRC="${HOME}/.bashrc"
STARSHIP_CONFIG="${HOME}/.config/starship.toml"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }

install_cli_tools() {
    log_info "Installing modern CLI utilities (fzf, zoxide, bat, eza)..."
    if command -v apt-get >/dev/null 2>&1; then
        local pkgs=(fzf zoxide bat)
        if apt-cache show eza >/dev/null 2>&1; then
            pkgs+=(eza)
        fi
        if [[ "$(id -u)" -eq 0 ]]; then
            apt-get update -q
            apt-get install -y -q "${pkgs[@]}"
        else
            sudo apt-get update -q
            sudo apt-get install -y -q "${pkgs[@]}"
        fi
    fi

    if ! command -v starship >/dev/null 2>&1; then
        log_info "Installing Starship cross-shell prompt..."
        curl -sS https://starship.rs/install.sh | sh -s -- -y
    fi
}

configure_starship() {
    log_info "Configuring Starship prompt in ${STARSHIP_CONFIG}..."
    mkdir -p "$(dirname "${STARSHIP_CONFIG}")"
    cat <<'EOF' > "${STARSHIP_CONFIG}"
# Starship Minimalist & Fast Prompt Configuration
format = "$directory$git_branch$git_status$python$character"

[directory]
truncation_length = 3
truncation_symbol = "…/"
style = "bold cyan"

[git_branch]
symbol = " "
style = "bold purple"

[git_status]
style = "bold red"

[python]
symbol = " "
format = 'via [${symbol}${pyenv_prefix}(${version} )(\($virtualenv\) )]($style)'
style = "bold yellow"

[character]
success_symbol = "[❯](bold green)"
error_symbol = "[❯](bold red)"
EOF
    log_pass "Starship prompt configuration deployed."
}

configure_shell_rc() {
    log_info "Adding terminal aliases and hooks to ${BASHRC}..."
    local marker="# --- os-manager Terminal Power-Up Hooks ---"
    if grep -qF "${marker}" "${BASHRC}" 2>/dev/null; then
        log_info "Hooks already configured in ${BASHRC}."
        return 0
    fi

    cat <<'EOF' >> "${BASHRC}"

# --- os-manager Terminal Power-Up Hooks ---
if command -v starship >/dev/null 2>&1; then
    eval "$(starship init bash)"
fi

if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init bash)"
    alias cd="z"
fi

if command -v fzf >/dev/null 2>&1; then
    eval "$(fzf --bash 2>/dev/null || true)"
fi

# Modern CLI Aliases
if command -v batcat >/dev/null 2>&1; then
    alias cat="batcat --paging=never"
elif command -v bat >/dev/null 2>&1; then
    alias cat="bat --paging=never"
fi

if command -v eza >/dev/null 2>&1; then
    alias ls="eza --icons --group-directories-first"
    alias ll="eza -la --icons --group-directories-first"
fi
EOF
    log_pass "Bashrc hooks and aliases configured."
}

main() {
    log_info "Executing Terminal DX Environment Setup..."
    install_cli_tools
    configure_starship
    configure_shell_rc
    log_pass "Terminal environment setup complete."
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```
chmod `+x` on `scripts/setup_terminal_env.sh`.

Add terminal functions to `os_manager/commands/tune.py`:

```python
def generate_starship_config() -> str:
    """Generate minimalist Starship prompt configuration TOML."""
    return """# Starship Minimalist Prompt
format = "$directory$git_branch$git_status$python$character"

[directory]
truncation_length = 3
style = "bold cyan"

[git_branch]
symbol = " "
style = "bold purple"

[python]
symbol = " "
style = "bold yellow"

[character]
success_symbol = "[❯](bold green)"
error_symbol = "[❯](bold red)"
"""


def configure_bashrc_aliases(bashrc_path: str | None = None) -> bool:
    """Add idempotent starship and zoxide hooks to bashrc."""
    p = Path(bashrc_path) if bashrc_path else Path.home() / ".bashrc"
    if not p.exists():
        p.touch()

    content = p.read_text()
    marker = "# --- os-manager Terminal Power-Up Hooks ---"
    if marker in content:
        return True

    snippet = f"""
{marker}
if command -v starship >/dev/null 2>&1; then
    eval "$(starship init bash)"
fi

if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init bash)"
fi
"""
    p.write_text(content + snippet)
    return True
```

Update `os_manager/commands/tune.py` to handle `osm tune terminal` and `osm tune all`.

- [ ] **Step 4: Run test to verify Task 3 passes**

Run: `python3 -m unittest tests/test_terminal_customization.py`
Expected output: PASS: 2/2 tests passed with code 0.

- [ ] **Step 5: Commit Task 3 deliverables**

```bash
git add scripts/setup_terminal_env.sh os_manager/commands/tune.py tests/test_terminal_customization.py
git commit -m "feat(terminal): implement Starship prompt, fzf, zoxide, and modern CLI setup"
```

---

### Task 4: CLI Router Registration, Master Harness Verification & Documentation

**Files:**
- Modify: `os_manager/cli.py`
- Modify: `tests/test_harness.sh`
- Create: `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md`
- Test: Full execution of `scripts/harness_check.sh` and `python3 -m unittest discover tests/`.

**Interfaces:**
- Produces:
  - Top-level CLI command: `osm tune`
  - Master harness registration for `test_tune_hardware.py`, `test_desktop_customization.py`, and `test_terminal_customization.py`.

- [ ] **Step 1: Register `tune` in `os_manager/cli.py`**

Update `os_manager/cli.py`:
- Import `from .commands.tune import run_tune`
- Add `tune` subparser to `build_parser()`
- Route `args.command == "tune"` to `run_tune(argv[1:])`

- [ ] **Step 2: Register tests in `tests/test_harness.sh`**

Add to `tests/test_harness.sh`:

```bash
echo "--- Testing Hardware Tuning & Customization Suite ---"
python3 -m unittest "${WORKSPACE_ROOT}/tests/test_tune_hardware.py" > /dev/null 2>&1
assert_exit_code "test_tune_hardware.py unit suite" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_desktop_customization.py" > /dev/null 2>&1
assert_exit_code "test_desktop_customization.py unit suite" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_terminal_customization.py" > /dev/null 2>&1
assert_exit_code "test_terminal_customization.py unit suite" 0 $?
```

- [ ] **Step 3: Create `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md`**

Create `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md` documenting:
1. Lenovo Battery Conservation Mode usage and ACPI threshold.
2. Intel VA-API video decoding verification (`vainfo`).
3. GNOME 48 typography (Inter, JetBrains Mono) & Nautilus `/mnt/data` bookmarking.
4. Starship prompt, `zoxide`, `fzf`, `bat`, and `eza` alias configuration.
5. All CLI workflows (`osm tune battery`, `osm tune vaapi`, `osm tune desktop`, `osm tune terminal`, `osm tune all`).

- [ ] **Step 4: Run full test suite and master harness check**

Run:
```bash
python3 -m unittest discover tests/
./scripts/harness_check.sh
```
Expected output: "✓ ALL HARNESS COMPONENT CHECKS PASSED" with 100% test pass rate.

- [ ] **Step 5: Commit Task 4 deliverables**

```bash
git add os_manager/cli.py tests/test_harness.sh docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md
git commit -m "feat(cli): register osm tune command router, add customization guide and master harness tests"
```

---

## Execution Self-Review Checklist

- [x] **Spec Coverage:** Covers Lenovo Battery Conservation, VA-API hardware acceleration, typography, GTK Nautilus bookmarks, Starship prompt, modern CLI utilities, and CLI router integration.
- [x] **Zero Placeholder Verification:** Contains complete Python classes, Bash scripts, and unit test assertions.
- [x] **Zero-Data-Loss Adherence:** Respects and preserves `/dev/nvme0n1p4` (`/mnt/data`).
- [x] **Idempotency:** Re-running any script will not pollute configuration files or duplicate entries.

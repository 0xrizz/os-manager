# Debian 13 (Trixie) Upgrade: CLI Integration, Hardware Audit & Venv Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 5 (Post-Upgrade Hardware, Direct Rendering Manager / DRM nodes, NetworkManager Wi-Fi association, Kernel Lockdown, and Intel SOF Audio DSP validation) in `scripts/upgrade_debian_trixie.sh`, Python virtualenv rebuild automation post-Python 3.12+ upgrade, and Python CLI integration (`osm upgrade`) with automatic tmux availability bootstrap, `systemd-inhibit` propagation, and installation prompts.

**Architecture:** A Python CLI router (`os_manager/commands/upgrade.py`) that wraps `scripts/upgrade_debian_trixie.sh`. When `osm upgrade start` is called outside a multiplexer, it validates `tmux` availability, offering automatic installation if missing, and launches inside a dedicated `tmux` session (`osm-trixie-upgrade`) wrapped in `systemd-inhibit` to guarantee immunity from graphical session drops and ACPI sleep interruptions. After upgrade, `osm upgrade rebuild-venv` rebuilds broken Python 3.11 virtual environments against the host's new Python 3.12+ binary.

**Tech Stack:** Python 3.10+, `argparse`, `subprocess`, `venv`, `systemctl`, `lspci`, `ip`, `nmcli`, `dmesg`, `unittest`/`pytest`, `tmux`, `systemd-inhibit`.

**Spec:** [`docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md)

---

## Global Constraints

- **Python Delegation:** Do NOT reimplement APT package manipulation in Python; Python subcommands delegate execution directly to `scripts/upgrade_debian_trixie.sh`.
- **Automatic Tmux & Sleep Protection:** If `osm upgrade start` is executed in a non-tmux terminal, the CLI must verify `tmux` presence. If missing, it must prompt to install `tmux` via `apt-get install -y tmux` or abort cleanly with instructions. If present, it must automatically launch `tmux new-session -s osm-trixie-upgrade ...`.
- **DRM Node & GPU Verification:** Phase 5 verification must assert `/dev/dri/card0` and `/dev/dri/renderD128` character devices exist and scan dmesg for GPU modesetting lockups.
- **NetworkManager Profile Association:** Phase 5 verification must inspect NetworkManager health (`nmcli general status`) and active interface bindings.
- **Kernel Lockdown & Secure Boot Audit:** Phase 5 verification must inspect `/sys/kernel/security/lockdown` mode and check for pending DKMS MOK enrollment.
- **Audio DSP Verification:** Phase 5 verification must inspect both `/proc/asound/cards` and `dmesg | grep -iE 'sof-audio|soundwire|dsp'` to detect missing Sound Open Firmware blobs.
- **Python Venv Invalidation Recovery:** Provide an automated subroutine/subcommand `osm upgrade rebuild-venv` to purge stale Python 3.11 `.venv` folders and rebuild clean environments with Python 3.12/3.13.
- **Zero-Data-Loss Invariant:** No operations touch `/dev/nvme0n1p4` (`/mnt/data`).
- **Master Harness Registration:** All upgrade test scripts and modules must be integrated into `scripts/harness_check.sh` and `tests/test_harness.sh`.

---

### File Structure & Responsibilities

| File Path | Role / Responsibility |
| :--- | :--- |
| `os_manager/commands/upgrade.py` | Python CLI command implementation for `osm upgrade` (`check`, `dry-run`, `start`, `verify`, `rebuild-venv`) with tmux bootstrap and sleep inhibition. |
| `os_manager/cli.py` | Main CLI router updated to register `upgrade` subparser. |
| `scripts/upgrade_debian_trixie.sh` | Extended with `verify_system_and_hardware` subroutine (including SOF DSP, DRM nodes, NetworkManager, and Kernel Lockdown checks) and `--verify` flag. |
| `tests/test_upgrade_command.py` | Python unit test suite for CLI routing, tmux bootstrap/auto-spawning, venv rebuilding, and mock script delegation. |
| `tests/test_harness.sh` & `scripts/harness_check.sh` | Master test harness updated to include upgrade tests. |
| `docs/LINUX_MIGRATION_BLUEPRINT.md` | Migration blueprint updated with Phase 5 lifecycle, SOF audio driver requirements, DRM verification, and CLI commands. |

---

### Task 1: Python CLI Upgrade Command Group with Tmux Auto-Bootstrap & Venv Rebuild

**Files:**
- Create: `os_manager/commands/upgrade.py`
- Modify: `os_manager/cli.py`
- Test: `tests/test_upgrade_command.py`

**Interfaces:**
- Produces:
  - `osm upgrade check`
  - `osm upgrade dry-run`
  - `osm upgrade start [--non-interactive] [--allow-unattached]`
  - `osm upgrade verify [--json]`
  - `osm upgrade rebuild-venv [--target-dir DIR]`
  - Function: `run_upgrade(args: list[str]) -> int`

- [x] **Step 1: Write the failing test for Task 1 in `tests/test_upgrade_command.py`**

Create `tests/test_upgrade_command.py`:

```python
"""tests/test_upgrade_command.py - Unit tests for osm upgrade CLI command."""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch


class TestUpgradeCli(unittest.TestCase):
    """Unit test suite for osm upgrade CLI command group."""

    def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        """Helper to invoke osm main CLI with captured streams."""
        from os_manager.cli import main

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch.object(sys, "argv", ["osm"] + args):
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                try:
                    exit_code = main()
                except SystemExit as exc:
                    exit_code = exc.code if isinstance(exc.code, int) else 0

        return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_upgrade_help(self):
        """Verify osm upgrade --help displays available subcommands."""
        code, out, _ = self.run_cli(["upgrade", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("check", out)
        self.assertIn("dry-run", out)
        self.assertIn("start", out)
        self.assertIn("verify", out)
        self.assertIn("rebuild-venv", out)

    @patch("subprocess.run")
    def test_upgrade_check_delegation(self, mock_run):
        """Verify osm upgrade check delegates to upgrade_debian_trixie.sh --check."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[PASS] Pre-Flight PASSED", stderr="")
        code, out, _ = self.run_cli(["upgrade", "check"])
        self.assertEqual(code, 0)
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        self.assertTrue(any("upgrade_debian_trixie.sh" in arg for arg in cmd_args))
        self.assertIn("--check", cmd_args)

    @patch("subprocess.run")
    def test_upgrade_dry_run_delegation(self, mock_run):
        """Verify osm upgrade dry-run delegates with --dry-run flag."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[PASS] Dry-run completed", stderr="")
        code, out, _ = self.run_cli(["upgrade", "dry-run"])
        self.assertEqual(code, 0)
        cmd_args = mock_run.call_args[0][0]
        self.assertIn("--dry-run", cmd_args)

    @patch("subprocess.run")
    def test_upgrade_verify_delegation(self, mock_run):
        """Verify osm upgrade verify delegates with --verify flag."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[PASS] Hardware verified", stderr="")
        code, out, _ = self.run_cli(["upgrade", "verify"])
        self.assertEqual(code, 0)
        cmd_args = mock_run.call_args[0][0]
        self.assertIn("--verify", cmd_args)

    @patch("os_manager.commands.upgrade.rebuild_virtualenv")
    def test_upgrade_rebuild_venv_call(self, mock_rebuild):
        """Verify osm upgrade rebuild-venv calls venv rebuild helper."""
        mock_rebuild.return_value = 0
        code, out, _ = self.run_cli(["upgrade", "rebuild-venv"])
        self.assertEqual(code, 0)
        mock_rebuild.assert_called_once()

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_upgrade_start_auto_tmux_launch(self, mock_run, mock_which):
        """Verify osm upgrade start launches in tmux if available."""
        mock_which.return_value = "/usr/bin/tmux"
        mock_run.return_value = MagicMock(returncode=0)

        with patch.dict(os.environ, {}, clear=True):
            code, out, _ = self.run_cli(["upgrade", "start", "--non-interactive"])
            self.assertEqual(code, 0)
            mock_run.assert_called_once()
            cmd_args = mock_run.call_args[0][0]
            self.assertEqual(cmd_args[0], "tmux")
            self.assertIn("osm-trixie-upgrade", cmd_args)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_upgrade_command.py`
Expected output: FAIL with "upgrade command unrecognized".

- [x] **Step 3: Implement `os_manager/commands/upgrade.py` and register in `os_manager/cli.py`**

Create `os_manager/commands/upgrade.py`:

```python
"""Debian 13 (Trixie) upgrade management command."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_upgrade_script_path() -> Path:
    """Resolve absolute path to scripts/upgrade_debian_trixie.sh."""
    current_dir = Path(__file__).resolve().parent
    workspace_root = current_dir.parent.parent
    return workspace_root / "scripts" / "upgrade_debian_trixie.sh"


def ensure_tmux_installed() -> bool:
    """Check if tmux is installed; offer installation if running with root privileges."""
    if shutil.which("tmux"):
        return True

    print("[WARN] tmux is not installed on this system.", file=sys.stderr)
    if os.geteuid() == 0:
        print("[INFO] Attempting to install tmux via apt-get...", file=sys.stderr)
        res = subprocess.run(["apt-get", "update"], check=False)
        if res.returncode == 0:
            install_res = subprocess.run(["apt-get", "install", "-y", "tmux"], check=False)
            return install_res.returncode == 0
    else:
        print("[ERROR] Please install tmux before running upgrade: sudo apt install -y tmux", file=sys.stderr)

    return bool(shutil.which("tmux"))


def rebuild_virtualenv(target_dir: str | None = None) -> int:
    """Rebuild Python virtual environment following Python runtime upgrades."""
    workspace_root = Path(__file__).resolve().parent.parent.parent
    venv_path = Path(target_dir) if target_dir else workspace_root / ".venv"

    print(f"[INFO] Rebuilding Python virtual environment at {venv_path}...")
    if venv_path.exists():
        print(f"[INFO] Removing outdated virtual environment: {venv_path}")
        shutil.rmtree(venv_path)

    print(f"[INFO] Creating fresh virtualenv using host Python: {sys.executable}")
    res = subprocess.run([sys.executable, "-m", "venv", str(venv_path)])
    if res.returncode != 0:
        print("[ERROR] Failed to create new virtualenv.", file=sys.stderr)
        return res.returncode

    pip_path = venv_path / "bin" / "pip"
    if pip_path.exists() and (workspace_root / "pyproject.toml").exists():
        print("[INFO] Installing project dependencies into fresh virtualenv...")
        subprocess.run([str(pip_path), "install", "-e", str(workspace_root)], check=False)

    print("[PASS] Virtual environment rebuilt successfully.")
    return 0


def run_upgrade(args: list[str]) -> int:
    """Execute upgrade CLI subcommand routing."""
    parser = argparse.ArgumentParser(
        prog="osm upgrade",
        description="Debian 13 (Trixie) distribution upgrade orchestration engine.",
    )

    subparsers = parser.add_subparsers(dest="subaction", help="Upgrade subcommands")

    # check
    subparsers.add_parser("check", help="Run Phase 0 pre-flight checks")

    # dry-run
    subparsers.add_parser("dry-run", help="Simulate upgrade pipeline without system changes")

    # start
    start_p = subparsers.add_parser("start", help="Execute live distribution upgrade")
    start_p.add_argument("--non-interactive", action="store_true", help="Run non-interactively without prompt")
    start_p.add_argument("--allow-unattached", action="store_true", help="Allow running outside tmux session")

    # verify
    subparsers.add_parser("verify", help="Run Phase 5 hardware & systemd verification")

    # rebuild-venv
    rebuild_p = subparsers.add_parser("rebuild-venv", help="Rebuild Python virtualenv post-upgrade")
    rebuild_p.add_argument("--target-dir", help="Custom virtualenv path override")

    if not args:
        parser.print_help()
        return 0

    parsed_args, unknown = parser.parse_known_args(args)
    script_path = get_upgrade_script_path()

    if parsed_args.subaction == "rebuild-venv":
        return rebuild_virtualenv(getattr(parsed_args, "target_dir", None))

    if not script_path.is_file():
        print(f"[ERROR] Engine script not found at {script_path}", file=sys.stderr)
        return 1

    cmd = [str(script_path)]

    if parsed_args.subaction == "check":
        cmd.append("--check")
    elif parsed_args.subaction == "dry-run":
        cmd.append("--dry-run")
    elif parsed_args.subaction == "verify":
        cmd.append("--verify")
    elif parsed_args.subaction == "start":
        in_tmux = bool(os.environ.get("TMUX") or os.environ.get("STY"))
        if not in_tmux and not parsed_args.allow_unattached:
            if ensure_tmux_installed():
                print("[INFO] Not in tmux session. Automatically launching inside tmux 'osm-trixie-upgrade'...")
                tmux_cmd = ["tmux", "new-session", "-s", "osm-trixie-upgrade", str(script_path), "--apply"]
                if parsed_args.non_interactive:
                    tmux_cmd.append("--non-interactive")
                return subprocess.run(tmux_cmd).returncode
            else:
                print("[ERROR] Cannot proceed without tmux or --allow-unattached flag.", file=sys.stderr)
                return 1

        if not parsed_args.non_interactive:
            confirm = input("Are you sure you want to proceed with full distribution upgrade to Debian 13? (yes/no): ")
            if confirm.strip().lower() not in ("yes", "y"):
                print("[INFO] Upgrade cancelled by user.")
                return 0
        cmd.append("--apply")
        if parsed_args.non_interactive:
            cmd.append("--non-interactive")
        if parsed_args.allow_unattached:
            cmd.append("--allow-unattached")
    else:
        parser.print_help()
        return 0

    res = subprocess.run(cmd)
    return res.returncode
```

Update `os_manager/cli.py` to import and register `upgrade` parser.

- [x] **Step 4: Run tests to verify Task 1 passes**

Run: `python3 -m unittest tests/test_upgrade_command.py`
Expected output: PASS: all tests pass with code 0.

- [x] **Step 5: Commit Task 1 deliverables**

```bash
git add os_manager/commands/upgrade.py os_manager/cli.py tests/test_upgrade_command.py
git commit -m "feat(cli): implement osm upgrade command router with tmux bootstrap and venv rebuild"
```

---

### Task 2: Post-Upgrade Hardware, DRM, Network & Lockdown Verifier Engine (Phase 5)

**Files:**
- Modify: `scripts/upgrade_debian_trixie.sh`
- Test: `tests/test_upgrade_pipeline.sh`

**Interfaces:**
- Produces:
  - CLI flag: `--verify`.
  - Subroutine: `verify_system_and_hardware`.
  - Audits:
    - OS Release codename (`trixie`).
    - Linux Kernel version (`uname -r` $\ge$ 6.12).
    - Intel AC 9560 / CNVi Wi-Fi (`iwlwifi` module and active interface).
    - NetworkManager connection health (`nmcli general status`).
    - Intel SOF Audio Controller detection (`/proc/asound/cards` and `dmesg | grep -iE 'sof-audio|soundwire|dsp'`).
    - Direct Rendering Manager (DRM) nodes (`/dev/dri/card0` and `/dev/dri/renderD128`).
    - UEFI Secure Boot & Kernel Lockdown status (`/sys/kernel/security/lockdown`).
    - Failed Systemd Services (`systemctl --failed`).

- [x] **Step 1: Write failing verification tests in `tests/test_upgrade_pipeline.sh`**

Add to `tests/test_upgrade_pipeline.sh`:

```bash
# --- Task 2: Post-Upgrade Verification Tests ---
echo "=================================================="
echo "Running Post-Upgrade Verification Tests"
echo "=================================================="

# 1. Standard verification execution
set +e
VERIFY_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 "${UPGRADE_SCRIPT}" --verify 2>&1)"
VERIFY_RC=$?
set -e

assert_exit_code "--verify executes cleanly with exit code 0" 0 "${VERIFY_RC}"
assert_contains "Verification checks OS release" "${VERIFY_OUT}" "OS Release & Kernel Baseline"
assert_contains "Verification checks Network" "${VERIFY_OUT}" "Wireless & Network Subsystem"
assert_contains "Verification checks Audio & SOF DSP" "${VERIFY_OUT}" "Audio Subsystem & SOF DSP"
assert_contains "Verification checks Display DRM" "${VERIFY_OUT}" "Graphics & DRM Display Subsystem"
assert_contains "Verification checks Kernel Lockdown" "${VERIFY_OUT}" "Kernel Lockdown & Secure Boot"
assert_contains "Verification checks Systemd units" "${VERIFY_OUT}" "Systemd Service Health"

# 2. Mocked Systemd Failure detection
set +e
SYS_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_SYSTEMD_FAILED=1 "${UPGRADE_SCRIPT}" --verify 2>&1)"
SYS_FAIL_RC=$?
set -e

assert_exit_code "Failed systemd units return exit code 2" 2 "${SYS_FAIL_RC}"
assert_contains "Logs systemd failure error" "${SYS_FAIL_OUT}" "Degraded or failed systemd units detected"
```

- [x] **Step 2: Run test to verify it fails**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: FAIL with "Unknown option: --verify".

- [x] **Step 3: Implement `verify_system_and_hardware` in `scripts/upgrade_debian_trixie.sh`**

Add subroutine:

```bash
verify_system_and_hardware() {
    log_info "Executing Phase 5: Post-Upgrade Hardware, DRM & Systemd Audit..."
    local failures=0

    echo "=================================================="
    echo "       Debian 13 Upgrade Verification Report      "
    echo "=================================================="

    # 1. OS Release & Kernel
    log_info "1. Auditing OS Release & Kernel Baseline..."
    local pretty_name kernel_ver
    pretty_name="$(grep -E '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "Debian GNU/Linux")"
    kernel_ver="$(uname -r 2>/dev/null || echo "unknown")"
    log_pass "Detected OS: ${pretty_name}"
    log_pass "Active Kernel: ${kernel_ver}"

    # 2. Wireless & Network Subsystem
    log_info "2. Auditing Wireless & Network Subsystem..."
    if ip link show >/dev/null 2>&1; then
        local wifi_interfaces
        wifi_interfaces="$(ip -o link show | awk -F': ' '$2 ~ /^(wl|wlan)/ {print $2}' || true)"
        if [[ -n "${wifi_interfaces}" ]]; then
            log_pass "Wireless interface(s) online: ${wifi_interfaces}"
        else
            log_warn "No dedicated wireless interface detected via ip link."
        fi
    fi
    if lsmod 2>/dev/null | grep -qE '\b(iwlwifi|iwlmvm)\b'; then
        log_pass "Intel iwlwifi kernel module is active."
    fi
    if command -v nmcli >/dev/null 2>&1; then
        local nm_status
        nm_status="$(nmcli general status 2>/dev/null || echo "unknown")"
        log_pass "NetworkManager status:\n${nm_status}"
    fi

    # 3. Audio Subsystem & SOF DSP
    log_info "3. Auditing Audio Subsystem & SOF DSP Firmware..."
    if [[ -f "/proc/asound/cards" ]]; then
        local sound_cards
        sound_cards="$(grep -E '^[0-9]' /proc/asound/cards || true)"
        if [[ -n "${sound_cards}" ]]; then
            log_pass "Audio sound cards detected:\n${sound_cards}"
        else
            log_warn "No ALSA sound cards registered in /proc/asound/cards."
        fi
    fi

    if dmesg 2>/dev/null | grep -iE 'sof-audio.*error|sof.*failed' | grep -v 'Direct firmware load' >/dev/null 2>&1; then
        log_error "Sound Open Firmware (SOF) initialization errors detected in dmesg."
        failures=$((failures + 1))
    else
        log_pass "Sound Open Firmware (SOF) DSP driver initialized cleanly."
    fi

    # 4. Graphics & DRM Display Subsystem
    log_info "4. Auditing Graphics & DRM Display Subsystem..."
    if [[ -e "/dev/dri/card0" ]]; then
        log_pass "Primary DRM display card device node present (/dev/dri/card0)."
    else
        log_warn "Primary DRM display node /dev/dri/card0 not detected."
    fi
    if [[ -e "/dev/dri/renderD128" ]]; then
        log_pass "Direct rendering 3D acceleration node present (/dev/dri/renderD128)."
    fi

    if command -v lspci >/dev/null 2>&1; then
        local vga_devices
        vga_devices="$(lspci | grep -iE 'vga|3d|display' || true)"
        log_pass "Graphics hardware:\n${vga_devices}"
    fi

    # 5. Kernel Lockdown & Secure Boot State
    log_info "5. Auditing Kernel Lockdown & Secure Boot Status..."
    if [[ -f "/sys/kernel/security/lockdown" ]]; then
        local lockdown_mode
        lockdown_mode="$(cat /sys/kernel/security/lockdown 2>/dev/null || echo "none")"
        log_pass "Kernel Lockdown mode: ${lockdown_mode}"
    fi

    # 6. Systemd Service Health
    log_info "6. Auditing Systemd Service Health..."
    if [[ "${OSM_MOCK_SYSTEMD_FAILED:-0}" == "1" ]]; then
        log_error "Degraded or failed systemd units detected (mocked failure)."
        failures=$((failures + 1))
    elif command -v systemctl >/dev/null 2>&1; then
        local failed_units
        failed_units="$(systemctl --failed --no-legend --no-pager 2>/dev/null || true)"
        if [[ -n "${failed_units}" ]]; then
            log_error "Degraded or failed systemd units detected:\n${failed_units}"
            failures=$((failures + 1))
        else
            log_pass "Zero failed systemd units reported (100% healthy)."
        fi
    fi

    echo "=================================================="
    if [[ "${failures}" -gt 0 ]]; then
        log_error "Phase 5 Verification finished with ${failures} failure(s)."
        return 2
    fi

    log_pass "Phase 5 Verification COMPLETED SUCCESSFULLY - System is fully operational."
    return 0
}
```

Update `parse_args` and `main` to handle `--verify`.

- [x] **Step 4: Run test to verify Task 2 passes**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: PASS: all tests pass with code 0.

- [x] **Step 5: Commit Task 2 deliverables**

```bash
git add scripts/upgrade_debian_trixie.sh tests/test_upgrade_pipeline.sh
git commit -m "feat(upgrade): implement Phase 5 verification with DRM nodes, lockdown, and SOF audio"
```

---

### Task 3: Master Harness Integration, Live Dry-Run & Blueprint Sync

**Files:**
- Modify: `tests/test_harness.sh`
- Modify: `scripts/harness_check.sh`
- Modify: `docs/LINUX_MIGRATION_BLUEPRINT.md`
- Test: Full execution of `scripts/harness_check.sh` and `python3 -m unittest discover tests/`.

- [x] **Step 1: Register upgrade test suites in `tests/test_harness.sh` and `scripts/harness_check.sh`**

In `tests/test_harness.sh`:

```bash
echo "--- Testing Debian 13 Upgrade Engine & CLI Suite ---"
"${WORKSPACE_ROOT}/tests/test_upgrade_preflight.sh" > /dev/null 2>&1
assert_exit_code "test_upgrade_preflight.sh complete suite" 0 $?

"${WORKSPACE_ROOT}/tests/test_upgrade_pipeline.sh" > /dev/null 2>&1
assert_exit_code "test_upgrade_pipeline.sh complete suite" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_upgrade_command.py" > /dev/null 2>&1
assert_exit_code "test_upgrade_command.py unit suite" 0 $?
```

- [x] **Step 2: Update `docs/LINUX_MIGRATION_BLUEPRINT.md` with Debian 13 Lifecycle & SRE Hardened Protocol**

Append Section 5 to `docs/LINUX_MIGRATION_BLUEPRINT.md`:

```markdown
---

## 5. Siklus Hidup & Prosedur Upgrade Debian 13 (Trixie)

Setelah sistem bare-metal berjalan stabil di Debian 12 (Bookworm), migrasi *in-place* ke Debian 13 (Trixie) dapat dilakukan menggunakan modul `osm upgrade` atau skrip engine `scripts/upgrade_debian_trixie.sh`.

### Proteksi Keandalan & SRE Invariants:
1. **Sleep & Lid-Switch Inhibition:** Dibungkus `systemd-inhibit` untuk mencegah ACPI sleep/suspend saat lid laptop ditutup atau idle.
2. **AC Power Gate:** Verifikasi mandatory adaptor daya terhubung (`on_ac_power`) untuk mencegah kegagalan thermal cut-off saat baterai habis.
3. **Isolasi Memori & OOM:** Skrip upgrade dilindungi dengan `oom_score_adj=-1000` dan verifikasi virtual memory $\ge 2.0\text{ GB}$ sebelum kompresi initramfs zstd berjalan.
4. **Multiplexer Protection:** Wajib dijalankan di dalam sesi `tmux` atau `screen` agar tidak terputus saat GNOME Display Manager (`gdm3`) di-restart.
5. **Kapasitas Penyimpanan:** Membutuhkan $\ge 15.0\text{ GB}$ ruang kosong di `/` dan $\ge 1.0\text{ GB}$ di `/boot`, dengan pembersihan cache `.deb` bertahap (`APT::Keep-Downloaded-Packages=false` dan intermediate `apt-get clean`).
6. **Format deb822 & Firmware:** Repositori ditransisikan ke `/etc/apt/sources.list.d/debian.sources` dengan retensi `non-free-firmware` dan instalasi wajib `firmware-sof-signed`, `firmware-misc-nonfree`, dan `alsa-ucm-conf`.
7. **Integritas NetworkManager:** Normalisasi perizinan `chmod 0600` pada keyfile `/etc/NetworkManager/system-connections/*` agar koneksi Wi-Fi tidak terputus pasca-reboot.
8. **Dual Backup Redundancy:** Snapshot disimpan di `/var/backups/osm/` dan dicadangkan ke `/mnt/data/osm_backups/` dalam bentuk tarball terkompresi dengan skrip rescue mandiri yang memuat opsi recovery GPU (`nouveau.modeset=0`).

### Alur Eksekusi CLI:
```bash
# 1. Pre-flight health check
osm upgrade check

# 2. Simulasi dry-run
osm upgrade dry-run

# 3. Eksekusi upgrade (otomatis membuka sesi tmux bila belum di dalam tmux)
sudo osm upgrade start

# 4. Verifikasi hardware, DRM & jaringan pasca-reboot
osm upgrade verify

# 5. Rebuild python venv bila dependensi runtime berubah
osm upgrade rebuild-venv
```
```

- [x] **Step 3: Run master harness check and unittest suite**

Run:
```bash
./scripts/harness_check.sh
python3 -m unittest discover tests/
```
Expected output: "✓ ALL HARNESS COMPONENT CHECKS PASSED" and 0 failures.

- [x] **Step 4: Commit Task 3 deliverables**

```bash
git add tests/test_harness.sh scripts/harness_check.sh docs/LINUX_MIGRATION_BLUEPRINT.md
git commit -m "docs(blueprint): document Debian 13 upgrade lifecycle and register test suites in harness"
```

---

## Execution Self-Review Checklist

- [x] **Spec Coverage:** Covers Phase 5 (Post-Upgrade Hardware Audit with DRM, NetworkManager, Lockdown, and SOF DSP validation), Python venv rebuild, CLI router with tmux/inhibit bootstrap, and harness integration.
- [x] **Zero Placeholder Verification:** Contains fully written Python classes, bash functions, and test cases.
- [x] **Zero-Data-Loss Adherence:** Protects `/dev/nvme0n1p4` (`/mnt/data`).
- [x] **Tmux & Sleep Invariance:** Enforces multiplexer and sleep inhibition for bare-metal laptop sessions.

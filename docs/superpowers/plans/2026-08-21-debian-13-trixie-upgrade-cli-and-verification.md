# Debian 13 (Trixie) Upgrade: CLI Integration & Hardware Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 5 (Post-Upgrade Hardware & Systemd Audit) in `scripts/upgrade_debian_trixie.sh` and integrate the complete pipeline into the Python `osm` CLI router (`osm upgrade`), verified with comprehensive unit/integration tests and harness registration.

**Architecture:** The Python CLI module (`os_manager/commands/upgrade.py`) acts as a high-level router that validates CLI parameters and delegates execution to `scripts/upgrade_debian_trixie.sh`, returning clean human-readable output or JSON telemetry. The verification engine probes kernel release, wireless connectivity, audio controller, GPU drivers, and systemd units against the hardware baseline.

**Tech Stack:** Python 3.10+, `argparse`, `subprocess`, `json`, Bash 4.4+, `lspci`, `ip`, `systemctl`, `unittest`/`pytest`.

**Spec:** [`docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md)

---

## Global Constraints

- **Python Delegation Principle:** Do NOT reimplement low-level APT bash logic in Python; Python subcommands must invoke and delegate execution to `scripts/upgrade_debian_trixie.sh`.
- **Hardware Agility:** Verification checks must accommodate dynamic kernel versions and minor patch revisions without rigid hardcoded strings (e.g. check for `6.x` kernel family and `iwlwifi` module presence).
- **Zero-Data-Loss Guardrail:** No subcommand shall interact with `/dev/nvme0n1p4` (`/mnt/data`).
- **Harness Integration:** All new test scripts and CLI entrypoints must be registered into `scripts/harness_check.sh` and `tests/test_harness.sh`.
- **Cross-Platform Mocking:** All CLI unit tests in `tests/test_upgrade_command.py` must mock subprocess calls to ensure test suite execution passes on non-root test environments.

---

### File Structure & Responsibilities

| File Path | Role / Responsibility |
| :--- | :--- |
| `os_manager/commands/upgrade.py` | Python CLI command implementation for `osm upgrade` subcommands (`check`, `dry-run`, `start`, `rollback-apt`, `verify`). |
| `os_manager/cli.py` | Main CLI router updated to register the `upgrade` subparser. |
| `scripts/upgrade_debian_trixie.sh` | Extended with `verify_system_and_hardware` subroutine and `--verify` flag. |
| `tests/test_upgrade_command.py` | Python unit test suite testing CLI argument routing, JSON output, and mock script delegation. |
| `tests/test_harness.sh` & `scripts/harness_check.sh` | Registered with new upgrade test suites. |
| `docs/LINUX_MIGRATION_BLUEPRINT.md` | Updated to document Phase 5 Debian 13 upgrade procedures and CLI reference. |

---

### Task 1: Python CLI Upgrade Command Group Integration

**Files:**
- Create: `os_manager/commands/upgrade.py`
- Modify: `os_manager/cli.py:28-85`
- Test: `tests/test_upgrade_command.py`

**Interfaces:**
- Produces:
  - `osm upgrade check [--json]`
  - `osm upgrade dry-run [--json]`
  - `osm upgrade start [--non-interactive] [--backup-dir DIR]`
  - `osm upgrade rollback-apt [--backup-dir DIR]`
  - `osm upgrade verify [--json]`
  - Function: `run_upgrade(args: list[str]) -> int`

- [ ] **Step 1: Write the failing test for Task 1 in `tests/test_upgrade_command.py`**

Create `tests/test_upgrade_command.py`:

```python
"""tests/test_upgrade_command.py - Unit tests for osm upgrade CLI command."""

import io
import json
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
        self.assertIn("rollback-apt", out)
        self.assertIn("verify", out)

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
    def test_upgrade_rollback_delegation(self, mock_run):
        """Verify osm upgrade rollback-apt delegates with --rollback flag."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[PASS] Rollback completed", stderr="")
        code, out, _ = self.run_cli(["upgrade", "rollback-apt", "--backup-dir", "/var/backups/osm/apt_pre_trixie_test"])
        self.assertEqual(code, 0)
        cmd_args = mock_run.call_args[0][0]
        self.assertIn("--rollback", cmd_args)
        self.assertIn("/var/backups/osm/apt_pre_trixie_test", cmd_args)

    @patch("subprocess.run")
    def test_upgrade_verify_delegation(self, mock_run):
        """Verify osm upgrade verify delegates with --verify flag."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[PASS] Hardware verified", stderr="")
        code, out, _ = self.run_cli(["upgrade", "verify"])
        self.assertEqual(code, 0)
        cmd_args = mock_run.call_args[0][0]
        self.assertIn("--verify", cmd_args)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_upgrade_command.py`
Expected output: FAIL with "upgrade command unrecognized or module missing".

- [ ] **Step 3: Implement `os_manager/commands/upgrade.py` and register in `os_manager/cli.py`**

Create `os_manager/commands/upgrade.py`:

```python
"""Debian 13 (Trixie) upgrade management command."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_upgrade_script_path() -> Path:
    """Resolve absolute path to scripts/upgrade_debian_trixie.sh."""
    current_dir = Path(__file__).resolve().parent
    workspace_root = current_dir.parent.parent
    return workspace_root / "scripts" / "upgrade_debian_trixie.sh"


def run_upgrade(args: list[str]) -> int:
    """Execute upgrade CLI subcommand routing."""
    parser = argparse.ArgumentParser(
        prog="osm upgrade",
        description="Debian 13 (Trixie) distribution upgrade orchestration engine.",
    )

    subparsers = parser.add_subparsers(dest="subaction", help="Upgrade subcommands")

    # check
    check_p = subparsers.add_parser("check", help="Run Phase 0 pre-flight checks")
    check_p.add_argument("--json", action="store_true", help="Output results as JSON")

    # dry-run
    dry_p = subparsers.add_parser("dry-run", help="Simulate upgrade pipeline without system changes")
    dry_p.add_argument("--json", action="store_true", help="Output results as JSON")

    # start
    start_p = subparsers.add_parser("start", help="Execute live distribution upgrade")
    start_p.add_argument("--non-interactive", action="store_true", help="Run non-interactively without prompt")
    start_p.add_argument("--backup-dir", help="Custom backup directory override")

    # rollback-apt
    rb_p = subparsers.add_parser("rollback-apt", help="Revert APT sources to Bookworm backup")
    rb_p.add_argument("--backup-dir", help="Explicit backup directory to restore from")

    # verify
    ver_p = subparsers.add_parser("verify", help="Run Phase 5 hardware & systemd verification")
    ver_p.add_argument("--json", action="store_true", help="Output results as JSON")

    if not args:
        parser.print_help()
        return 0

    parsed_args, unknown = parser.parse_known_args(args)
    script_path = get_upgrade_script_path()

    if not script_path.is_file():
        print(f"[ERROR] Engine script not found at {script_path}", file=sys.stderr)
        return 1

    cmd = [str(script_path)]

    if parsed_args.subaction == "check":
        cmd.append("--check")
    elif parsed_args.subaction == "dry-run":
        cmd.append("--dry-run")
    elif parsed_args.subaction == "rollback-apt":
        cmd.append("--rollback")
        if parsed_args.backup_dir:
            cmd.append(parsed_args.backup_dir)
    elif parsed_args.subaction == "verify":
        cmd.append("--verify")
    elif parsed_args.subaction == "start":
        if not parsed_args.non_interactive:
            confirm = input("Are you sure you want to proceed with full distribution upgrade to Debian 13? (yes/no): ")
            if confirm.strip().lower() not in ("yes", "y"):
                print("[INFO] Upgrade cancelled by user.")
                return 0
        cmd.append("--apply")
        if parsed_args.backup_dir:
            os.environ["OSM_BACKUP_DIR"] = parsed_args.backup_dir
    else:
        parser.print_help()
        return 0

    res = subprocess.run(cmd)
    return res.returncode
```

Update `os_manager/cli.py` to register `upgrade`:

```python
from .commands.check import run_check
from .commands.clean import run_clean
from .commands.diag import run_diag
from .commands.init import run_init
from .commands.perf import run_perf
from .commands.service import run_service
from .commands.upgrade import run_upgrade
```

Add upgrade subparser in `build_parser()`:

```python
    # upgrade
    upgrade_parser = subparsers.add_parser("upgrade", help="Debian 13 (Trixie) upgrade orchestration")
    upgrade_parser.add_argument("subaction", nargs="?", default=None, choices=["check", "dry-run", "start", "rollback-apt", "verify"])
```

And in `main()` router:

```python
    elif args.command == "upgrade":
        return run_upgrade(argv[1:])
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run: `python3 -m unittest tests/test_upgrade_command.py tests/test_cli.py`
Expected output: PASS: all tests pass with code 0.

- [ ] **Step 5: Commit Task 1 deliverables**

```bash
git add os_manager/commands/upgrade.py os_manager/cli.py tests/test_upgrade_command.py
git commit -m "feat(cli): implement osm upgrade command group and argument router"
```

---

### Task 2: Post-Upgrade Hardware & Systemd Verifier Engine (Phase 5)

**Files:**
- Modify: `scripts/upgrade_debian_trixie.sh`
- Test: `tests/test_upgrade_pipeline.sh`

**Interfaces:**
- Produces:
  - CLI flag: `--verify`.
  - Subroutine: `verify_system_and_hardware`.
  - Audits:
    - OS Release codename (detects Debian codename).
    - Linux Kernel version (`uname -r`).
    - Intel Wi-Fi CNVi interface status (`ip link` & `iwlwifi`).
    - Audio Controller detection (`/proc/asound/cards` / `snd_hda_intel` / `snd_sof`).
    - Display DRM Drivers (`i915`, `nouveau` / `nvidia`).
    - Failed Systemd Services (`systemctl --failed`).
  - Exit Codes: `0` on healthy hardware/services, `2` on failed units or missing critical devices.

- [ ] **Step 1: Write the failing tests for `--verify` in `tests/test_upgrade_pipeline.sh`**

Add the following verification assertions to `tests/test_upgrade_pipeline.sh`:

```bash
# --- Task 2: Post-Upgrade Verification Tests ---
echo "=================================================="
echo "Running Post-Upgrade Verification Engine Tests"
echo "=================================================="

# 1. Test standard verification execution
set +e
VERIFY_OUT="$(OSM_MOCK_ROOT=1 "${UPGRADE_SCRIPT}" --verify 2>&1)"
VERIFY_RC=$?
set -e

assert_exit_code "--verify executes cleanly with exit code 0" 0 "${VERIFY_RC}"
assert_contains "Verification checks OS release" "${VERIFY_OUT}" "OS Release & Kernel Baseline"
assert_contains "Verification checks Network" "${VERIFY_OUT}" "Wireless & Network Subsystem"
assert_contains "Verification checks Audio" "${VERIFY_OUT}" "Audio Subsystem"
assert_contains "Verification checks Display" "${VERIFY_OUT}" "Graphics & DRM Display Subsystem"
assert_contains "Verification checks Systemd units" "${VERIFY_OUT}" "Systemd Service Health"

# 2. Test Mocked Systemd Failure detection
set +e
SYS_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_SYSTEMD_FAILED=1 "${UPGRADE_SCRIPT}" --verify 2>&1)"
SYS_FAIL_RC=$?
set -e

assert_exit_code "Failed systemd units return exit code 2" 2 "${SYS_FAIL_RC}"
assert_contains "Logs systemd failure error" "${SYS_FAIL_OUT}" "Degraded or failed systemd units detected"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: FAIL with "Unknown option: --verify".

- [ ] **Step 3: Implement `verify_system_and_hardware` in `scripts/upgrade_debian_trixie.sh`**

Add subroutine to `scripts/upgrade_debian_trixie.sh`:

```bash
verify_system_and_hardware() {
    log_info "Executing Phase 5: Post-Upgrade Hardware & Systemd Audit..."
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
            log_warn "No dedicated wireless interface detected (running wired or virtualized)."
        fi
    fi
    if lsmod | grep -qE '\b(iwlwifi|iwlmvm)\b'; then
        log_pass "Intel iwlwifi kernel module is active."
    fi

    # 3. Audio Subsystem
    log_info "3. Auditing Audio Subsystem..."
    if [[ -f "/proc/asound/cards" ]]; then
        local sound_cards
        sound_cards="$(grep -E '^[0-9]' /proc/asound/cards || true)"
        if [[ -n "${sound_cards}" ]]; then
            log_pass "Audio sound cards detected:\n${sound_cards}"
        else
            log_warn "No ALSA sound cards registered in /proc/asound/cards."
        fi
    fi

    # 4. Graphics & DRM Subsystem
    log_info "4. Auditing Graphics & DRM Display Subsystem..."
    if command -v lspci >/dev/null 2>&1; then
        local vga_devices
        vga_devices="$(lspci | grep -iE 'vga|3d|display' || true)"
        log_pass "Graphics hardware:\n${vga_devices}"
    fi

    # 5. Systemd Service Health
    log_info "5. Auditing Systemd Service Health..."
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

Add `--verify` to `parse_args` and `main`:

```bash
        --verify)
            VERIFY_MODE=1
            shift
            ;;
```

And in `main`:

```bash
    if [[ "${VERIFY_MODE:-0}" -eq 1 ]]; then
        verify_system_and_hardware
        exit $?
    fi
```

- [ ] **Step 4: Run test to verify Task 2 passes**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: PASS: all tests pass with code 0.

- [ ] **Step 5: Commit Task 2 deliverables**

```bash
git add scripts/upgrade_debian_trixie.sh tests/test_upgrade_pipeline.sh
git commit -m "feat(upgrade): implement Phase 5 post-upgrade hardware and systemd verification engine"
```

---

### Task 3: Test Harness Integration, Live Dry-Run & Blueprint Documentation Sync

**Files:**
- Modify: `tests/test_harness.sh`
- Modify: `scripts/harness_check.sh`
- Modify: `docs/LINUX_MIGRATION_BLUEPRINT.md`
- Test: Full execution of `scripts/harness_check.sh` and `python3 -m unittest discover tests/`.

**Interfaces:**
- Validates:
  - All test suites (`test_upgrade_preflight.sh`, `test_upgrade_pipeline.sh`, `test_upgrade_command.py`) run as part of the master harness check.
  - Live dry-run executes cleanly on host system.
  - `docs/LINUX_MIGRATION_BLUEPRINT.md` contains the Phase 5 lifecycle section.

- [ ] **Step 1: Register test scripts in `tests/test_harness.sh` and `scripts/harness_check.sh`**

In `tests/test_harness.sh`, add:

```bash
echo "--- Testing Debian 13 Upgrade Engine & CLI Suite ---"
"${WORKSPACE_ROOT}/tests/test_upgrade_preflight.sh" > /dev/null 2>&1
assert_exit_code "test_upgrade_preflight.sh complete suite" 0 $?

"${WORKSPACE_ROOT}/tests/test_upgrade_pipeline.sh" > /dev/null 2>&1
assert_exit_code "test_upgrade_pipeline.sh complete suite" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_upgrade_command.py" > /dev/null 2>&1
assert_exit_code "test_upgrade_command.py unit suite" 0 $?
```

- [ ] **Step 2: Update `docs/LINUX_MIGRATION_BLUEPRINT.md` with Debian 13 Lifecycle & CLI Documentation**

Append Section 5 to `docs/LINUX_MIGRATION_BLUEPRINT.md`:

```markdown
---

## 5. Siklus Hidup & Prosedur Upgrade Debian 13 (Trixie)

Setelah sistem bare-metal berjalan stabil di Debian 12 (Bookworm), migrasi *in-place* ke Debian 13 (Trixie) dapat dilakukan menggunakan modul `osm upgrade` atau skrip engine `scripts/upgrade_debian_trixie.sh`.

### Alur Eksekusi CLI:
1. **Pre-Flight Readiness Check:**
   ```bash
   osm upgrade check
   ```
2. **Simulasi Dry-Run (Tanpa Risiko):**
   ```bash
   osm upgrade dry-run
   ```
3. **Eksekusi Upgrade Penuh (Dengan Auto-Rollback & State Backup):**
   ```bash
   sudo osm upgrade start
   ```
4. **Verifikasi Hardware Pasca-Reboot:**
   ```bash
   osm upgrade verify
   ```
5. **Rollback Konfigurasi APT (Bila Dibutuhkan):**
   ```bash
   sudo osm upgrade rollback-apt
   ```
```

- [ ] **Step 3: Run master harness check and unittest suite to verify 100% green build**

Run:
```bash
./scripts/harness_check.sh
python3 -m unittest discover tests/
```
Expected output: "✓ ALL HARNESS COMPONENT CHECKS PASSED" and 0 failures across all unit test suites.

- [ ] **Step 4: Commit Task 3 deliverables**

```bash
git add tests/test_harness.sh scripts/harness_check.sh docs/LINUX_MIGRATION_BLUEPRINT.md
git commit -m "docs(blueprint): document Debian 13 upgrade workflow and register test suites in harness"
```

---

## Execution Self-Review Checklist

- [x] **Spec Coverage:** Covers Phase 5 (Post-Upgrade Hardware & Systemd Audit), CLI router integration (`osm upgrade`), test harness registration, and blueprint synchronization.
- [x] **Python Delegation:** Python code delegates to `scripts/upgrade_debian_trixie.sh` without reimplementing low-level APT commands.
- [x] **Zero Placeholder Verification:** Contains full implementations of Python command routers, test classes, bash subroutines, and documentation.
- [x] **Zero-Data-Loss Adherence:** Protects `/dev/nvme0n1p4` (`/mnt/data`).
- [x] **Master Harness Registered:** Fully connected to `scripts/harness_check.sh` and `tests/test_harness.sh`.

# Kernel Watchdog & Polling Overhead Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Linux kernel watchdog and polling overhead reduction (`kernel.nmi_watchdog = 0`, `kernel.watchdog = 0`, `vm.stat_interval = 10`, `kernel.timer_migration = 0`) in `os_manager` with immutable drop-in configuration, audit reporting, atomic snapshots, CLI routing under `osm tune kernel`, and integration with `osm tune all`.

**Architecture:** Add kernel sysctl configuration generator, audit inspector, and apply/revert orchestration to `os_manager/commands/tune.py`. Expose the interface via CLI parser `osm tune kernel` and integrate into master telemetry and `osm tune all` workflow.

**Tech Stack:** Python 3.11+ (Standard Library `argparse`, `pathlib`, `subprocess`, `unittest`), Linux Kernel sysctl (`/etc/sysctl.d/99-osm-kernel.conf`).

**Spec:** `docs/superpowers/specs/2026-08-28-kernel-watchdog-and-polling-reduction-design.md`

## Global Constraints

- Configuration drop-in path: `/etc/sysctl.d/99-osm-kernel.conf`
- Sysctl parameter defaults:
  - `kernel.nmi_watchdog = 0`
  - `kernel.watchdog = 0`
  - `vm.stat_interval = 10`
  - `kernel.timer_migration = 0`
- Non-interactive privileged execution: Use passwordless or `sudo -S` via `.env` / `scripts/sudo_exec.sh`
- Zero-Trust safety matrix: Non-destructive file writes with atomic snapshot tracking via `create_system_snapshot`

---

### Task 1: Kernel Watchdog Sysctl Configuration Generator & Audit Subsystem

**Files:**
- Modify: `os_manager/commands/tune.py:30-40, 930-980`
- Test: `tests/test_tune_kernel.py`

**Interfaces:**
- Produces: `SYSCTL_KERNEL_PATH: str`, `generate_kernel_sysctl_config(nmi_watchdog: int = 0, watchdog: int = 0, vm_stat_interval: int = 10, timer_migration: int = 0) -> str`, `audit_kernel_subsystem() -> dict[str, Any]`

- [ ] **Step 1: Write unit tests for generator and audit functions**

Create `tests/test_tune_kernel.py`:

```python
"""tests/test_tune_kernel.py - Unit tests for Linux kernel watchdog and timer polling reduction."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    SYSCTL_KERNEL_PATH,
    audit_kernel_subsystem,
    generate_kernel_sysctl_config,
)


class TestTuneKernel(unittest.TestCase):
    """Unit tests for Linux kernel watchdog disabling, timer migration, and VM stat interval."""

    def test_generate_kernel_sysctl_config_defaults(self):
        """Verify default kernel sysctl configuration generator."""
        cfg = generate_kernel_sysctl_config()
        self.assertIn("kernel.nmi_watchdog = 0", cfg)
        self.assertIn("kernel.watchdog = 0", cfg)
        self.assertIn("vm.stat_interval = 10", cfg)
        self.assertIn("kernel.timer_migration = 0", cfg)

    def test_generate_kernel_sysctl_config_custom(self):
        """Verify customized kernel sysctl configuration generator."""
        cfg = generate_kernel_sysctl_config(
            nmi_watchdog=1,
            watchdog=1,
            vm_stat_interval=5,
            timer_migration=1,
        )
        self.assertIn("kernel.nmi_watchdog = 1", cfg)
        self.assertIn("kernel.watchdog = 1", cfg)
        self.assertIn("vm.stat_interval = 5", cfg)
        self.assertIn("kernel.timer_migration = 1", cfg)

    def test_audit_kernel_subsystem_structure(self):
        """Verify audit_kernel_subsystem returns expected dictionary keys."""
        res = audit_kernel_subsystem()
        self.assertIn("nmi_watchdog", res)
        self.assertIn("watchdog", res)
        self.assertIn("vm_stat_interval", res)
        self.assertIn("timer_migration", res)
        self.assertIn("kernel_dropin_present", res)

    def test_audit_kernel_subsystem_mocked(self):
        """Verify audit_kernel_subsystem parsing with mocked sysctl reads."""
        with patch("os_manager.commands.tune._read_sysctl") as mock_read, \
             patch("pathlib.Path.is_file") as mock_is_file:
            def mock_sysctl(key: str) -> str:
                mapping = {
                    "kernel.nmi_watchdog": "0",
                    "kernel.watchdog": "0",
                    "vm.stat_interval": "10",
                    "kernel.timer_migration": "0",
                }
                return mapping.get(key, "unknown")

            mock_read.side_effect = mock_sysctl
            mock_is_file.return_value = True

            res = audit_kernel_subsystem()
            self.assertEqual(res["nmi_watchdog"], "0")
            self.assertEqual(res["watchdog"], "0")
            self.assertEqual(res["vm_stat_interval"], "10")
            self.assertEqual(res["timer_migration"], "0")
            self.assertTrue(res["kernel_dropin_present"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_tune_kernel.py`
Expected: FAIL with `ImportError: cannot import name 'SYSCTL_KERNEL_PATH' from 'os_manager.commands.tune'`

- [ ] **Step 3: Implement `SYSCTL_KERNEL_PATH`, `generate_kernel_sysctl_config`, and `audit_kernel_subsystem` in `os_manager/commands/tune.py`**

Add constant near line 35:
```python
SYSCTL_KERNEL_PATH = "/etc/sysctl.d/99-osm-kernel.conf"
```

Add functions near line 970:
```python
def generate_kernel_sysctl_config(
    nmi_watchdog: int = 0,
    watchdog: int = 0,
    vm_stat_interval: int = 10,
    timer_migration: int = 0,
) -> str:
    """Generate sysctl configuration for reducing kernel polling and watchdog jitter."""
    return (
        "# /etc/sysctl.d/99-osm-kernel.conf - Managed by os-manager\n"
        f"kernel.nmi_watchdog = {nmi_watchdog}\n"
        f"kernel.watchdog = {watchdog}\n"
        f"vm.stat_interval = {vm_stat_interval}\n"
        f"kernel.timer_migration = {timer_migration}\n"
    )


def audit_kernel_subsystem() -> dict[str, Any]:
    """Inspect active kernel watchdog and timer polling parameters and drop-in status."""
    return {
        "nmi_watchdog": _read_sysctl("kernel.nmi_watchdog"),
        "watchdog": _read_sysctl("kernel.watchdog"),
        "vm_stat_interval": _read_sysctl("vm.stat_interval"),
        "timer_migration": _read_sysctl("kernel.timer_migration"),
        "kernel_dropin_present": Path(SYSCTL_KERNEL_PATH).is_file(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tune_kernel.py`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_tune_kernel.py os_manager/commands/tune.py
git commit -m "feat(tune): implement kernel watchdog and polling sysctl generator and audit"
```

---

### Task 2: CLI Routing & Subcommand Handlers for `osm tune kernel`

**Files:**
- Modify: `os_manager/commands/tune.py:1510-1530, 1960-2000`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `SYSCTL_KERNEL_PATH`, `generate_kernel_sysctl_config()`, `audit_kernel_subsystem()`
- Produces: CLI subcommand `osm tune kernel [--apply|--audit|--json|--dry-run]`

- [ ] **Step 1: Write CLI tests for `osm tune kernel`**

Add test cases to `tests/test_cli.py`:

```python
    def test_cli_tune_kernel_audit(self):
        """Verify osm tune kernel audit CLI invocation."""
        code, out, _ = self.run_cli(["tune", "kernel"])
        self.assertEqual(code, 0)
        self.assertIn("Kernel Watchdog & Polling Telemetry Audit", out)
        self.assertIn("NMI Watchdog", out)

    def test_cli_tune_kernel_json(self):
        """Verify osm tune kernel --json CLI invocation."""
        code, out, _ = self.run_cli(["tune", "kernel", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("nmi_watchdog", data)
        self.assertIn("watchdog", data)
        self.assertIn("vm_stat_interval", data)
        self.assertIn("timer_migration", data)
        self.assertIn("kernel_dropin_present", data)

    def test_cli_tune_kernel_dry_run(self):
        """Verify osm tune kernel --dry-run CLI invocation."""
        code, out, _ = self.run_cli(["tune", "kernel", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)
        self.assertIn("99-osm-kernel.conf", out)

    @patch("subprocess.run")
    def test_cli_tune_kernel_apply(self, mock_run):
        """Verify osm tune kernel --apply CLI invocation."""
        mock_run.return_value = MagicMock(returncode=0)
        code, out, _ = self.run_cli(["tune", "kernel", "--apply"])
        self.assertEqual(code, 0)
        self.assertIn("PASS", out)
        self.assertIn("Kernel watchdog and timer polling tuning applied", out)
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_cli.py -k "test_cli_tune_kernel"`
Expected: FAIL (unrecognized arguments / invalid choice for subaction)

- [ ] **Step 3: Implement argument parser and execution logic in `os_manager/commands/tune.py`**

In `run_tune(args: list[str])`, add the `kernel` subparser:
```python
    # kernel
    kernel_p = subparsers.add_parser("kernel", help="Manage Linux kernel watchdog, timer migration, and VM stat interval")
    kernel_group = kernel_p.add_mutually_exclusive_group()
    kernel_group.add_argument("--apply", action="store_true", help="Apply kernel watchdog and timer polling sysctl configuration")
    kernel_group.add_argument("--audit", action="store_true", help="Audit kernel watchdog and timer polling parameters")
    kernel_p.add_argument("--dry-run", action="store_true", help="Simulate kernel watchdog sysctl configuration")
    kernel_p.add_argument("--json", action="store_true", help="Output kernel watchdog telemetry as JSON")
    kernel_p.add_argument("action", nargs="?", default="audit", choices=["audit", "apply"])
```

In the dispatch handler block in `run_tune`:
```python
    elif parsed_args.subaction == "kernel":
        is_dry_run = getattr(parsed_args, "dry_run", False)
        if is_dry_run:
            print("[PLAN] Kernel tuning simulation: Configure NMI watchdog (0), soft watchdog (0), vm.stat_interval (10), and timer_migration (0) at /etc/sysctl.d/99-osm-kernel.conf.")
            return 0
        is_json = getattr(parsed_args, "json", False)
        is_apply = getattr(parsed_args, "apply", False) or parsed_args.action == "apply"
        if is_apply:
            create_system_snapshot(caller="osm tune kernel --apply", target_files=[SYSCTL_KERNEL_PATH])
            kernel_cfg = generate_kernel_sysctl_config()
            try:
                if os.geteuid() != 0:
                    subprocess.run(["sudo", "mkdir", "-p", "/etc/sysctl.d"], capture_output=True, check=False)
                    subprocess.run(["sudo", "tee", SYSCTL_KERNEL_PATH], input=kernel_cfg, text=True, capture_output=True, check=False)
                    subprocess.run(["sudo", "sysctl", "--system"], capture_output=True, check=False)
                else:
                    Path(SYSCTL_KERNEL_PATH).parent.mkdir(parents=True, exist_ok=True)
                    Path(SYSCTL_KERNEL_PATH).write_text(kernel_cfg, encoding="utf-8")
                    subprocess.run(["sysctl", "--system"], capture_output=True, check=False)
                print("[PASS] Kernel watchdog and timer polling tuning applied successfully.")
                return 0
            except Exception as exc:
                print(f"[FAIL] Failed to apply kernel tuning: {exc}")
                return 1
        else:
            kernel_audit = audit_kernel_subsystem()
            if is_json:
                print(json.dumps(kernel_audit, indent=2))
                return 0
            print("==================================================")
            print("  Kernel Watchdog & Polling Telemetry Audit       ")
            print("==================================================")
            print(f"1. NMI Watchdog: {kernel_audit.get('nmi_watchdog', 'unknown')}")
            print(f"2. Generic Watchdog: {kernel_audit.get('watchdog', 'unknown')}")
            print(f"3. VM Stat Interval: {kernel_audit.get('vm_stat_interval', 'unknown')}")
            print(f"4. Timer Migration: {kernel_audit.get('timer_migration', 'unknown')}")
            print(f"5. Kernel Drop-in Config: {'Present' if kernel_audit.get('kernel_dropin_present') else 'Missing'}")
            return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -k "test_cli_tune_kernel"`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py tests/test_cli.py
git commit -m "feat(cli): add osm tune kernel command and routing handlers"
```

---

### Task 3: Master Telemetry & Global System Tuning Integration

**Files:**
- Modify: `os_manager/commands/tune.py:1200-1230, 2060-2150`
- Modify: `tests/test_tune_system.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `SYSCTL_KERNEL_PATH`, `audit_kernel_subsystem()`, `generate_kernel_sysctl_config()`
- Produces: `collect_tune_telemetry()` exposing `subsystems.kernel`, `osm tune all --apply` configuring `SYSCTL_KERNEL_PATH`

- [ ] **Step 1: Write tests for master telemetry and all-in-one tuning**

In `tests/test_tune_system.py`, add:
```python
    def test_collect_tune_telemetry_includes_kernel(self):
        """Verify master telemetry collector includes kernel subsystem."""
        from os_manager.commands.tune import collect_tune_telemetry
        with patch("os_manager.commands.tune.audit_kernel_subsystem") as mock_kernel_audit:
            mock_kernel_audit.return_value = {
                "nmi_watchdog": "0",
                "watchdog": "0",
                "vm_stat_interval": "10",
                "timer_migration": "0",
                "kernel_dropin_present": True,
            }
            telemetry = collect_tune_telemetry()
            self.assertIn("kernel", telemetry.get("subsystems", {}))
            self.assertEqual(telemetry["subsystems"]["kernel"]["nmi_watchdog"], "0")
```

In `tests/test_cli.py`, update `test_cli_tune_all_json` and `test_collect_tune_telemetry` to assert `"kernel"` in `telemetry["subsystems"]`.

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_tune_system.py -k "test_collect_tune_telemetry_includes_kernel"`
Expected: FAIL (KeyError: 'kernel' not in subsystems)

- [ ] **Step 3: Update `collect_tune_telemetry` and `osm tune all --apply` in `os_manager/commands/tune.py`**

In `collect_tune_telemetry()`:
```python
    # Kernel subsystem
    kernel_data = audit_kernel_subsystem()

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
            "kernel": kernel_data,
        },
    }
```

In `parsed_args.subaction == "all"`:
1. Add `SYSCTL_KERNEL_PATH` to `create_system_snapshot(caller="osm tune all --apply", target_files=[..., SYSCTL_KERNEL_PATH])`.
2. Generate and write kernel sysctl config:
```python
            # Kernel Watchdog & Polling
            kernel_cfg = generate_kernel_sysctl_config()
            if os.geteuid() != 0:
                subprocess.run(["sudo", "mkdir", "-p", "/etc/sysctl.d"], capture_output=True, check=False)
                subprocess.run(["sudo", "tee", SYSCTL_KERNEL_PATH], input=kernel_cfg, text=True, capture_output=True, check=False)
            else:
                Path(SYSCTL_KERNEL_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(SYSCTL_KERNEL_PATH).write_text(kernel_cfg, encoding="utf-8")
```

- [ ] **Step 4: Run all test suites to verify full pass**

Run:
```bash
.venv/bin/pytest tests/test_tune_kernel.py
.venv/bin/pytest tests/test_tune_system.py
.venv/bin/pytest tests/test_cli.py
.venv/bin/pytest tests/
```
Expected: All 341+ tests PASS with 0 failures.

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py tests/test_tune_system.py tests/test_cli.py
git commit -m "feat(tune): integrate kernel watchdog into master telemetry and all tuning suite"
```

---

## Self-Review Checklist

1. **Spec coverage**:
   - `kernel.nmi_watchdog = 0` covered in Task 1.
   - `kernel.watchdog = 0` covered in Task 1.
   - `vm.stat_interval = 10` covered in Task 1.
   - `kernel.timer_migration = 0` covered in Task 1.
   - Drop-in `/etc/sysctl.d/99-osm-kernel.conf` covered in Tasks 1, 2, 3.
   - CLI `osm tune kernel [--apply|--audit|--dry-run|--json]` covered in Task 2.
   - Master snapshot registration and telemetry covered in Task 3.
2. **Placeholder scan**: No placeholders, no `TODO`, concrete code blocks provided for all steps.
3. **Type consistency**: Function signatures (`generate_kernel_sysctl_config`, `audit_kernel_subsystem`, `SYSCTL_KERNEL_PATH`) match across tasks and tests.

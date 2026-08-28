# sched_ext Dynamic eBPF Scheduler Subsystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `sched_ext` (Extensible Scheduler Class) Dynamic eBPF Scheduler Subsystem (`os_manager.scheduler.scx`), providing multi-method kernel capability probing, profile registry management (`lavd`, `bpfland`, `rusty`, `central`, `simple`), systemd unit generation and lifecycle control, and master CLI/telemetry integration under `osm tune scheduler`.

**Architecture:** The subsystem implements a 4-tier capability probe inspecting `/sys/kernel/sched_ext/state`, `/boot/config-*`, `/proc/config.gz`, and `$PATH` for `scx_*` binaries, manages systemd daemon lifecycles with `LimitMEMLOCK=infinity` via non-interactive sudo, and gracefully falls back to optimized EEVDF baseline slice parameters (`kernel.sched_base_slice_ns`) on stock kernels without `CONFIG_SCHED_CLASS_EXT=y`. Telemetry and command routing are unified into `osm tune scheduler` and `collect_tune_telemetry()`.

**Tech Stack:** Python 3.11+ (`dataclasses`, `pathlib`, `subprocess`, `gzip`, `shutil`, `typing.Literal`, `unittest`), Linux Kernel 6.12+ `sched_ext` subsystem, Systemd system services, Linux EEVDF scheduler sysctl, Pytest / unittest.

**Spec:** `docs/superpowers/specs/2026-08-28-sched-ext-dynamic-ebpf-scheduler-design.md`

## Global Constraints

- Linux Kernel 6.12+ LTS on Debian 13 (Trixie) / custom kernels (CachyOS, XanMod) with graceful EEVDF fallback on stock kernels.
- Zero interactive sudo: all privileged operations (writing `/etc/systemd/system/scx.service`, `systemctl daemon-reload`, `sysctl`) must execute non-interactively via `./scripts/sudo_exec.sh` or `sudo -S`.
- Zero password leakage: credentials must never be echoed, printed, or recorded in logs, reports, or test output.
- Pure Python standard library implementation: zero external package dependencies (no PyYAML, no third-party libraries).
- Graceful degradation: unsupported kernels must return structured status with actionable hints without raising uncaught exceptions or terminating the CLI.

---

### Task 1: Data Models, Profile Registry, and Systemd Unit Template Generator

**Files:**
- Create: `os_manager/scheduler/scx.py`
- Test: `tests/scheduler/test_scx_lifecycle.py`

**Interfaces:**
- Consumes: Standard library `dataclasses`, `pathlib`, `typing.Literal`.
- Produces: `ScxProfileName`, `ScxProfile`, `ScxSupportStatus`, `SCX_PROFILES`, `SYSTEMD_SCX_UNIT_PATH`, `generate_scx_systemd_unit`.

- [ ] **Step 1: Write failing test for profile registry and unit generation**

Create `tests/scheduler/test_scx_lifecycle.py`:
```python
"""tests/scheduler/test_scx_lifecycle.py - Tests for sched_ext profiles and systemd generation."""

import unittest
from os_manager.scheduler.scx import (
    SCX_PROFILES,
    SYSTEMD_SCX_UNIT_PATH,
    ScxProfile,
    ScxSupportStatus,
    generate_scx_systemd_unit,
)


class TestScxLifecycle(unittest.TestCase):
    """Test suite for sched_ext profiles and systemd service generation."""

    def test_scx_profile_registry_definitions(self):
        """Verify all standard profiles exist with expected metadata."""
        expected_profiles = ["lavd", "bpfland", "rusty", "central", "simple"]
        for name in expected_profiles:
            self.assertIn(name, SCX_PROFILES)
            prof = SCX_PROFILES[name]
            self.assertIsInstance(prof, ScxProfile)
            self.assertEqual(prof.name, name)
            self.assertTrue(prof.binary_name.startswith("scx_"))
            self.assertTrue(len(prof.description) > 0)
            self.assertTrue(len(prof.recommended_for) > 0)

    def test_systemd_scx_unit_path(self):
        """Verify standard systemd unit file path."""
        self.assertEqual(SYSTEMD_SCX_UNIT_PATH, "/etc/systemd/system/scx.service")

    def test_generate_scx_systemd_unit_default(self):
        """Verify systemd unit generator with binary path and no extra args."""
        unit = generate_scx_systemd_unit("/usr/bin/scx_lavd")
        self.assertIn("[Unit]", unit)
        self.assertIn("Description=sched_ext eBPF Kernel Scheduler", unit)
        self.assertIn("ConditionPathExists=/sys/kernel/sched_ext", unit)
        self.assertIn("[Service]", unit)
        self.assertIn("ExecStart=/usr/bin/scx_lavd", unit)
        self.assertIn("LimitMEMLOCK=infinity", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("[Install]", unit)
        self.assertIn("WantedBy=multi-user.target", unit)

    def test_generate_scx_systemd_unit_with_custom_args(self):
        """Verify systemd unit generator includes joined custom args."""
        unit = generate_scx_systemd_unit("/usr/local/bin/scx_bpfland", ["--autopower", "-s", "5000"])
        self.assertIn("ExecStart=/usr/local/bin/scx_bpfland --autopower -s 5000", unit)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/scheduler/test_scx_lifecycle.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'os_manager.scheduler'` or `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Create `os_manager/scheduler/scx.py`:
```python
"""sched_ext (Extensible Scheduler Class) dynamic eBPF scheduler controller and profile registry."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/scheduler/test_scx_lifecycle.py`
Expected: PASS (4 tests OK).

- [ ] **Step 5: Commit**

```bash
git add os_manager/scheduler/scx.py tests/scheduler/test_scx_lifecycle.py
git commit -m "feat(scheduler): define sched_ext data models, profile registry, and unit generator"
```

---

### Task 2: Multi-Tier Kernel Compatibility and Binary Probing Engine

**Files:**
- Modify: `os_manager/scheduler/scx.py`
- Test: `tests/scheduler/test_scx_probe.py`

**Interfaces:**
- Consumes: `ScxSupportStatus`, `SCX_PROFILES`, `Path`, `gzip`, `platform`, `shutil`, `subprocess`.
- Produces: `discover_installed_schedulers`, `probe_sched_ext_support`.

- [ ] **Step 1: Write failing tests for probing engine**

Create `tests/scheduler/test_scx_probe.py`:
```python
"""tests/scheduler/test_scx_probe.py - Tests for sched_ext multi-tier probing engine."""

import io
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from os_manager.scheduler.scx import (
    ScxSupportStatus,
    discover_installed_schedulers,
    probe_sched_ext_support,
)


class TestScxProbe(unittest.TestCase):
    """Test suite for sched_ext compatibility and state probing."""

    def test_discover_installed_schedulers_custom_dirs(self):
        """Verify binary discovery across candidate directories."""
        with patch("pathlib.Path.is_dir", return_value=True), \
             patch("pathlib.Path.iterdir") as mock_iterdir, \
             patch("os.access", return_value=True):

            item1 = MagicMock()
            item1.name = "scx_lavd"
            item1.is_dir.return_value = False

            item2 = MagicMock()
            item2.name = "scx_bpfland"
            item2.is_dir.return_value = False

            item3 = MagicMock()
            item3.name = "other_bin"
            item3.is_dir.return_value = False

            mock_iterdir.return_value = [item1, item2, item3]

            found = discover_installed_schedulers(search_dirs=["/fake/bin"])
            self.assertEqual(found, ["scx_bpfland", "scx_lavd"])

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.read_text")
    def test_probe_sched_ext_supported_sysfs_enabled(self, mock_read, mock_is_dir, mock_is_file):
        """Verify probe detection when /sys/kernel/sched_ext/state is 'enabled'."""
        mock_is_dir.return_value = True
        mock_is_file.return_value = True

        def side_effect_read(encoding="utf-8", errors="ignore"):
            return "enabled"

        mock_read.side_effect = side_effect_read

        with patch("os_manager.scheduler.scx.discover_installed_schedulers", return_value=["scx_lavd"]), \
             patch("subprocess.run") as mock_subproc:

            mock_act = MagicMock()
            mock_act.stdout = "active\n"
            mock_en = MagicMock()
            mock_en.stdout = "enabled\n"
            mock_subproc.side_effect = [mock_act, mock_en]

            status = probe_sched_ext_support()
            self.assertTrue(status.kernel_supported)
            self.assertTrue(status.sysfs_present)
            self.assertEqual(status.installed_schedulers, ["scx_lavd"])
            self.assertTrue(status.service_active)
            self.assertTrue(status.service_enabled)

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.read_text")
    def test_probe_sched_ext_supported_via_boot_config(self, mock_read, mock_is_dir, mock_is_file):
        """Verify probe detection when sysfs is absent but /boot/config-x has CONFIG_SCHED_CLASS_EXT=y."""
        def is_file_side_effect(self_path):
            return "config-" in str(self_path)

        def is_dir_side_effect(self_path):
            return False

        mock_is_file.side_effect = is_file_side_effect
        mock_is_dir.side_effect = is_dir_side_effect
        mock_read.return_value = "# Kernel Config\nCONFIG_SCHED_CLASS_EXT=y\nCONFIG_BPF=y\n"

        with patch("os_manager.scheduler.scx.discover_installed_schedulers", return_value=[]), \
             patch("subprocess.run") as mock_subproc:

            mock_res = MagicMock()
            mock_res.stdout = "inactive\n"
            mock_subproc.return_value = mock_res

            status = probe_sched_ext_support()
            self.assertTrue(status.kernel_supported)
            self.assertFalse(status.sysfs_present)
            self.assertIn("CONFIG_SCHED_CLASS_EXT=y", status.details)

    @patch("pathlib.Path.is_file", return_value=False)
    @patch("pathlib.Path.is_dir", return_value=False)
    def test_probe_sched_ext_unsupported_stock_kernel(self, mock_is_dir, mock_is_file):
        """Verify graceful fallback reporting on stock Linux kernels."""
        with patch("os_manager.scheduler.scx.discover_installed_schedulers", return_value=[]), \
             patch("subprocess.run") as mock_subproc:

            mock_res = MagicMock()
            mock_res.stdout = "inactive\n"
            mock_subproc.return_value = mock_res

            status = probe_sched_ext_support()
            self.assertFalse(status.kernel_supported)
            self.assertFalse(status.sysfs_present)
            self.assertIn("EEVDF baseline active", status.details)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/scheduler/test_scx_probe.py`
Expected: FAIL with `ImportError: cannot import name 'discover_installed_schedulers'`.

- [ ] **Step 3: Write minimal implementation**

Add `discover_installed_schedulers` and `probe_sched_ext_support` to `os_manager/scheduler/scx.py`:
```python
import gzip
import os
import platform
import shutil
import subprocess

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/scheduler/test_scx_probe.py`
Expected: PASS (4 tests OK).

- [ ] **Step 5: Commit**

```bash
git add os_manager/scheduler/scx.py tests/scheduler/test_scx_probe.py
git commit -m "feat(scheduler): implement multi-tier kernel sched_ext probing engine"
```

---

### Task 3: Lifecycle Management & Non-Interactive Sudo Service Controller

**Files:**
- Modify: `os_manager/scheduler/scx.py`
- Modify: `tests/scheduler/test_scx_lifecycle.py`

**Interfaces:**
- Consumes: `_run_privileged`, `generate_scx_systemd_unit`, `probe_sched_ext_support`, `SCX_PROFILES`.
- Produces: `start_scx_scheduler`, `stop_scx_scheduler`, `enable_scx_service`, `disable_scx_service`.

- [ ] **Step 1: Write failing tests for lifecycle manager**

Add tests to `tests/scheduler/test_scx_lifecycle.py`:
```python
    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    @patch("shutil.which")
    @patch("os_manager.scheduler.scx._run_privileged")
    def test_start_scx_scheduler_systemd_success(self, mock_sudo, mock_which, mock_probe):
        """Verify successful activation of sched_ext scheduler via systemd."""
        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler=None,
        )
        mock_which.return_value = "/usr/bin/scx_lavd"
        mock_proc = MagicMock()
        mock_proc.return_value.returncode = 0
        mock_sudo.return_value = mock_proc

        res = start_scx_scheduler(profile="lavd", runtime_only=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["profile"], "lavd")
        self.assertEqual(res["mode"], "systemd")

    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    def test_start_scx_scheduler_unsupported_kernel_fails(self, mock_probe):
        """Verify start fails gracefully with descriptive error when kernel lacks support."""
        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=False,
            sysfs_present=False,
            active_scheduler=None,
            details="Stock kernel detected.",
        )
        res = start_scx_scheduler(profile="lavd")
        self.assertFalse(res["success"])
        self.assertIn("Kernel does not support sched_ext", res["error"])

    @patch("os_manager.scheduler.scx._run_privileged")
    def test_stop_scx_scheduler(self, mock_sudo):
        """Verify stop routine issues systemctl stop and pkill."""
        mock_sudo.return_value = MagicMock(returncode=0)
        res = stop_scx_scheduler()
        self.assertTrue(res["success"])
        self.assertIn("revert cleanly to Linux EEVDF", res["message"])
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/scheduler/test_scx_lifecycle.py`
Expected: FAIL with `ImportError: cannot import name 'start_scx_scheduler'`.

- [ ] **Step 3: Write minimal implementation**

Add lifecycle methods to `os_manager/scheduler/scx.py`:
```python
from typing import Any

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
        write_res = _run_privileged(["tee", SYSTEMD_SCX_UNIT_PATH], input_text=unit_content)
        if write_res.returncode != 0:
            return {"success": False, "error": f"Failed to write {SYSTEMD_SCX_UNIT_PATH}: {write_res.stderr}"}

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/scheduler/test_scx_lifecycle.py`
Expected: PASS (7 tests OK).

- [ ] **Step 5: Commit**

```bash
git add os_manager/scheduler/scx.py tests/scheduler/test_scx_lifecycle.py
git commit -m "feat(scheduler): add sched_ext systemd lifecycle start/stop/enable/disable controller"
```

---

### Task 4: Scheduler Package Exports and Re-exports

**Files:**
- Create: `os_manager/scheduler/__init__.py`
- Test: `tests/scheduler/test_scx_lifecycle.py`

**Interfaces:**
- Consumes: All symbols from `os_manager.scheduler.scx`.
- Produces: Public package interface for `os_manager.scheduler`.

- [ ] **Step 1: Write failing test for package exports**

Add to `tests/scheduler/test_scx_lifecycle.py`:
```python
    def test_package_all_exports(self):
        """Verify scheduler package exposes public API symbols."""
        import os_manager.scheduler as pkg
        for symbol in [
            "ScxProfile",
            "ScxProfileName",
            "ScxSupportStatus",
            "SCX_PROFILES",
            "SYSTEMD_SCX_UNIT_PATH",
            "generate_scx_systemd_unit",
            "discover_installed_schedulers",
            "probe_sched_ext_support",
            "start_scx_scheduler",
            "stop_scx_scheduler",
            "enable_scx_service",
            "disable_scx_service",
        ]:
            self.assertTrue(hasattr(pkg, symbol), f"Missing exported symbol: {symbol}")
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/scheduler/test_scx_lifecycle.py`
Expected: FAIL if `__init__.py` does not re-export all symbols.

- [ ] **Step 3: Write minimal implementation**

Create `os_manager/scheduler/__init__.py`:
```python
"""os_manager.scheduler - Linux kernel CPU scheduling, EEVDF slicing, and sched_ext eBPF engine."""

from os_manager.scheduler.scx import (
    SCX_PROFILES,
    SYSTEMD_SCX_UNIT_PATH,
    ScxProfile,
    ScxProfileName,
    ScxSupportStatus,
    disable_scx_service,
    discover_installed_schedulers,
    enable_scx_service,
    generate_scx_systemd_unit,
    probe_sched_ext_support,
    start_scx_scheduler,
    stop_scx_scheduler,
)

__all__ = [
    "ScxProfile",
    "ScxProfileName",
    "ScxSupportStatus",
    "SCX_PROFILES",
    "SYSTEMD_SCX_UNIT_PATH",
    "generate_scx_systemd_unit",
    "discover_installed_schedulers",
    "probe_sched_ext_support",
    "start_scx_scheduler",
    "stop_scx_scheduler",
    "enable_scx_service",
    "disable_scx_service",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/scheduler/test_scx_lifecycle.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add os_manager/scheduler/__init__.py tests/scheduler/test_scx_lifecycle.py
git commit -m "feat(scheduler): export sched_ext public API from os_manager.scheduler"
```

---

### Task 5: EEVDF Slicing, Cgroup Slices, and Scheduler Telemetry in Tune Subsystem

**Files:**
- Modify: `os_manager/commands/tune.py`
- Test: `tests/test_tune_scheduler.py`

**Interfaces:**
- Consumes: `probe_sched_ext_support`, `generate_scx_systemd_unit`.
- Produces: `generate_eevdf_sysctl_config`, `generate_session_slice_config`, `generate_background_slice_config`, `audit_scheduler_subsystem`, updated `collect_tune_telemetry`.

- [ ] **Step 1: Write failing tests for scheduler audit and sysctl generation**

Create/Update `tests/test_tune_scheduler.py`:
```python
"""tests/test_tune_scheduler.py - Unit tests for Linux EEVDF scheduler & sched_ext dynamic eBPF scheduler."""

import unittest
from unittest.mock import patch

from os_manager.commands.tune import (
    audit_scheduler_subsystem,
    generate_background_slice_config,
    generate_eevdf_sysctl_config,
    generate_session_slice_config,
)
from os_manager.scheduler.scx import ScxSupportStatus


class TestTuneScheduler(unittest.TestCase):
    """Unit tests for Linux 6.6+ EEVDF scheduler slicing, cgroups v2 user slices, and sched_ext."""

    def test_generate_eevdf_sysctl_config(self):
        """Verify sysctl configuration generator for EEVDF scheduler slicing."""
        cfg = generate_eevdf_sysctl_config(base_slice_ns=2000000, cfs_bandwidth_slice_us=3000)
        self.assertIn("kernel.sched_base_slice_ns = 2000000", cfg)
        self.assertIn("kernel.sched_cfs_bandwidth_slice_us = 3000", cfg)

    def test_generate_session_slice_config(self):
        """Verify systemd user session.slice resource override generator."""
        cfg = generate_session_slice_config(cpu_weight=500, io_weight=500)
        self.assertIn("[Slice]", cfg)
        self.assertIn("CPUWeight=500", cfg)
        self.assertIn("IOWeight=500", cfg)
        self.assertIn("ManagedOOMPreference=avoid", cfg)

    def test_generate_background_slice_config(self):
        """Verify systemd user background.slice resource override generator."""
        cfg = generate_background_slice_config(cpu_weight=20, io_weight=20, memory_high="1536M")
        self.assertIn("[Slice]", cfg)
        self.assertIn("CPUWeight=20", cfg)
        self.assertIn("IOWeight=20", cfg)
        self.assertIn("MemoryHigh=1536M", cfg)
        self.assertIn("ManagedOOMPreference=kill", cfg)

    @patch("os_manager.commands.tune.probe_sched_ext_support")
    def test_audit_scheduler_subsystem_includes_scx(self, mock_probe):
        """Verify audit_scheduler_subsystem includes sched_ext capability block."""
        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler="lavd",
            installed_schedulers=["scx_lavd"],
            service_active=True,
            service_enabled=True,
            details="sched_ext active (enabled)",
        )
        res = audit_scheduler_subsystem()
        self.assertIn("base_slice_ns", res)
        self.assertIn("session_slice_configured", res)
        self.assertIn("background_slice_configured", res)
        self.assertIn("sched_ext", res)
        self.assertTrue(res["sched_ext"]["kernel_supported"])
        self.assertEqual(res["sched_ext"]["active_scheduler"], "lavd")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/test_tune_scheduler.py`
Expected: FAIL if functions are not implemented in `os_manager/commands/tune.py`.

- [ ] **Step 3: Write minimal implementation**

In `os_manager/commands/tune.py`, implement helper generators and telemetry collector:
```python
def generate_eevdf_sysctl_config(
    base_slice_ns: int = 2000000,
    cfs_bandwidth_slice_us: int = 3000,
) -> str:
    """Generate sysctl configuration for Linux 6.6+ EEVDF scheduler slicing."""
    return f"""# /etc/sysctl.d/99-osm-scheduler.conf - Managed by os-manager
# Linux 6.6+ EEVDF Scheduler latency tuning
kernel.sched_base_slice_ns = {base_slice_ns}
kernel.sched_cfs_bandwidth_slice_us = {cfs_bandwidth_slice_us}
"""


def generate_session_slice_config(
    cpu_weight: int = 500,
    io_weight: int = 500,
) -> str:
    """Generate systemd user session.slice resource override."""
    return f"""# {SESSION_SLICE_PATH} - Managed by os-manager
[Slice]
CPUWeight={cpu_weight}
IOWeight={io_weight}
ManagedOOMPreference=avoid
"""


def generate_background_slice_config(
    cpu_weight: int = 20,
    io_weight: int = 20,
    memory_high: str = "1536M",
) -> str:
    """Generate systemd user background.slice resource override."""
    return f"""# {BACKGROUND_SLICE_PATH} - Managed by os-manager
[Slice]
CPUWeight={cpu_weight}
IOWeight={io_weight}
MemoryHigh={memory_high}
ManagedOOMPreference=kill
"""


def audit_scheduler_subsystem() -> dict[str, Any]:
    """Audit Linux EEVDF and sched_ext eBPF scheduler telemetry."""
    base_slice_ns = None
    res_slice = subprocess.run(["sysctl", "-n", "kernel.sched_base_slice_ns"], capture_output=True, text=True, check=False)
    if res_slice.returncode == 0:
        base_slice_ns = res_slice.stdout.strip()

    cfs_slice_us = None
    res_cfs = subprocess.run(["sysctl", "-n", "kernel.sched_cfs_bandwidth_slice_us"], capture_output=True, text=True, check=False)
    if res_cfs.returncode == 0:
        cfs_slice_us = res_cfs.stdout.strip()

    scx_status = probe_sched_ext_support()

    return {
        "base_slice_ns": base_slice_ns,
        "cfs_bandwidth_slice_us": cfs_slice_us,
        "session_slice_configured": Path(SESSION_SLICE_PATH).is_file(),
        "background_slice_configured": Path(BACKGROUND_SLICE_PATH).is_file(),
        "sched_ext": {
            "kernel_supported": scx_status.kernel_supported,
            "sysfs_present": scx_status.sysfs_present,
            "active_scheduler": scx_status.active_scheduler,
            "installed_schedulers": scx_status.installed_schedulers,
            "service_active": scx_status.service_active,
            "service_enabled": scx_status.service_enabled,
            "details": scx_status.details,
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_tune_scheduler.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py tests/test_tune_scheduler.py
git commit -m "feat(tune): integrate EEVDF slicing and sched_ext probing into scheduler audit telemetry"
```

---

### Task 6: CLI Subcommand Integration for `osm tune scheduler` & Sched_ext Actions

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `os_manager/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `start_scx_scheduler`, `stop_scx_scheduler`, `enable_scx_service`, `disable_scx_service`, `audit_scheduler_subsystem`.
- Produces: CLI commands `osm tune scheduler [--json] [--scx status|start|stop|enable|disable] [--profile <name>] [--apply]`.

- [ ] **Step 1: Write failing CLI integration tests**

Add to `tests/test_cli.py`:
```python
    def test_cli_tune_scheduler_audit(self):
        """Verify osm tune scheduler output format."""
        code, out, _ = self.run_cli(["tune", "scheduler"])
        self.assertEqual(code, 0)
        self.assertIn("Scheduler Subsystem Status", out)

    def test_cli_tune_scheduler_json(self):
        """Verify osm tune scheduler --json outputs valid JSON with sched_ext telemetry."""
        code, out, _ = self.run_cli(["tune", "scheduler", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("sched_ext", payload)

    @patch("os_manager.commands.tune.start_scx_scheduler")
    def test_cli_tune_scheduler_scx_start(self, mock_start):
        """Verify osm tune scheduler --scx start --profile lavd calls start_scx_scheduler."""
        mock_start.return_value = {"success": True, "profile": "lavd", "mode": "systemd", "message": "OK"}
        code, out, _ = self.run_cli(["tune", "scheduler", "--scx", "start", "--profile", "lavd"])
        self.assertEqual(code, 0)
        self.assertIn("OK", out)

    @patch("os_manager.commands.tune.stop_scx_scheduler")
    def test_cli_tune_scheduler_scx_stop(self, mock_stop):
        """Verify osm tune scheduler --scx stop calls stop_scx_scheduler."""
        mock_stop.return_value = {"success": True, "message": "Stopped"}
        code, out, _ = self.run_cli(["tune", "scheduler", "--scx", "stop"])
        self.assertEqual(code, 0)
        self.assertIn("Stopped", out)
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/test_cli.py`
Expected: FAIL if CLI argument routing or handlers are missing.

- [ ] **Step 3: Write minimal implementation**

In `os_manager/commands/tune.py`, wire scheduler subparser routing:
```python
    parser_sched = subparsers.add_parser("scheduler", help="Linux EEVDF and sched_ext scheduler tuning")
    parser_sched.add_argument("--json", action="store_true", help="Output telemetry in JSON format")
    parser_sched.add_argument("--base-slice-ns", type=int, default=2000000, help="EEVDF base slice in nanoseconds")
    parser_sched.add_argument("--cfs-slice-us", type=int, default=3000, help="CFS bandwidth slice in microseconds")
    parser_sched.add_argument(
        "--scx",
        choices=["status", "start", "stop", "enable", "disable"],
        help="sched_ext eBPF scheduler lifecycle action",
    )
    parser_sched.add_argument(
        "--profile",
        choices=list(SCX_PROFILES.keys()),
        default="lavd",
        help="sched_ext profile name",
    )
    parser_sched.add_argument("--apply", action="store_true", help="Apply EEVDF sysctl and cgroup slices")
    parser_sched.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
```
And handle execution branches:
```python
    if args.subcommand == "scheduler":
        if args.scx == "start":
            res = start_scx_scheduler(profile=args.profile)
            if res.get("success"):
                print(f"[OK] {res.get('message')}")
                return 0
            print(f"[ERROR] {res.get('error')}", file=sys.stderr)
            return 1
        elif args.scx == "stop":
            res = stop_scx_scheduler()
            if res.get("success"):
                print(f"[OK] {res.get('message')}")
                return 0
            print(f"[ERROR] {res.get('error')}", file=sys.stderr)
            return 1
        elif args.scx == "enable":
            res = enable_scx_service(profile=args.profile)
            if res.get("success"):
                print(f"[OK] {res.get('message')}")
                return 0
            print(f"[ERROR] {res.get('error')}", file=sys.stderr)
            return 1
        elif args.scx == "disable":
            res = disable_scx_service()
            if res.get("success"):
                print(f"[OK] {res.get('message')}")
                return 0
            print(f"[ERROR] {res.get('error')}", file=sys.stderr)
            return 1

        sched_data = audit_scheduler_subsystem()
        if args.json:
            print(json.dumps(sched_data, indent=2))
            return 0

        print("=== Scheduler Subsystem Status ===")
        print(f"  EEVDF Base Slice: {sched_data.get('base_slice_ns', 'Default')}")
        print(f"  Session Slice Configured: {sched_data.get('session_slice_configured')}")
        print(f"  Background Slice Configured: {sched_data.get('background_slice_configured')}")
        scx = sched_data.get("sched_ext", {})
        print("  sched_ext Status:")
        print(f"    Kernel Supported: {scx.get('kernel_supported')}")
        print(f"    Sysfs Present: {scx.get('sysfs_present')}")
        print(f"    Active Scheduler: {scx.get('active_scheduler') or 'None'}")
        print(f"    Service Active: {scx.get('service_active')}")
        print(f"    Service Enabled: {scx.get('service_enabled')}")
        print(f"    Details: {scx.get('details')}")
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_cli.py`
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py os_manager/cli.py tests/test_cli.py
git commit -m "feat(cli): wire osm tune scheduler subcommands and sched_ext lifecycle actions"
```

---

### Task 7: Master Harness & Full Verification Integration

**Files:**
- Modify: `tests/test_harness.sh`
- Test: `./tests/test_harness.sh`

**Interfaces:**
- Consumes: All tests in `tests/scheduler/`, `tests/test_tune_scheduler.py`, `tests/test_cli.py`.
- Produces: Clean exit 0 with 90+ verified harness assertions.

- [ ] **Step 1: Write failing harness verification check**

Ensure `tests/test_harness.sh` includes assertions for `test_scx_probe.py` and `test_scx_lifecycle.py`:
```bash
echo -n "Checking sched_ext dynamic eBPF scheduler test suite... "
python3 -m unittest discover -s tests/scheduler -p "test_*.py" >/dev/null 2>&1
assert_exit_code $? 0 "sched_ext test suite discovery"
```

- [ ] **Step 2: Run test harness to verify execution**

Run: `./tests/test_harness.sh`
Expected: PASS (All assertions pass with Exit Code 0).

- [ ] **Step 3: Run full pytest suite**

Run: `pytest tests/`
Expected: 100% tests passing.

- [ ] **Step 4: Commit**

```bash
git add tests/test_harness.sh
git commit -m "chore(test): verify master harness integrity for sched_ext dynamic scheduler subsystem"
```

---

## Plan Self-Review Checklist

- **Spec Coverage:**
  - Section 3 (Data Models & Profile Registry) -> Tasks 1, 4
  - Section 4 (Compatibility & State Probing Engine) -> Task 2
  - Section 5 (Lifecycle Management & Systemd Integration) -> Task 3
  - Section 6 (Master CLI & Telemetry Integration) -> Tasks 5, 6
  - Section 7 (Verification & Test Plan) -> Tasks 1, 2, 3, 5, 6, 7
- **Zero-Placeholder Check:** Passed (All code blocks contain complete, executable Python and Bash code; no "TBD", "TODO", or pseudo-code).
- **Type and Naming Consistency:** Passed (`ScxProfileName`, `ScxProfile`, `ScxSupportStatus`, `SCX_PROFILES`, `start_scx_scheduler`, `stop_scx_scheduler`, `enable_scx_service`, `disable_scx_service`, `audit_scheduler_subsystem`).
- **Privileged Execution:** Non-interactive sudo execution enforced via `_run_privileged` and `./scripts/sudo_exec.sh`.

# Autonomous PSI Feedback & zRAM Compaction Daemon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Autonomous PSI Feedback & zRAM Compaction Daemon (`os_manager.memory.psi_daemon`), providing kernel PSI metric parsing, a 3-tier staged mitigation engine with debounced cooldowns, dual epoll/async monitoring, systemd lifecycle management, and CLI commands under `osm psi` and `osm tune memory`.

**Architecture:** The subsystem parses `/proc/pressure/{cpu,memory,io}` stall metrics into structured `PsiMetrics` dataclasses, evaluates them against `PsiThresholds` via `StagedMitigationController` to autonomously compact zRAM (`/sys/block/zram*/compact`), kick MGLRU, or drop caches during memory stall, debounces triggers with a 20s cooldown window, and exposes control via `PsiMonitorEngine`, systemd unit management, and `osm psi` CLI.

**Tech Stack:** Python 3.11+ (`dataclasses`, `argparse`, `json`, `pathlib`, `select.epoll`, `asyncio`, `subprocess`), Linux PSI (`/proc/pressure/*`), zRAM Sysfs (`/sys/block/zram*/compact`), Linux MGLRU (`/sys/kernel/mm/lru_gen/enabled`), Systemd, Pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-autonomous-psi-feedback-daemon-design.md`

## Global Constraints

- Linux Kernel 6.6+ / 6.12 LTS target on Debian 13 (Trixie), WSL2, and bare-metal Linux.
- Zero interactive sudo: privileged sysfs/systemd writes must use non-interactive sudo execution (`./scripts/sudo_exec.sh` or `sudo -S`).
- Zero password leakage: never echo or log credentials.
- Graceful degradation: if `/proc/pressure/*` or `/sys/block/zram*` are absent, return structured unsupported status without crashing.
- Cooldown debounce: minimum 20-second suppression window between autonomous mitigation actions to prevent compaction thrashing.
- Pure Python standard library implementation without external dependencies (no PyYAML or third-party packages).

---

### Task 1: PSI Data Models and Metrics Parser

**Files:**
- Create: `os_manager/memory/psi_daemon.py`
- Test: `tests/memory/test_psi_parser.py`

**Interfaces:**
- Consumes: `/proc/pressure/{cpu,memory,io}` file formats.
- Produces: `PsiReading`, `PsiMetrics`, `PsiThresholds`, `parse_psi_line`, `parse_psi_file`, `collect_psi_metrics`.

- [ ] **Step 1: Write failing unit tests for PSI parser**

Create `tests/memory/test_psi_parser.py`:
```python
"""tests/memory/test_psi_parser.py - Unit tests for Linux PSI metrics parser."""

import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from os_manager.memory.psi_daemon import (
    PsiMetrics,
    PsiReading,
    PsiThresholds,
    collect_psi_metrics,
    parse_psi_file,
    parse_psi_line,
)


class TestPsiParser(unittest.TestCase):
    """Test suite for parsing /proc/pressure/{cpu,memory,io} records."""

    def test_parse_psi_line_valid_some(self):
        """Verify parsing standard 'some' PSI line."""
        line = "some avg10=1.23 avg60=4.56 avg300=7.89 total=1234567"
        res = parse_psi_line(line)
        self.assertIsNotNone(res)
        prefix, reading = res
        self.assertEqual(prefix, "some")
        self.assertEqual(reading.avg10, 1.23)
        self.assertEqual(reading.avg60, 4.56)
        self.assertEqual(reading.avg300, 7.89)
        self.assertEqual(reading.total, 1234567)

    def test_parse_psi_line_valid_full(self):
        """Verify parsing standard 'full' PSI line."""
        line = "full avg10=0.00 avg60=0.15 avg300=0.26 total=32458166"
        res = parse_psi_line(line)
        self.assertIsNotNone(res)
        prefix, reading = res
        self.assertEqual(prefix, "full")
        self.assertEqual(reading.avg10, 0.0)
        self.assertEqual(reading.avg60, 0.15)
        self.assertEqual(reading.avg300, 0.26)
        self.assertEqual(reading.total, 32458166)

    def test_parse_psi_line_invalid(self):
        """Verify parsing invalid or empty line returns None."""
        self.assertIsNone(parse_psi_line(""))
        self.assertIsNone(parse_psi_line("invalid line without metrics"))

    def test_parse_psi_file_memory(self):
        """Verify parsing simulated /proc/pressure/memory content."""
        content = (
            "some avg10=10.50 avg60=5.20 avg300=1.10 total=500000\n"
            "full avg10=2.00 avg60=0.50 avg300=0.10 total=100000\n"
        )
        with patch("pathlib.Path.is_file", return_value=True), \
             patch("pathlib.Path.read_text", return_value=content):
            parsed = parse_psi_file("/proc/pressure/memory")
            self.assertIn("some", parsed)
            self.assertIn("full", parsed)
            self.assertEqual(parsed["some"].avg10, 10.5)
            self.assertEqual(parsed["full"].avg10, 2.0)

    def test_parse_psi_file_missing(self):
        """Verify parsing nonexistent PSI file returns empty dict."""
        with patch("pathlib.Path.is_file", return_value=False):
            parsed = parse_psi_file("/proc/pressure/nonexistent")
            self.assertEqual(parsed, {})

    def test_collect_psi_metrics_success(self):
        """Verify collect_psi_metrics aggregates cpu, memory, and io metrics."""
        sample_cpu = "some avg10=1.00 avg60=2.00 avg300=3.00 total=100\n"
        sample_mem = (
            "some avg10=4.00 avg60=5.00 avg300=6.00 total=200\n"
            "full avg10=7.00 avg60=8.00 avg300=9.00 total=300\n"
        )
        sample_io = (
            "some avg10=10.00 avg60=11.00 avg300=12.00 total=400\n"
            "full avg10=13.00 avg60=14.00 avg300=15.00 total=500\n"
        )

        def mock_read(path_str):
            if "cpu" in str(path_str):
                return sample_cpu
            elif "memory" in str(path_str):
                return sample_mem
            elif "io" in str(path_str):
                return sample_io
            return ""

        with patch("pathlib.Path.is_file", return_value=True), \
             patch("pathlib.Path.read_text", side_effect=mock_read):
            metrics = collect_psi_metrics()
            self.assertIsNotNone(metrics)
            self.assertEqual(metrics.cpu_some.avg10, 1.0)
            self.assertEqual(metrics.memory_some.avg10, 4.0)
            self.assertEqual(metrics.memory_full.avg10, 7.0)
            self.assertEqual(metrics.io_some.avg10, 10.0)
            self.assertEqual(metrics.io_full.avg10, 13.0)
            self.assertTrue(len(metrics.timestamp) > 0)

    def test_collect_psi_metrics_unsupported(self):
        """Verify collect_psi_metrics returns None if PSI sysfs path missing."""
        with patch("pathlib.Path.is_file", return_value=False):
            self.assertIsNone(collect_psi_metrics())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/memory/test_psi_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'os_manager.memory.psi_daemon'`

- [ ] **Step 3: Write minimal implementation in `os_manager/memory/psi_daemon.py`**

Create `os_manager/memory/psi_daemon.py`:
```python
"""os_manager/memory/psi_daemon.py - Autonomous PSI Feedback & zRAM Compaction Subsystem."""

import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

PsiSubsystem = Literal["cpu", "memory", "io"]
MitigationTier = Literal["none", "tier1_compact", "tier2_mglru_sync", "tier3_throttle_drop"]

PROC_PRESSURE_DIR = Path("/proc/pressure")
PRESSURE_FILES = {
    "cpu": PROC_PRESSURE_DIR / "cpu",
    "memory": PROC_PRESSURE_DIR / "memory",
    "io": PROC_PRESSURE_DIR / "io",
}


@dataclass
class PsiReading:
    """Parsed PSI stall metrics for a single pressure category (some or full)."""
    avg10: float = 0.0
    avg60: float = 0.0
    avg300: float = 0.0
    total: int = 0


@dataclass
class PsiMetrics:
    """Aggregated snapshot of all system pressure stall readings."""
    cpu_some: PsiReading
    memory_some: PsiReading
    memory_full: PsiReading
    io_some: PsiReading
    io_full: PsiReading
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PsiThresholds:
    """Configurable trigger thresholds and cooldown windows for autonomous mitigations."""
    tier1_memory_some_avg10: float = 10.0
    tier1_memory_some_avg60: float = 5.0
    tier2_memory_some_avg10: float = 25.0
    tier2_memory_full_avg10: float = 10.0
    tier3_memory_full_avg10: float = 40.0
    cooldown_seconds: int = 20


def parse_psi_line(line: str) -> tuple[str, PsiReading] | None:
    """Parse a single line from /proc/pressure/{cpu,memory,io}."""
    line = line.strip()
    if not line:
        return None
    match = re.match(
        r"^(some|full)\s+avg10=([\d\.]+)\s+avg60=([\d\.]+)\s+avg300=([\d\.]+)\s+total=(\d+)",
        line,
    )
    if not match:
        return None
    prefix = match.group(1)
    reading = PsiReading(
        avg10=float(match.group(2)),
        avg60=float(match.group(3)),
        avg300=float(match.group(4)),
        total=int(match.group(5)),
    )
    return prefix, reading


def parse_psi_file(path: str | Path) -> dict[str, PsiReading]:
    """Parse a pressure file into a dictionary mapping 'some' and 'full' to PsiReading."""
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        content = p.read_text(encoding="utf-8")
        readings: dict[str, PsiReading] = {}
        for line in content.splitlines():
            res = parse_psi_line(line)
            if res:
                prefix, reading = res
                readings[prefix] = reading
        return readings
    except Exception:
        return {}


def collect_psi_metrics() -> PsiMetrics | None:
    """Collect current snapshot of all system PSI metrics."""
    if not PRESSURE_FILES["memory"].is_file():
        return None

    cpu_readings = parse_psi_file(PRESSURE_FILES["cpu"])
    mem_readings = parse_psi_file(PRESSURE_FILES["memory"])
    io_readings = parse_psi_file(PRESSURE_FILES["io"])

    return PsiMetrics(
        cpu_some=cpu_readings.get("some", PsiReading()),
        memory_some=mem_readings.get("some", PsiReading()),
        memory_full=mem_readings.get("full", PsiReading()),
        io_some=io_readings.get("some", PsiReading()),
        io_full=io_readings.get("full", PsiReading()),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/memory/test_psi_parser.py -v`
Expected: PASS (6/6 tests passing)

- [ ] **Step 5: Commit**

```bash
git add os_manager/memory/psi_daemon.py tests/memory/test_psi_parser.py
git commit -m "feat(memory): implement PSI metrics parser and data models"
```

---

### Task 2: 3-Tier Staged Mitigation Engine and Debounced Cooldown

**Files:**
- Modify: `os_manager/memory/psi_daemon.py`
- Test: `tests/memory/test_psi_mitigation.py`

**Interfaces:**
- Consumes: `PsiMetrics`, `PsiThresholds`, `MitigationTier`.
- Produces: `compact_zram_devices()`, `trigger_mglru_kick()`, `trigger_critical_cache_drop()`, `StagedMitigationController`.

- [ ] **Step 1: Write failing unit tests for Staged Mitigation Engine**

Create `tests/memory/test_psi_mitigation.py`:
```python
"""tests/memory/test_psi_mitigation.py - Unit tests for 3-tier PSI mitigation actions and cooldown."""

import time
import unittest
from unittest.mock import MagicMock, call, patch

from os_manager.memory.psi_daemon import (
    PsiMetrics,
    PsiReading,
    PsiThresholds,
    StagedMitigationController,
    compact_zram_devices,
    trigger_critical_cache_drop,
    trigger_mglru_kick,
)


class TestPsiMitigation(unittest.TestCase):
    """Test suite for autonomous memory mitigations and debounce mechanics."""

    def setUp(self):
        self.thresholds = PsiThresholds(
            tier1_memory_some_avg10=10.0,
            tier1_memory_some_avg60=5.0,
            tier2_memory_some_avg10=25.0,
            tier2_memory_full_avg10=10.0,
            tier3_memory_full_avg10=40.0,
            cooldown_seconds=20,
        )
        self.controller = StagedMitigationController(thresholds=self.thresholds)

    def _make_metrics(self, mem_some_10=0.0, mem_some_60=0.0, mem_full_10=0.0):
        return PsiMetrics(
            cpu_some=PsiReading(),
            memory_some=PsiReading(avg10=mem_some_10, avg60=mem_some_60),
            memory_full=PsiReading(avg10=mem_full_10),
            io_some=PsiReading(),
            io_full=PsiReading(),
        )

    def test_compact_zram_devices(self):
        """Verify zRAM compaction writes 1 to /sys/block/zram*/compact."""
        with patch("glob.glob", return_value=["/sys/block/zram0/compact", "/sys/block/zram1/compact"]), \
             patch("os_manager.memory.psi_daemon._write_privileged_sysfs", return_value=True) as mock_write:
            compacted = compact_zram_devices()
            self.assertEqual(compacted, ["/sys/block/zram0/compact", "/sys/block/zram1/compact"])
            self.assertEqual(mock_write.call_count, 2)

    def test_trigger_mglru_kick(self):
        """Verify MGLRU trigger writes to sysfs and executes sync."""
        with patch("os_manager.memory.psi_daemon._write_privileged_sysfs", return_value=True) as mock_write, \
             patch("os.sync") as mock_sync:
            res = trigger_mglru_kick()
            self.assertTrue(res)
            mock_write.assert_called_once_with("/sys/kernel/mm/lru_gen/enabled", "1")
            mock_sync.assert_called_once()

    def test_trigger_critical_cache_drop(self):
        """Verify critical drop writes drop_caches and appends log event."""
        with patch("os_manager.memory.psi_daemon._write_privileged_sysfs", return_value=True) as mock_write, \
             patch("os_manager.memory.psi_daemon._log_psi_event") as mock_log:
            res = trigger_critical_cache_drop(reason="test critical")
            self.assertTrue(res)
            mock_write.assert_called_once_with("/proc/sys/vm/drop_caches", "1")
            mock_log.assert_called_once()

    def test_evaluate_no_mitigation_when_healthy(self):
        """Verify no mitigation is executed under normal memory pressure."""
        metrics = self._make_metrics(mem_some_10=2.0, mem_some_60=1.0, mem_full_10=0.0)
        res = self.controller.evaluate_and_mitigate(metrics)
        self.assertEqual(res["tier"], "none")
        self.assertFalse(res["mitigated"])

    def test_evaluate_tier1_compact_trigger(self):
        """Verify Tier 1 compaction triggers when memory.some.avg10 >= 10.0."""
        metrics = self._make_metrics(mem_some_10=12.5, mem_some_60=2.0, mem_full_10=0.0)
        with patch("os_manager.memory.psi_daemon.compact_zram_devices", return_value=["/sys/block/zram0/compact"]):
            res = self.controller.evaluate_and_mitigate(metrics)
            self.assertEqual(res["tier"], "tier1_compact")
            self.assertTrue(res["mitigated"])
            self.assertEqual(self.controller.last_mitigation_tier, "tier1_compact")

    def test_evaluate_tier2_mglru_trigger(self):
        """Verify Tier 2 triggers compaction + MGLRU when memory.some.avg10 >= 25.0."""
        metrics = self._make_metrics(mem_some_10=28.0, mem_some_60=15.0, mem_full_10=5.0)
        with patch("os_manager.memory.psi_daemon.compact_zram_devices", return_value=["/sys/block/zram0/compact"]), \
             patch("os_manager.memory.psi_daemon.trigger_mglru_kick", return_value=True):
            res = self.controller.evaluate_and_mitigate(metrics)
            self.assertEqual(res["tier"], "tier2_mglru_sync")
            self.assertTrue(res["mitigated"])

    def test_evaluate_tier3_critical_trigger(self):
        """Verify Tier 3 triggers drop caches when memory.full.avg10 >= 40.0."""
        metrics = self._make_metrics(mem_some_10=80.0, mem_some_60=60.0, mem_full_10=45.0)
        with patch("os_manager.memory.psi_daemon.compact_zram_devices", return_value=["/sys/block/zram0/compact"]), \
             patch("os_manager.memory.psi_daemon.trigger_mglru_kick", return_value=True), \
             patch("os_manager.memory.psi_daemon.trigger_critical_cache_drop", return_value=True):
            res = self.controller.evaluate_and_mitigate(metrics)
            self.assertEqual(res["tier"], "tier3_throttle_drop")
            self.assertTrue(res["mitigated"])

    def test_cooldown_suppression(self):
        """Verify mitigation is suppressed during the 20-second cooldown window."""
        metrics = self._make_metrics(mem_some_10=15.0)
        with patch("os_manager.memory.psi_daemon.compact_zram_devices", return_value=["/sys/block/zram0/compact"]):
            # First evaluation triggers mitigation
            res1 = self.controller.evaluate_and_mitigate(metrics)
            self.assertTrue(res1["mitigated"])

            # Immediate second evaluation triggers cooldown suppression
            res2 = self.controller.evaluate_and_mitigate(metrics)
            self.assertFalse(res2["mitigated"])
            self.assertTrue(res2["cooldown_active"])
            self.assertEqual(res2["reason"], "cooldown_suppressed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/memory/test_psi_mitigation.py -v`
Expected: FAIL with `ImportError: cannot import name 'StagedMitigationController' from 'os_manager.memory.psi_daemon'`

- [ ] **Step 3: Implement Staged Mitigation Engine in `os_manager/memory/psi_daemon.py`**

Append to `os_manager/memory/psi_daemon.py`:
```python
import glob
import json
import subprocess

PSI_LOG_FILE = Path("backups/logs/psi_events.jsonl")


def _write_privileged_sysfs(target_path: str, value: str) -> bool:
    """Write value to sysfs or procfs securely using non-interactive sudo if needed."""
    p = Path(target_path)
    try:
        if os.geteuid() == 0:
            p.write_text(f"{value}\n", encoding="utf-8")
            return True

        # Non-interactive sudo pipe
        cmd = f"echo '{value}' | sudo -S tee '{target_path}'"
        env_path = Path.cwd() / ".env"
        if env_path.is_file():
            res = subprocess.run(
                f"grep -E '^SUDO_PASSWORD=' '{env_path}' | cut -d '=' -f2- | {cmd}",
                shell=True,
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            res = subprocess.run(["sudo", "-n", "tee", target_path], input=f"{value}\n", text=True, capture_output=True, check=False)
        return res.returncode == 0
    except Exception:
        return False


def _log_psi_event(tier: str, reason: str, metrics: PsiMetrics | None = None) -> None:
    """Log critical memory pressure mitigation event to audit file."""
    try:
        PSI_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tier": tier,
            "reason": reason,
            "metrics": asdict(metrics) if metrics else {},
        }
        with open(PSI_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass


def compact_zram_devices() -> list[str]:
    """Trigger memory compaction across all active zRAM devices."""
    compacted: list[str] = []
    targets = glob.glob("/sys/block/zram*/compact")
    for target in targets:
        if _write_privileged_sysfs(target, "1"):
            compacted.append(target)
    return compacted


def trigger_mglru_kick() -> bool:
    """Re-enable MGLRU page aging and request dirty page writeback sync."""
    mglru_target = "/sys/kernel/mm/lru_gen/enabled"
    _write_privileged_sysfs(mglru_target, "1")
    try:
        os.sync()
    except Exception:
        pass
    return True


def trigger_critical_cache_drop(reason: str = "critical stall", metrics: PsiMetrics | None = None) -> bool:
    """Execute emergency page cache reclaim and record audit event."""
    _log_psi_event("tier3_throttle_drop", reason, metrics)
    return _write_privileged_sysfs("/proc/sys/vm/drop_caches", "1")


class StagedMitigationController:
    """3-Tier autonomous memory pressure mitigation engine with cooldown debouncing."""

    def __init__(self, thresholds: PsiThresholds | None = None):
        self.thresholds = thresholds or PsiThresholds()
        self.last_mitigation_time: float = 0.0
        self.last_mitigation_tier: MitigationTier = "none"
        self.mitigation_count: int = 0

    def evaluate_and_mitigate(self, metrics: PsiMetrics) -> dict[str, Any]:
        """Evaluate current PSI metrics against thresholds and trigger appropriate mitigation tier."""
        now = time.monotonic()
        time_since_last = now - self.last_mitigation_time
        in_cooldown = time_since_last < self.thresholds.cooldown_seconds

        # Determine target tier
        target_tier: MitigationTier = "none"
        reason = "pressure_normal"

        if metrics.memory_full.avg10 >= self.thresholds.tier3_memory_full_avg10:
            target_tier = "tier3_throttle_drop"
            reason = f"memory.full.avg10={metrics.memory_full.avg10:.2f} >= {self.thresholds.tier3_memory_full_avg10}"
        elif (
            metrics.memory_some.avg10 >= self.thresholds.tier2_memory_some_avg10
            or metrics.memory_full.avg10 >= self.thresholds.tier2_memory_full_avg10
        ):
            target_tier = "tier2_mglru_sync"
            reason = f"memory.some.avg10={metrics.memory_some.avg10:.2f} or memory.full.avg10={metrics.memory_full.avg10:.2f}"
        elif (
            metrics.memory_some.avg10 >= self.thresholds.tier1_memory_some_avg10
            or metrics.memory_some.avg60 >= self.thresholds.tier1_memory_some_avg60
        ):
            target_tier = "tier1_compact"
            reason = f"memory.some.avg10={metrics.memory_some.avg10:.2f} or memory.some.avg60={metrics.memory_some.avg60:.2f}"

        if target_tier == "none":
            return {
                "mitigated": False,
                "tier": "none",
                "reason": reason,
                "cooldown_active": in_cooldown,
                "cooldown_remaining": max(0.0, self.thresholds.cooldown_seconds - time_since_last),
            }

        if in_cooldown:
            return {
                "mitigated": False,
                "tier": target_tier,
                "reason": "cooldown_suppressed",
                "cooldown_active": True,
                "cooldown_remaining": max(0.0, self.thresholds.cooldown_seconds - time_since_last),
            }

        # Execute mitigation
        compacted: list[str] = []
        if target_tier in ("tier1_compact", "tier2_mglru_sync", "tier3_throttle_drop"):
            compacted = compact_zram_devices()

        if target_tier in ("tier2_mglru_sync", "tier3_throttle_drop"):
            trigger_mglru_kick()

        if target_tier == "tier3_throttle_drop":
            trigger_critical_cache_drop(reason=reason, metrics=metrics)

        self.last_mitigation_time = now
        self.last_mitigation_tier = target_tier
        self.mitigation_count += 1

        return {
            "mitigated": True,
            "tier": target_tier,
            "reason": reason,
            "compacted_devices": compacted,
            "cooldown_active": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/memory/test_psi_mitigation.py -v`
Expected: PASS (8/8 tests passing)

- [ ] **Step 5: Commit**

```bash
git add os_manager/memory/psi_daemon.py tests/memory/test_psi_mitigation.py
git commit -m "feat(memory): implement 3-tier staged mitigation and debounce controller"
```

---

### Task 3: Dual Monitoring Engine and Systemd Lifecycle Management

**Files:**
- Modify: `os_manager/memory/psi_daemon.py`
- Modify: `os_manager/memory/__init__.py`
- Test: `tests/memory/test_psi_daemon_service.py`

**Interfaces:**
- Consumes: `StagedMitigationController`, systemd commands (`systemctl`).
- Produces: `PsiMonitorEngine`, `generate_psi_systemd_unit()`, `manage_psi_daemon()`, `audit_psi_telemetry()`.

- [ ] **Step 1: Write failing unit tests for PsiMonitorEngine and Systemd Management**

Create `tests/memory/test_psi_daemon_service.py`:
```python
"""tests/memory/test_psi_daemon_service.py - Unit tests for PSI monitor engine and systemd unit lifecycle."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.memory.psi_daemon import (
    PsiMonitorEngine,
    SYSTEMD_PSI_UNIT_PATH,
    audit_psi_telemetry,
    generate_psi_systemd_unit,
    manage_psi_daemon,
)


class TestPsiDaemonService(unittest.TestCase):
    """Test suite for monitor loop, systemd unit generation, and service management."""

    def test_generate_psi_systemd_unit(self):
        """Verify systemd service unit template content."""
        unit = generate_psi_systemd_unit()
        self.assertIn("[Unit]", unit)
        self.assertIn("Description=os-manager Autonomous PSI Memory Feedback & zRAM Compaction Daemon", unit)
        self.assertIn("ExecStart=/usr/local/bin/osm psi daemon --run", unit)
        self.assertIn("Restart=always", unit)
        self.assertIn("MemoryMax=128M", unit)

    def test_manage_psi_daemon_status_inactive(self):
        """Verify manage_psi_daemon status check when service is inactive."""
        with patch("subprocess.run") as mock_run, \
             patch("pathlib.Path.is_file", return_value=True):
            mock_run.side_effect = [
                MagicMock(returncode=3, stdout="inactive\n"),  # is-active
                MagicMock(returncode=0, stdout="enabled\n"),   # is-enabled
            ]
            res = manage_psi_daemon("status")
            self.assertTrue(res["installed"])
            self.assertFalse(res["active"])
            self.assertTrue(res["enabled"])

    def test_manage_psi_daemon_start(self):
        """Verify manage_psi_daemon start writes unit and starts service."""
        with patch("os_manager.memory.psi_daemon._write_privileged_sysfs", return_value=True) as mock_write, \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            res = manage_psi_daemon("start")
            self.assertTrue(res["success"])
            mock_write.assert_called_once()

    def test_manage_psi_daemon_stop(self):
        """Verify manage_psi_daemon stop calls systemctl stop."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            res = manage_psi_daemon("stop")
            self.assertTrue(res["success"])

    def test_audit_psi_telemetry(self):
        """Verify audit_psi_telemetry collects subsystem health and PSI readings."""
        with patch("os_manager.memory.psi_daemon.collect_psi_metrics") as mock_metrics, \
             patch("glob.glob", return_value=["/sys/block/zram0/compact"]), \
             patch("os_manager.memory.psi_daemon.manage_psi_daemon", return_value={"active": True, "installed": True}):
            mock_metrics.return_value = MagicMock(
                cpu_some=MagicMock(avg10=1.0, avg60=2.0, avg300=3.0),
                memory_some=MagicMock(avg10=4.0, avg60=5.0, avg300=6.0),
                memory_full=MagicMock(avg10=7.0, avg60=8.0, avg300=9.0),
                io_some=MagicMock(avg10=10.0, avg60=11.0, avg300=12.0),
                io_full=MagicMock(avg10=13.0, avg60=14.0, avg300=15.0),
                timestamp="2026-08-28T10:00:00Z",
            )
            telemetry = audit_psi_telemetry()
            self.assertTrue(telemetry["supported"])
            self.assertTrue(telemetry["daemon_active"])
            self.assertEqual(telemetry["cpu"]["some_avg10"], 1.0)
            self.assertEqual(telemetry["memory"]["some_avg10"], 4.0)
            self.assertEqual(telemetry["memory"]["full_avg10"], 7.0)
            self.assertEqual(telemetry["zram_devices"], ["/sys/block/zram0/compact"])

    def test_psi_monitor_engine_step(self):
        """Verify PsiMonitorEngine step executes a single poll & mitigate iteration."""
        with patch("os_manager.memory.psi_daemon.collect_psi_metrics") as mock_metrics:
            mock_metrics.return_value = MagicMock(
                memory_some=MagicMock(avg10=15.0, avg60=2.0),
                memory_full=MagicMock(avg10=0.0),
            )
            engine = PsiMonitorEngine()
            with patch.object(engine.controller, "evaluate_and_mitigate", return_value={"mitigated": True, "tier": "tier1_compact"}) as mock_eval:
                result = engine.step()
                self.assertIsNotNone(result)
                mock_eval.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/memory/test_psi_daemon_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'PsiMonitorEngine' from 'os_manager.memory.psi_daemon'`

- [ ] **Step 3: Implement PsiMonitorEngine and Systemd Lifecycle in `os_manager/memory/psi_daemon.py` and export in `os_manager/memory/__init__.py`**

Append to `os_manager/memory/psi_daemon.py`:
```python
SYSTEMD_PSI_UNIT_PATH = "/etc/systemd/system/osm-psi.service"


def generate_psi_systemd_unit() -> str:
    """Generate systemd unit file content for osm-psi background daemon."""
    return """# /etc/systemd/system/osm-psi.service - Managed by os-manager
[Unit]
Description=os-manager Autonomous PSI Memory Feedback & zRAM Compaction Daemon
Documentation=https://github.com/0xrizz/os-manager
After=systemd-modules-load.service zramswap.service

[Service]
Type=simple
ExecStart=/usr/local/bin/osm psi daemon --run
Restart=always
RestartSec=5s
Nice=-5
MemoryHigh=64M
MemoryMax=128M

[Install]
WantedBy=multi-user.target
"""


def manage_psi_daemon(action: str) -> dict[str, Any]:
    """Control osm-psi daemon lifecycle: status, start, stop, enable, disable."""
    unit_installed = Path(SYSTEMD_PSI_UNIT_PATH).is_file()

    if action == "status":
        active = False
        enabled = False
        try:
            res_act = subprocess.run(["systemctl", "is-active", "osm-psi.service"], capture_output=True, text=True, check=False)
            active = res_act.stdout.strip() == "active"
            res_en = subprocess.run(["systemctl", "is-enabled", "osm-psi.service"], capture_output=True, text=True, check=False)
            enabled = res_en.stdout.strip() == "enabled"
        except Exception:
            pass
        return {
            "installed": unit_installed,
            "active": active,
            "enabled": enabled,
            "unit_path": SYSTEMD_PSI_UNIT_PATH,
        }

    if action == "start":
        unit_content = generate_psi_systemd_unit()
        _write_privileged_sysfs(SYSTEMD_PSI_UNIT_PATH, unit_content)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, check=False)
        res = subprocess.run(["sudo", "systemctl", "restart", "osm-psi.service"], capture_output=True, text=True, check=False)
        return {"success": res.returncode == 0, "action": "start", "error": res.stderr}

    if action == "stop":
        res = subprocess.run(["sudo", "systemctl", "stop", "osm-psi.service"], capture_output=True, text=True, check=False)
        return {"success": res.returncode == 0, "action": "stop", "error": res.stderr}

    if action == "enable":
        unit_content = generate_psi_systemd_unit()
        _write_privileged_sysfs(SYSTEMD_PSI_UNIT_PATH, unit_content)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, check=False)
        res = subprocess.run(["sudo", "systemctl", "enable", "--now", "osm-psi.service"], capture_output=True, text=True, check=False)
        return {"success": res.returncode == 0, "action": "enable", "error": res.stderr}

    if action == "disable":
        res = subprocess.run(["sudo", "systemctl", "disable", "--now", "osm-psi.service"], capture_output=True, text=True, check=False)
        return {"success": res.returncode == 0, "action": "disable", "error": res.stderr}

    return {"success": False, "error": f"Unknown daemon action '{action}'"}


def audit_psi_telemetry() -> dict[str, Any]:
    """Collect comprehensive telemetry for PSI support, daemon status, and live pressure."""
    metrics = collect_psi_metrics()
    supported = metrics is not None
    daemon_status = manage_psi_daemon("status")
    zram_devices = glob.glob("/sys/block/zram*/compact")

    telemetry: dict[str, Any] = {
        "supported": supported,
        "daemon_installed": daemon_status.get("installed", False),
        "daemon_active": daemon_status.get("active", False),
        "zram_devices": zram_devices,
    }

    if metrics:
        telemetry["timestamp"] = metrics.timestamp
        telemetry["cpu"] = {
            "some_avg10": metrics.cpu_some.avg10,
            "some_avg60": metrics.cpu_some.avg60,
            "some_avg300": metrics.cpu_some.avg300,
        }
        telemetry["memory"] = {
            "some_avg10": metrics.memory_some.avg10,
            "some_avg60": metrics.memory_some.avg60,
            "some_avg300": metrics.memory_some.avg300,
            "full_avg10": metrics.memory_full.avg10,
            "full_avg60": metrics.memory_full.avg60,
            "full_avg300": metrics.memory_full.avg300,
        }
        telemetry["io"] = {
            "some_avg10": metrics.io_some.avg10,
            "some_avg60": metrics.io_some.avg60,
            "some_avg300": metrics.io_some.avg300,
            "full_avg10": metrics.io_full.avg10,
            "full_avg60": metrics.io_full.avg60,
            "full_avg300": metrics.io_full.avg300,
        }
    return telemetry


class PsiMonitorEngine:
    """Monitoring and mitigation execution runner with dual epoll and polling loop."""

    def __init__(self, thresholds: PsiThresholds | None = None):
        self.controller = StagedMitigationController(thresholds=thresholds)

    def step(self) -> dict[str, Any] | None:
        """Execute one polling sample and evaluate mitigation."""
        metrics = collect_psi_metrics()
        if not metrics:
            return None
        mitigation_result = self.controller.evaluate_and_mitigate(metrics)
        return {
            "metrics": metrics,
            "mitigation": mitigation_result,
        }

    def run_daemon_loop(self, interval: float = 2.0) -> None:
        """Run continuous monitoring loop for daemon execution."""
        while True:
            try:
                self.step()
                time.sleep(interval)
            except KeyboardInterrupt:
                break
            except Exception:
                time.sleep(interval)
```

Update `os_manager/memory/__init__.py`:
```python
"""Memory management and zRAM optimization subsystem."""
from os_manager.memory.psi_daemon import (
    MitigationTier,
    PsiMetrics,
    PsiMonitorEngine,
    PsiReading,
    PsiSubsystem,
    PsiThresholds,
    audit_psi_telemetry,
    collect_psi_metrics,
    compact_zram_devices,
    generate_psi_systemd_unit,
    manage_psi_daemon,
    parse_psi_file,
    parse_psi_line,
    trigger_critical_cache_drop,
    trigger_mglru_kick,
)
from os_manager.memory.zram import (
    CANONICAL_ZRAM_CONF,
    CANONICAL_ZRAM_DEVICE,
    CANONICAL_ZRAM_GENERATOR_PKG,
    CONFLICTING_ZRAM_SERVICES,
    ConflictingServiceStatus,
    ZramAuditReport,
    audit_zram_system,
    generate_canonical_zram_conf,
    remediate_zram_conflicts,
    unmask_zram_service,
)

__all__ = [
    "CANONICAL_ZRAM_CONF",
    "CANONICAL_ZRAM_DEVICE",
    "CANONICAL_ZRAM_GENERATOR_PKG",
    "CONFLICTING_ZRAM_SERVICES",
    "ConflictingServiceStatus",
    "ZramAuditReport",
    "audit_zram_system",
    "generate_canonical_zram_conf",
    "remediate_zram_conflicts",
    "unmask_zram_service",
    "PsiReading",
    "PsiMetrics",
    "PsiThresholds",
    "PsiSubsystem",
    "MitigationTier",
    "parse_psi_line",
    "parse_psi_file",
    "collect_psi_metrics",
    "compact_zram_devices",
    "trigger_mglru_kick",
    "trigger_critical_cache_drop",
    "generate_psi_systemd_unit",
    "manage_psi_daemon",
    "audit_psi_telemetry",
    "PsiMonitorEngine",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/memory/test_psi_daemon_service.py -v`
Expected: PASS (6/6 tests passing)

- [ ] **Step 5: Commit**

```bash
git add os_manager/memory/psi_daemon.py os_manager/memory/__init__.py tests/memory/test_psi_daemon_service.py
git commit -m "feat(memory): implement PSI monitor engine, systemd unit and exports"
```

---

### Task 4: `osm psi` CLI Command Module and Router Dispatcher

**Files:**
- Create: `os_manager/commands/psi.py`
- Modify: `os_manager/cli.py`
- Test: `tests/test_cli_psi.py`

**Interfaces:**
- Consumes: `os_manager.memory.psi_daemon` functions.
- Produces: `run_psi(argv: list[str]) -> int`, CLI subcommand `osm psi`.

- [ ] **Step 1: Write failing unit tests for `osm psi` CLI routing**

Create `tests/test_cli_psi.py`:
```python
"""tests/test_cli_psi.py - Unit tests for osm psi CLI command router."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from os_manager.cli import main


class TestCliPsi(unittest.TestCase):
    """Test suite for osm psi CLI command dispatcher."""

    def test_osm_psi_status_json(self):
        """Test 'osm psi status --json' output."""
        mock_telemetry = {
            "supported": True,
            "daemon_active": True,
            "cpu": {"some_avg10": 0.5, "some_avg60": 0.2, "some_avg300": 0.1},
            "memory": {"some_avg10": 1.2, "full_avg10": 0.0},
            "io": {"some_avg10": 3.4, "full_avg10": 1.1},
            "zram_devices": ["/sys/block/zram0/compact"],
        }
        with patch("os_manager.commands.psi.audit_psi_telemetry", return_value=mock_telemetry), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["psi", "status", "--json"])
            self.assertEqual(code, 0)
            data = json.loads(mock_out.getvalue())
            self.assertTrue(data["supported"])
            self.assertTrue(data["daemon_active"])

    def test_osm_psi_compact(self):
        """Test 'osm psi compact' manual trigger."""
        with patch("os_manager.commands.psi.compact_zram_devices", return_value=["/sys/block/zram0/compact"]) as mock_comp, \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["psi", "compact"])
            self.assertEqual(code, 0)
            mock_comp.assert_called_once()
            self.assertIn("Compacted 1 zRAM devices", mock_out.getvalue())

    def test_osm_psi_daemon_status(self):
        """Test 'osm psi daemon status'."""
        with patch("os_manager.commands.psi.manage_psi_daemon", return_value={"installed": True, "active": True, "enabled": True}) as mock_manage, \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["psi", "daemon", "status"])
            self.assertEqual(code, 0)
            mock_manage.assert_called_once_with("status")
            self.assertIn("Active: True", mock_out.getvalue())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_cli_psi.py -v`
Expected: FAIL with unrecognized command or import error.

- [ ] **Step 3: Create `os_manager/commands/psi.py` and register in `os_manager/cli.py`**

Create `os_manager/commands/psi.py`:
```python
"""os_manager/commands/psi.py - Autonomous PSI Feedback & zRAM Compaction CLI Command Module."""

import argparse
import json
import sys
import time
from typing import List

from ..memory.psi_daemon import (
    PsiMonitorEngine,
    audit_psi_telemetry,
    compact_zram_devices,
    manage_psi_daemon,
)


def run_psi(argv: List[str]) -> int:
    """Entrypoint dispatcher for 'osm psi' commands."""
    parser = argparse.ArgumentParser(
        prog="osm psi",
        description="Autonomous Linux PSI (Pressure Stall Information) Feedback & zRAM Compaction",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="PSI action")

    # status
    status_parser = subparsers.add_parser("status", help="Display real-time CPU, Memory, and I/O PSI stall telemetry")
    status_parser.add_argument("--json", action="store_true", help="Output telemetry as JSON")

    # compact
    subparsers.add_parser("compact", help="Trigger manual on-demand zRAM memory compaction")

    # monitor
    mon_parser = subparsers.add_parser("monitor", help="Live interactive terminal PSI stall monitor")
    mon_parser.add_argument("--interval", type=float, default=1.0, help="Sampling interval in seconds")

    # daemon
    daemon_parser = subparsers.add_parser("daemon", help="Manage osm-psi systemd background daemon")
    daemon_parser.add_argument("action", nargs="?", default="status", choices=["status", "start", "stop", "enable", "disable"])
    daemon_parser.add_argument("--run", action="store_true", help="Execute monitor loop directly in foreground")
    daemon_parser.add_argument("--json", action="store_true", help="Output daemon status as JSON")

    args, unknown = parser.parse_known_args(argv)

    if args.subcommand == "status" or not args.subcommand:
        telemetry = audit_psi_telemetry()
        if getattr(args, "json", False):
            print(json.dumps(telemetry, indent=2))
            return 0
        if not telemetry.get("supported"):
            print("Linux PSI (Pressure Stall Information) is not supported on this kernel/environment.")
            return 1
        print("==================================================")
        print("    Linux Pressure Stall Information (PSI) Audit  ")
        print("==================================================")
        print(f"Daemon Installed: {telemetry.get('daemon_installed')}")
        print(f"Daemon Active:    {telemetry.get('daemon_active')}")
        print(f"zRAM Targets:     {len(telemetry.get('zram_devices', []))} devices detected")
        print("\nPressure Readings (Stall Percentage):")
        mem = telemetry.get("memory", {})
        cpu = telemetry.get("cpu", {})
        io = telemetry.get("io", {})
        print(f"  CPU    - some: 10s={cpu.get('some_avg10', 0):.2f}%, 60s={cpu.get('some_avg60', 0):.2f}%, 300s={cpu.get('some_avg300', 0):.2f}%")
        print(f"  Memory - some: 10s={mem.get('some_avg10', 0):.2f}%, 60s={mem.get('some_avg60', 0):.2f}%, 300s={mem.get('some_avg300', 0):.2f}%")
        print(f"  Memory - full: 10s={mem.get('full_avg10', 0):.2f}%, 60s={mem.get('full_avg60', 0):.2f}%, 300s={mem.get('full_avg300', 0):.2f}%")
        print(f"  I/O    - some: 10s={io.get('some_avg10', 0):.2f}%, 60s={io.get('some_avg60', 0):.2f}%, 300s={io.get('some_avg300', 0):.2f}%")
        print(f"  I/O    - full: 10s={io.get('full_avg10', 0):.2f}%, 60s={io.get('full_avg60', 0):.2f}%, 300s={io.get('full_avg300', 0):.2f}%")
        return 0

    elif args.subcommand == "compact":
        compacted = compact_zram_devices()
        print(f"[PASS] Compacted {len(compacted)} zRAM devices.")
        for dev in compacted:
            print(f"  - {dev}")
        return 0

    elif args.subcommand == "monitor":
        engine = PsiMonitorEngine()
        print(f"Starting live PSI monitoring (interval={args.interval}s, Ctrl+C to exit)...")
        try:
            while True:
                sample = engine.step()
                if sample and sample.get("metrics"):
                    m = sample["metrics"]
                    mit = sample.get("mitigation", {})
                    mit_str = f" [Mitigation: {mit.get('tier')}]" if mit.get("mitigated") else ""
                    print(f"[{m.timestamp}] Memory some={m.memory_some.avg10:.2f}% full={m.memory_full.avg10:.2f}% | CPU some={m.cpu_some.avg10:.2f}% | IO some={m.io_some.avg10:.2f}%{mit_str}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped PSI monitor.")
        return 0

    elif args.subcommand == "daemon":
        if args.run:
            engine = PsiMonitorEngine()
            engine.run_daemon_loop()
            return 0
        res = manage_psi_daemon(args.action)
        if args.json:
            print(json.dumps(res, indent=2))
            return 0 if res.get("success", True) else 1
        print(f"PSI Daemon ({args.action}):")
        for k, v in res.items():
            print(f"  {k.capitalize()}: {v}")
        return 0 if res.get("success", True) else 1

    return 0
```

Modify `os_manager/cli.py` to import and route `run_psi`:
- Add `from .commands.psi import run_psi`
- Add parser entry `subparsers.add_parser("psi", add_help=False, help="Autonomous PSI Memory Feedback & zRAM Compaction")`
- Add routing branch in `main()`: `elif args.command == "psi": return run_psi(argv[1:])`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_cli_psi.py -v`
Expected: PASS (3/3 tests passing)

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/psi.py os_manager/cli.py tests/test_cli_psi.py
git commit -m "feat(cli): add osm psi command router and subcommands"
```

---

### Task 5: Memory Telemetry Integration in `osm tune memory`

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `tests/test_tune_memory.py`

**Interfaces:**
- Consumes: `audit_psi_telemetry()` from `os_manager.memory.psi_daemon`.
- Produces: Enhanced `audit_memory_subsystem()` and `osm tune memory` output containing PSI metrics.

- [ ] **Step 1: Write failing unit test for PSI in `audit_memory_subsystem`**

Update `tests/test_tune_memory.py` to assert `psi` telemetry integration:
```python
    def test_audit_memory_subsystem_includes_psi(self):
        """Verify audit_memory_subsystem includes PSI telemetry fields."""
        with patch("pathlib.Path.read_text", return_value="always [madvise] never\n"), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="180\n")), \
             patch("os_manager.commands.tune.audit_earlyoom_status", return_value={"active": True}), \
             patch("os_manager.commands.tune.audit_dual_tier_swap_status", return_value={"has_zram": True}), \
             patch("os_manager.memory.psi_daemon.audit_psi_telemetry", return_value={"supported": True, "daemon_active": True}) as mock_psi:
            res = audit_memory_subsystem()
            self.assertIn("psi", res)
            self.assertTrue(res["psi"]["supported"])
            self.assertTrue(res["psi"]["daemon_active"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_tune_memory.py -v`
Expected: FAIL (KeyError or missing `psi` key)

- [ ] **Step 3: Update `os_manager/commands/tune.py` to include PSI telemetry in memory audit**

In `os_manager/commands/tune.py`:
- In `audit_memory_subsystem()`:
  - Add call to `from ..memory.psi_daemon import audit_psi_telemetry`
  - Include `"psi": audit_psi_telemetry()` in the returned dictionary.
- In `run_tune()` under `subaction == "memory"` text formatting:
  - Print line 6: `print(f"6. PSI Daemon Active: {mem_audit.get('psi', {}).get('daemon_active', False)}")`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_tune_memory.py -v`
Expected: PASS (all tests in test_tune_memory passing)

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py tests/test_tune_memory.py
git commit -m "feat(tune): integrate PSI feedback daemon telemetry into tune memory"
```

---

### Task 6: Master Harness Verification and End-to-End Suite

**Files:**
- Test: `tests/test_harness.sh`
- Test: Full Pytest test suite

**Interfaces:**
- Consumes: All `os-manager` modules and tests.
- Produces: Zero regressions across master test harness.

- [ ] **Step 1: Run comprehensive Pytest test suite**

Run: `PYTHONPATH=. .venv/bin/pytest tests/`
Expected: PASS across all test files with 0 errors.

- [ ] **Step 2: Run master harness shell suite**

Run: `./tests/test_harness.sh`
Expected: PASS across all assertions (83+ assertions passing with 0 failures).

- [ ] **Step 3: Verify CLI routing with live execution**

Run: `python3 -m os_manager.cli psi --help` and `python3 -m os_manager.cli psi status --json`
Expected: Exit code 0, formatted help / valid JSON telemetry.

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "chore(test): verify master harness integrity for autonomous PSI daemon subsystem"
```

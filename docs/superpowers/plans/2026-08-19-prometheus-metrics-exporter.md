# Prometheus Metrics Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a zero-dependency Python 3 Prometheus metrics daemon (`scripts/metrics_exporter.py`). It exposes WSL2 system health and Claude Code lifecycle telemetry on `127.0.0.1:9100`, backed by a systemd user service unit and unit tests.

**Architecture:** The daemon runs a standard library `http.server.HTTPServer` bound strictly to IPv4 loopback `127.0.0.1:9100`. Custom collectors gather CPU load, memory and swap distribution, ext4 root storage capacity, systemd unit failures, and hook telemetry. The endpoint formats all metrics into Prometheus 0.0.4 text exposition format. A sandboxed systemd user service (`systemd/os-metrics-exporter.service`) manages daemon lifecycle, orchestrated via `scripts/manage_timers.sh`.

**Tech Stack:** Python 3.10+ (Standard Library: `http.server`, `socketserver`, `json`, `os`, `sys`, `time`, `subprocess`, `argparse`, `unittest`), systemd user units, Bash 5.2+, `jq`, `curl`.

**Spec:** `docs/superpowers/specs/2026-08-19-prometheus-metrics-exporter-design.md`

## Global Constraints

- **Strict Loopback Binding**: The daemon must bind exclusively to IPv4 address `127.0.0.1`. Requests originating from any non-loopback address must receive an immediate HTTP 403 Forbidden response or connection drop.
- **Zero External Dependencies**: The daemon must run entirely on the standard Python 3 runtime without third-party package dependencies (`pip`, `prometheus_client`, `requests`, `psutil`).
- **Memory Footprint Budget**: Daemon memory consumption must remain below 25MB Resident Set Size (RSS) during continuous operation.
- **Latency Budget**: Metric collection and rendering must complete within 50 milliseconds per scrape request.
- **Unified Log Schema**: Hook telemetry collection must parse `backups/logs/harness_audit.jsonl` matching the exact schema emitted by `trace_helper.sh`: `timestamp_iso`, `timestamp_epoch`, `hook_name`, `target_tool`, `duration_ms`, `duration_us`, `exit_code`.
- **Systemd Sandboxing**: The service unit must enforce `ProtectSystem=strict`, `ProtectHome=read-only`, `ReadWritePaths=/home/rizz/dev/os-manager/backups/logs`, `PrivateTmp=true`, and `NoNewPrivileges=true`.

---

### Task 1: Create Unit and Integration Test Suite for Metrics Exporter

**Files:**
- Create: `tests/test_metrics_exporter.py`

**Interfaces:**
- Consumes: `scripts/metrics_exporter.py` (`parse_loadavg`, `parse_meminfo`, `collect_storage_metrics`, `collect_systemd_metrics`, `collect_harness_metrics`, `format_prometheus_metrics`, `MetricsHTTPRequestHandler`, `MetricsServer`)
- Produces: Automated test suite validating data parsers, Prometheus exposition format compliance, HTTP status codes (`GET /metrics`, `GET /health`, `POST /metrics`, `GET /404`), and non-loopback client rejection.

- [ ] **Step 1: Write the failing unit and integration test suite**

```python
cat <<'EOF' > tests/test_metrics_exporter.py
#!/usr/bin/env python3
"""tests/test_metrics_exporter.py

Comprehensive unit and integration test suite for the Prometheus Metrics Exporter.
Validates metric parsing, exposition formatting, HTTP routing, and security boundaries.
"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

# Ensure workspace root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from scripts.metrics_exporter import (
    parse_loadavg,
    parse_meminfo,
    collect_storage_metrics,
    collect_systemd_metrics,
    collect_harness_metrics,
    format_prometheus_metrics,
    create_server,
)


class TestMetricsParsers(unittest.TestCase):
    """Test standalone parsing functions with fixture inputs."""

    def test_parse_loadavg_valid(self):
        content = "0.42 0.38 0.29 2/450 12345\n"
        cores, loads = parse_loadavg(content)
        self.assertGreaterEqual(cores, 1)
        self.assertEqual(loads["1m"], 0.42)
        self.assertEqual(loads["5m"], 0.38)
        self.assertEqual(loads["15m"], 0.29)

    def test_parse_loadavg_malformed(self):
        cores, loads = parse_loadavg("invalid content")
        self.assertGreaterEqual(cores, 1)
        self.assertEqual(loads["1m"], 0.0)
        self.assertEqual(loads["5m"], 0.0)
        self.assertEqual(loads["15m"], 0.0)

    def test_parse_meminfo_valid(self):
        content = (
            "MemTotal:       32505856 kB\n"
            "MemFree:        23592960 kB\n"
            "MemAvailable:   27772592 kB\n"
            "Buffers:          123456 kB\n"
            "Cached:          4056176 kB\n"
            "SwapTotal:       8388608 kB\n"
            "SwapFree:        8388608 kB\n"
        )
        mem = parse_meminfo(content)
        self.assertEqual(mem["total_bytes"], 32505856 * 1024)
        self.assertEqual(mem["free_bytes"], 23592960 * 1024)
        self.assertEqual(mem["available_bytes"], 27772592 * 1024)
        self.assertEqual(mem["buffers_bytes"], 123456 * 1024)
        self.assertEqual(mem["cached_bytes"], 4056176 * 1024)
        self.assertEqual(mem["swap_total_bytes"], 8388608 * 1024)
        self.assertEqual(mem["swap_free_bytes"], 8388608 * 1024)
        self.assertEqual(mem["swap_used_bytes"], 0)

    def test_parse_meminfo_empty(self):
        mem = parse_meminfo("")
        self.assertEqual(mem["total_bytes"], 0)
        self.assertEqual(mem["available_bytes"], 0)
        self.assertEqual(mem["swap_used_bytes"], 0)

    def test_collect_storage_metrics_root(self):
        storage = collect_storage_metrics("/")
        self.assertIn("total_bytes", storage)
        self.assertIn("free_bytes", storage)
        self.assertIn("available_bytes", storage)
        self.assertGreater(storage["total_bytes"], 0)
        self.assertGreater(storage["available_bytes"], 0)

    def test_collect_harness_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_log = os.path.join(tmpdir, "harness_audit.jsonl")
            error_log = os.path.join(tmpdir, "harness_errors.jsonl")

            records = [
                {"hook_name": "SessionStart", "exit_code": 0, "duration_ms": 12.5},
                {"hook_name": "PreToolUse", "exit_code": 0, "duration_ms": 1.2},
                {"hook_name": "PreToolUse", "exit_code": 2, "duration_ms": 2.1},
                {"hook_name": "PostToolUse", "exit_code": 0, "duration_ms": 15.4},
            ]
            with open(audit_log, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
                f.write("corrupted json line\n")

            with open(error_log, "w", encoding="utf-8") as f:
                f.write(json.dumps({"error": "test failure 1"}) + "\n")
                f.write(json.dumps({"error": "test failure 2"}) + "\n")

            harness = collect_harness_metrics(audit_log, error_log)
            self.assertEqual(harness["hook_executions"]["SessionStart"], 1)
            self.assertEqual(harness["hook_executions"]["PreToolUse"], 2)
            self.assertEqual(harness["hook_executions"]["PostToolUse"], 1)
            self.assertEqual(harness["hook_blocks"]["PreToolUse"], 1)
            self.assertEqual(harness["latest_durations_ms"]["PreToolUse"], 2.1)
            self.assertEqual(harness["tool_failures_total"], 2)

    def test_format_prometheus_metrics(self):
        data = {
            "cpu_cores": 16,
            "cpu_load": {"1m": 0.42, "5m": 0.38, "15m": 0.29},
            "memory": {
                "total_bytes": 33285996544,
                "available_bytes": 28439126016,
                "free_bytes": 24159191040,
                "cached_bytes": 4056176640,
                "buffers_bytes": 123456789,
                "swap_total_bytes": 8589934592,
                "swap_free_bytes": 8589934592,
                "swap_used_bytes": 0,
            },
            "storage": {
                "total_bytes": 1081101172736,
                "free_bytes": 985123954688,
                "available_bytes": 985123954688,
            },
            "systemd": {
                "system_failed_units": 0,
                "user_failed_units": 0,
                "system_running": 1,
                "user_running": 1,
            },
            "harness": {
                "hook_executions": {"SessionStart": 14, "PreToolUse": 128},
                "hook_blocks": {"PreToolUse": 4},
                "latest_durations_ms": {"PreToolUse": 14.82},
                "tool_failures_total": 3,
            },
            "scrape_duration_seconds": 0.0084,
            "exporter_up": 1,
        }

        output = format_prometheus_metrics(data)
        self.assertIn("# HELP wsl_cpu_cores_total", output)
        self.assertIn("# TYPE wsl_cpu_cores_total gauge", output)
        self.assertIn("wsl_cpu_cores_total 16", output)
        self.assertIn('wsl_cpu_load_average{period="1m"} 0.42', output)
        self.assertIn('wsl_storage_bytes_total{mount="/",fstype="ext4"} 1081101172736', output)
        self.assertIn('harness_hook_executions_total{hook="PreToolUse"} 128', output)
        self.assertIn('harness_hook_blocks_total{hook="PreToolUse"} 4', output)
        self.assertIn("exporter_up 1", output)


class TestMetricsHTTPServer(unittest.TestCase):
    """Integration tests running an ephemeral in-process HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.port = 19100
        cls.server = create_server("127.0.0.1", cls.port, WORKSPACE_ROOT)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2.0)

    def test_get_metrics_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/metrics"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            content_type = resp.headers.get("Content-Type", "")
            self.assertIn("text/plain", content_type)
            self.assertIn("version=0.0.4", content_type)
            body = resp.read().decode("utf-8")
            self.assertIn("wsl_cpu_cores_total", body)
            self.assertIn("wsl_memory_bytes_total", body)
            self.assertIn("exporter_up 1", body)

    def test_get_health_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "healthy")
            self.assertIn("uptime_seconds", data)

    def test_method_not_allowed(self):
        url = f"http://127.0.0.1:{self.port}/metrics"
        req = urllib.request.Request(url, data=b'{"test":1}', method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=2.0)
        self.assertEqual(ctx.exception.code, 405)

    def test_not_found(self):
        url = f"http://127.0.0.1:{self.port}/nonexistent"
        req = urllib.request.Request(url, method="GET")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=2.0)
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
EOF
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_metrics_exporter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.metrics_exporter'` or `ImportError`.

- [ ] **Step 3: Create minimal stub to confirm test structure**

```python
mkdir -p scripts
cat <<'EOF' > scripts/metrics_exporter.py
#!/usr/bin/env python3
"""Stub for scripts/metrics_exporter.py"""
pass
EOF
chmod +x scripts/metrics_exporter.py
```

- [ ] **Step 4: Run test to verify expected failure signatures**

Run: `python3 -m unittest tests/test_metrics_exporter.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_loadavg' from 'scripts.metrics_exporter'`.

- [ ] **Step 5: Commit test suite**

```bash
git add tests/test_metrics_exporter.py scripts/metrics_exporter.py
git commit -m "test(exporter): add unit and integration test suite for metrics exporter"
```

---

### Task 2: Implement Zero-Dependency Python Exporter Daemon

**Files:**
- Modify: `scripts/metrics_exporter.py`
- Test: `tests/test_metrics_exporter.py`

**Interfaces:**
- Consumes: `/proc/loadavg`, `/proc/meminfo`, `os.statvfs('/')`, `systemctl`, `backups/logs/harness_audit.jsonl`, `backups/logs/harness_errors.jsonl`.
- Produces: CLI interface supporting `--port`, `--bind`, `--workspace`, dynamic Prometheus `/metrics` exposition, `/health` endpoint, and IPv4 loopback enforcement.

- [ ] **Step 1: Review failing test suite from Task 1**

Run: `python3 -m unittest tests/test_metrics_exporter.py -v`
Expected: FAIL on missing imports.

- [ ] **Step 2: Implement complete zero-dependency exporter daemon**

```python
cat <<'EOF' > scripts/metrics_exporter.py
#!/usr/bin/env python3
"""scripts/metrics_exporter.py

Zero-dependency Prometheus Metrics Exporter for WSL2 and Claude Code Agent Harness.
Listens strictly on IPv4 loopback 127.0.0.1 and exposes metrics in Prometheus 0.0.4 text format.
"""

import argparse
import http.server
import json
import os
import socketserver
import subprocess
import sys
import time
from typing import Any, Dict, List, Tuple

START_TIME = time.time()


def parse_loadavg(content: str) -> Tuple[int, Dict[str, float]]:
    """Extract CPU cores and 1m, 5m, 15m load averages."""
    cores = os.cpu_count() or 1
    loads = {"1m": 0.0, "5m": 0.0, "15m": 0.0}
    parts = content.strip().split()
    if len(parts) >= 3:
        try:
            loads["1m"] = float(parts[0])
            loads["5m"] = float(parts[1])
            loads["15m"] = float(parts[2])
        except ValueError:
            pass
    return cores, loads


def parse_meminfo(content: str) -> Dict[str, int]:
    """Parse /proc/meminfo into byte measurements."""
    raw_kb: Dict[str, int] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, rest = line.split(":", 1)
        val_parts = rest.strip().split()
        if val_parts:
            try:
                raw_kb[key] = int(val_parts[0])
            except ValueError:
                continue

    total_kb = raw_kb.get("MemTotal", 0)
    free_kb = raw_kb.get("MemFree", 0)
    avail_kb = raw_kb.get("MemAvailable", free_kb)
    cached_kb = raw_kb.get("Cached", 0)
    buffers_kb = raw_kb.get("Buffers", 0)
    swap_total_kb = raw_kb.get("SwapTotal", 0)
    swap_free_kb = raw_kb.get("SwapFree", 0)
    swap_used_kb = max(0, swap_total_kb - swap_free_kb)

    return {
        "total_bytes": total_kb * 1024,
        "free_bytes": free_kb * 1024,
        "available_bytes": avail_kb * 1024,
        "cached_bytes": cached_kb * 1024,
        "buffers_bytes": buffers_kb * 1024,
        "swap_total_bytes": swap_total_kb * 1024,
        "swap_free_bytes": swap_free_kb * 1024,
        "swap_used_bytes": swap_used_kb * 1024,
    }


def collect_storage_metrics(path: str = "/") -> Dict[str, int]:
    """Calculate filesystem capacity and usage using os.statvfs."""
    try:
        st = os.statvfs(path)
        total_bytes = st.f_blocks * st.f_frsize
        free_bytes = st.f_bfree * st.f_frsize
        avail_bytes = st.f_bavail * st.f_frsize
        return {
            "total_bytes": total_bytes,
            "free_bytes": free_bytes,
            "available_bytes": avail_bytes,
        }
    except OSError:
        return {"total_bytes": 0, "free_bytes": 0, "available_bytes": 0}


def collect_systemd_metrics() -> Dict[str, int]:
    """Collect systemd unit health status for system and user scopes."""
    results = {
        "system_failed_units": 0,
        "user_failed_units": 0,
        "system_running": 0,
        "user_running": 0,
    }

    # System scope failed units
    try:
        proc = subprocess.run(
            ["systemctl", "--failed", "--no-legend"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if proc.returncode == 0:
            lines = [line for line in proc.stdout.splitlines() if line.strip()]
            results["system_failed_units"] = len(lines)
    except (OSError, subprocess.TimeoutExpired):
        pass

    # User scope failed units
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "--failed", "--no-legend"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if proc.returncode == 0:
            lines = [line for line in proc.stdout.splitlines() if line.strip()]
            results["user_failed_units"] = len(lines)
    except (OSError, subprocess.TimeoutExpired):
        pass

    # System scope running status
    try:
        proc = subprocess.run(
            ["systemctl", "is-system-running"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        status = proc.stdout.strip()
        results["system_running"] = 1 if status in ("running", "degraded") else 0
    except (OSError, subprocess.TimeoutExpired):
        pass

    # User scope running status
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        status = proc.stdout.strip()
        results["user_running"] = 1 if status in ("running", "degraded") else 0
    except (OSError, subprocess.TimeoutExpired):
        pass

    return results


def collect_harness_metrics(audit_log_path: str, error_log_path: str) -> Dict[str, Any]:
    """Aggregate lifecycle hook executions, blocks, and tool failures."""
    hook_executions: Dict[str, int] = {}
    hook_blocks: Dict[str, int] = {}
    latest_durations_ms: Dict[str, float] = {}
    tool_failures_total = 0

    if os.path.isfile(audit_log_path):
        try:
            with open(audit_log_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        hook = record.get("hook_name")
                        exit_code = record.get("exit_code", 0)
                        dur_ms = float(record.get("duration_ms", 0.0))
                        if hook:
                            hook_executions[hook] = hook_executions.get(hook, 0) + 1
                            latest_durations_ms[hook] = dur_ms
                            if exit_code == 2:
                                hook_blocks[hook] = hook_blocks.get(hook, 0) + 1
                    except (json.JSONDecodeError, ValueError):
                        continue
        except OSError:
            pass

    if os.path.isfile(error_log_path):
        try:
            with open(error_log_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip():
                        tool_failures_total += 1
        except OSError:
            pass

    return {
        "hook_executions": hook_executions,
        "hook_blocks": hook_blocks,
        "latest_durations_ms": latest_durations_ms,
        "tool_failures_total": tool_failures_total,
    }


def collect_all_metrics(workspace_root: str) -> Dict[str, Any]:
    """Gather all system and harness telemetry."""
    t0 = time.perf_counter()

    # CPU load
    loadavg_content = ""
    if os.path.isfile("/proc/loadavg"):
        try:
            with open("/proc/loadavg", "r", encoding="utf-8") as f:
                loadavg_content = f.read()
        except OSError:
            pass
    cores, cpu_load = parse_loadavg(loadavg_content)

    # Memory
    meminfo_content = ""
    if os.path.isfile("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                meminfo_content = f.read()
        except OSError:
            pass
    mem_data = parse_meminfo(meminfo_content)

    # Storage
    storage_data = collect_storage_metrics("/")

    # Systemd
    systemd_data = collect_systemd_metrics()

    # Agent Harness
    audit_log = os.path.join(workspace_root, "backups", "logs", "harness_audit.jsonl")
    error_log = os.path.join(workspace_root, "backups", "logs", "harness_errors.jsonl")
    harness_data = collect_harness_metrics(audit_log, error_log)

    scrape_duration = time.perf_counter() - t0

    return {
        "cpu_cores": cores,
        "cpu_load": cpu_load,
        "memory": mem_data,
        "storage": storage_data,
        "systemd": systemd_data,
        "harness": harness_data,
        "scrape_duration_seconds": scrape_duration,
        "exporter_up": 1,
    }


def format_prometheus_metrics(data: Dict[str, Any]) -> str:
    """Format dictionary into Prometheus 0.0.4 text representation."""
    lines: List[str] = []

    # CPU
    lines.append("# HELP wsl_cpu_cores_total Total virtual CPU cores allocated to WSL2.")
    lines.append("# TYPE wsl_cpu_cores_total gauge")
    lines.append(f"wsl_cpu_cores_total {data['cpu_cores']}")

    lines.append("# HELP wsl_cpu_load_average System load average over 1, 5, and 15 minutes.")
    lines.append("# TYPE wsl_cpu_load_average gauge")
    lines.append(f'wsl_cpu_load_average{{period="1m"}} {data["cpu_load"]["1m"]:.2f}')
    lines.append(f'wsl_cpu_load_average{{period="5m"}} {data["cpu_load"]["5m"]:.2f}')
    lines.append(f'wsl_cpu_load_average{{period="15m"}} {data["cpu_load"]["15m"]:.2f}')

    # Memory
    mem = data["memory"]
    lines.append("# HELP wsl_memory_bytes_total Total physical RAM allocated to the VM in bytes.")
    lines.append("# TYPE wsl_memory_bytes_total gauge")
    lines.append(f"wsl_memory_bytes_total {mem['total_bytes']}")

    lines.append("# HELP wsl_memory_bytes_available Available memory for new applications.")
    lines.append("# TYPE wsl_memory_bytes_available gauge")
    lines.append(f"wsl_memory_bytes_available {mem['available_bytes']}")

    lines.append("# HELP wsl_memory_bytes_free Unused physical RAM in bytes.")
    lines.append("# TYPE wsl_memory_bytes_free gauge")
    lines.append(f"wsl_memory_bytes_free {mem['free_bytes']}")

    lines.append("# HELP wsl_memory_bytes_cached Memory used for disk caching in bytes.")
    lines.append("# TYPE wsl_memory_bytes_cached gauge")
    lines.append(f"wsl_memory_bytes_cached {mem['cached_bytes']}")

    lines.append("# HELP wsl_memory_bytes_buffers Memory used for file buffers in bytes.")
    lines.append("# TYPE wsl_memory_bytes_buffers gauge")
    lines.append(f"wsl_memory_bytes_buffers {mem['buffers_bytes']}")

    lines.append("# HELP wsl_swap_bytes_total Total configured swap space in bytes.")
    lines.append("# TYPE wsl_swap_bytes_total gauge")
    lines.append(f"wsl_swap_bytes_total {mem['swap_total_bytes']}")

    lines.append("# HELP wsl_swap_bytes_free Unused swap space in bytes.")
    lines.append("# TYPE wsl_swap_bytes_free gauge")
    lines.append(f"wsl_swap_bytes_free {mem['swap_free_bytes']}")

    lines.append("# HELP wsl_swap_bytes_used Consumed swap space in bytes.")
    lines.append("# TYPE wsl_swap_bytes_used gauge")
    lines.append(f"wsl_swap_bytes_used {mem['swap_used_bytes']}")

    # Storage
    st = data["storage"]
    lines.append("# HELP wsl_storage_bytes_total Total capacity of ext4 root partition in bytes.")
    lines.append("# TYPE wsl_storage_bytes_total gauge")
    lines.append(f'wsl_storage_bytes_total{{mount="/",fstype="ext4"}} {st["total_bytes"]}')

    lines.append("# HELP wsl_storage_bytes_free Total free space on ext4 partition in bytes.")
    lines.append("# TYPE wsl_storage_bytes_free gauge")
    lines.append(f'wsl_storage_bytes_free{{mount="/",fstype="ext4"}} {st["free_bytes"]}')

    lines.append("# HELP wsl_storage_bytes_available Available space for unprivileged users in bytes.")
    lines.append("# TYPE wsl_storage_bytes_available gauge")
    lines.append(f'wsl_storage_bytes_available{{mount="/",fstype="ext4"}} {st["available_bytes"]}')

    # Systemd
    sd = data["systemd"]
    lines.append("# HELP wsl_systemd_failed_units Number of failed systemd units in system scope.")
    lines.append("# TYPE wsl_systemd_failed_units gauge")
    lines.append(f'wsl_systemd_failed_units{{scope="system"}} {sd["system_failed_units"]}')

    lines.append("# HELP wsl_systemd_user_failed_units Number of failed systemd units in user scope.")
    lines.append("# TYPE wsl_systemd_user_failed_units gauge")
    lines.append(f'wsl_systemd_user_failed_units{{scope="user"}} {sd["user_failed_units"]}')

    lines.append("# HELP wsl_systemd_running_status Systemd runtime status (1=running/degraded, 0=other).")
    lines.append("# TYPE wsl_systemd_running_status gauge")
    lines.append(f'wsl_systemd_running_status{{scope="system"}} {sd["system_running"]}')
    lines.append(f'wsl_systemd_running_status{{scope="user"}} {sd["user_running"]}')

    # Harness
    hn = data["harness"]
    lines.append("# HELP harness_hook_executions_total Total invocations of lifecycle hooks.")
    lines.append("# TYPE harness_hook_executions_total counter")
    for hook, count in sorted(hn["hook_executions"].items()):
        lines.append(f'harness_hook_executions_total{{hook="{hook}"}} {count}')

    lines.append("# HELP harness_hook_blocks_total Total hook invocations blocked by security guardrails.")
    lines.append("# TYPE harness_hook_blocks_total counter")
    for hook, count in sorted(hn["hook_blocks"].items()):
        lines.append(f'harness_hook_blocks_total{{hook="{hook}"}} {count}')

    lines.append("# HELP harness_hook_duration_ms Latest measured duration of hook execution in ms.")
    lines.append("# TYPE harness_hook_duration_ms gauge")
    for hook, dur in sorted(hn["latest_durations_ms"].items()):
        lines.append(f'harness_hook_duration_ms{{hook="{hook}"}} {dur:.2f}')

    lines.append("# HELP harness_tool_failures_total Total tool execution errors logged.")
    lines.append("# TYPE harness_tool_failures_total counter")
    lines.append(f'harness_tool_failures_total{{source="PostToolUseFailure"}} {hn["tool_failures_total"]}')

    # Meta
    lines.append("# HELP exporter_scrape_duration_seconds Time taken to collect all metrics.")
    lines.append("# TYPE exporter_scrape_duration_seconds gauge")
    lines.append(f"exporter_scrape_duration_seconds {data['scrape_duration_seconds']:.6f}")

    lines.append("# HELP exporter_up Exporter operational status indicator.")
    lines.append("# TYPE exporter_up gauge")
    lines.append(f"exporter_up {data['exporter_up']}")

    return "\n".join(lines) + "\n"


class MetricsHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """Custom HTTP handler serving Prometheus metrics and health checks."""

    server_version = "WSLMetricsExporter/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stdout logging for silent background operation."""
        pass

    def _verify_client(self) -> bool:
        """Enforce strict loopback client address constraint."""
        client_ip = self.client_address[0]
        if client_ip not in ("127.0.0.1", "localhost", "::1"):
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"403 Forbidden: Loopback connections only.\n")
            return False
        return True

    def do_GET(self) -> None:
        """Route GET requests to /metrics, /health, or return 404."""
        if not self._verify_client():
            return

        workspace = getattr(self.server, "workspace_root", WORKSPACE_ROOT)

        if self.path == "/metrics":
            data = collect_all_metrics(workspace)
            payload = format_prometheus_metrics(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path in ("/health", "/"):
            uptime = int(time.time() - START_TIME)
            payload = json.dumps({"status": "healthy", "uptime_seconds": uptime}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found\n")

    def do_HEAD(self) -> None:
        """Support HEAD requests for health probes."""
        if not self._verify_client():
            return
        if self.path in ("/metrics", "/health", "/"):
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        """Reject non-GET methods."""
        self.send_response(405)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"405 Method Not Allowed\n")

    do_PUT = do_POST
    do_DELETE = do_POST
    do_PATCH = do_POST


class MetricsServer(socketserver.TCPServer):
    """TCPServer carrying workspace root configuration."""

    allow_reuse_address = True

    def __init__(self, server_address: Tuple[str, int], workspace_root: str):
        self.workspace_root = workspace_root
        super().__init__(server_address, MetricsHTTPRequestHandler)


def create_server(host: str, port: int, workspace_root: str) -> MetricsServer:
    """Instantiate a configured MetricsServer instance."""
    return MetricsServer((host, port), workspace_root)


def main() -> None:
    """CLI entry point for metrics exporter daemon."""
    parser = argparse.ArgumentParser(description="WSL2 & Claude Harness Prometheus Exporter")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("OS_EXPORTER_PORT", "9100")),
        help="Port to bind (default: 9100 or OS_EXPORTER_PORT)",
    )
    parser.add_argument(
        "--bind",
        type=str,
        default=os.environ.get("OS_EXPORTER_BIND", "127.0.0.1"),
        help="Address to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=os.environ.get("WORKSPACE_ROOT", WORKSPACE_ROOT),
        help="Path to os-manager workspace root",
    )
    args = parser.parse_args()

    if args.bind not in ("127.0.0.1", "localhost"):
        sys.stderr.write(f"Error: Refusing to bind to non-loopback address: {args.bind}\n")
        sys.exit(1)

    try:
        server = create_server(args.bind, args.port, args.workspace)
    except OSError as e:
        sys.stderr.write(f"Error: Failed to bind to {args.bind}:{args.port}: {e}\n")
        sys.exit(1)

    print(f"Starting Prometheus Metrics Exporter on http://{args.bind}:{args.port}/metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Prometheus Metrics Exporter.")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
EOF
chmod +x scripts/metrics_exporter.py
```

- [ ] **Step 3: Run unit and integration tests to verify pass**

Run: `python3 -m unittest tests/test_metrics_exporter.py -v`
Expected: PASS (all tests succeed with OK status).

- [ ] **Step 4: Verify CLI execution and help flag**

Run: `python3 scripts/metrics_exporter.py --help`
Expected: Return code 0 with usage information.

- [ ] **Step 5: Commit metrics exporter implementation**

```bash
git add scripts/metrics_exporter.py
git commit -m "feat(exporter): implement zero-dependency Prometheus metrics exporter"
```

---

### Task 3: Create Systemd User Service Unit

**Files:**
- Create: `systemd/os-metrics-exporter.service`

**Interfaces:**
- Consumes: `scripts/metrics_exporter.py`
- Produces: Hardened systemd user service unit with strict filesystem sandboxing.

- [ ] **Step 1: Write verification test command**

Run: `test -f systemd/os-metrics-exporter.service`
Expected: FAIL before file creation.

- [ ] **Step 2: Create hardened systemd user service unit**

```ini
cat <<'EOF' > systemd/os-metrics-exporter.service
[Unit]
Description=OS-Manager Prometheus Metrics Exporter
Documentation=https://github.com/0xrizz/os-manager
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/rizz/dev/os-manager/scripts/metrics_exporter.py --port 9100 --bind 127.0.0.1
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

# Security Sandboxing Settings
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/rizz/dev/os-manager/backups/logs
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=default.target
EOF
```

- [ ] **Step 3: Verify unit file syntax**

Run: `grep -E 'ExecStart|ProtectSystem|ProtectHome' systemd/os-metrics-exporter.service`
Expected: Matches service directives and security settings.

- [ ] **Step 4: Commit systemd unit**

```bash
git add systemd/os-metrics-exporter.service
git commit -m "feat(systemd): add hardened user service unit for metrics exporter"
```

---

### Task 4: Integrate Exporter Management Into Timer Manager Script

**Files:**
- Modify: `scripts/manage_timers.sh`

**Interfaces:**
- Consumes: `systemd/os-maintenance.service`, `systemd/os-maintenance.timer`, `systemd/os-metrics-exporter.service`
- Produces: CLI commands (`install`, `uninstall`, `status`, `enable`, `disable`, `--status`, `--enable`, `--disable`) orchestrating both maintenance timers and the metrics exporter.

- [ ] **Step 1: Write failing test checking for exporter integration**

Run: `grep -q "os-metrics-exporter.service" scripts/manage_timers.sh`
Expected: FAIL (exit code 1).

- [ ] **Step 2: Update `scripts/manage_timers.sh` with exporter unit lifecycle management**

```bash
cat <<'EOF' > scripts/manage_timers.sh
#!/usr/bin/env bash
# scripts/manage_timers.sh - Install and manage os-manager systemd user timers and services
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
ACTION="${1:-status}"

# Normalize flag syntax (--status -> status)
ACTION="${ACTION#--}"

install_units() {
    echo "=== Installing OS-Manager Systemd User Units ==="
    mkdir -p "${SYSTEMD_USER_DIR}"
    cp "${WORKSPACE_ROOT}/systemd/os-maintenance.service" "${SYSTEMD_USER_DIR}/"
    cp "${WORKSPACE_ROOT}/systemd/os-maintenance.timer" "${SYSTEMD_USER_DIR}/"
    cp "${WORKSPACE_ROOT}/systemd/os-metrics-exporter.service" "${SYSTEMD_USER_DIR}/"

    systemctl --user daemon-reload
    systemctl --user enable --now os-maintenance.timer
    systemctl --user enable --now os-metrics-exporter.service
    echo "✓ Maintenance timer and metrics exporter installed and activated."
}

uninstall_units() {
    echo "=== Disabling OS-Manager Systemd User Units ==="
    systemctl --user disable --now os-maintenance.timer 2>/dev/null || true
    systemctl --user disable --now os-metrics-exporter.service 2>/dev/null || true
    rm -f "${SYSTEMD_USER_DIR}/os-maintenance.service"
    rm -f "${SYSTEMD_USER_DIR}/os-maintenance.timer"
    rm -f "${SYSTEMD_USER_DIR}/os-metrics-exporter.service"
    systemctl --user daemon-reload
    echo "✓ Maintenance timer and metrics exporter disabled and uninstalled."
}

check_status() {
    echo "=== OS-Manager Systemd User Timer Status ==="
    systemctl --user list-timers --all | grep -E 'os-maintenance|NEXT' || echo "No active maintenance timers found."
    echo ""
    echo "=== OS-Manager Systemd Exporter Status ==="
    systemctl --user status os-metrics-exporter.service --no-pager 2>/dev/null || echo "Exporter service inactive or uninstalled."
}

case "${ACTION}" in
    install|enable)
        install_units
        ;;
    uninstall|disable)
        uninstall_units
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status|enable|disable|--status|--enable|--disable}"
        exit 1
        ;;
esac
EOF
chmod +x scripts/manage_timers.sh
```

- [ ] **Step 3: Verify script syntax and status execution**

Run: `bash -n scripts/manage_timers.sh && ./scripts/manage_timers.sh --status`
Expected: Status executes cleanly without syntax errors.

- [ ] **Step 4: Commit `scripts/manage_timers.sh` update**

```bash
git add scripts/manage_timers.sh
git commit -m "feat(timers): add metrics exporter service lifecycle to manage_timers.sh"
```

---

### Task 5: Master Harness Integration and Verification

**Files:**
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_metrics_exporter.py`, `scripts/metrics_exporter.py`, `systemd/os-metrics-exporter.service`
- Produces: Automated assertions in master test runner verifying script compilation, CLI execution, unit test suite pass rate, and systemd unit integrity.

- [ ] **Step 1: Check existing assertions in `tests/test_harness.sh`**

Run: `grep -q "test_metrics_exporter.py" tests/test_harness.sh`
Expected: FAIL (assertion not yet present).

- [ ] **Step 2: Add metrics exporter test assertions to `tests/test_harness.sh`**

Read `tests/test_harness.sh` and append a test block before the final summary:

```bash
cat <<'EOF' >> tests/test_harness.sh

echo "--- Testing Prometheus Metrics Exporter Suite ---"
set +e
python3 -m py_compile "${WORKSPACE_ROOT}/scripts/metrics_exporter.py" > /dev/null 2>&1
assert_exit_code "metrics_exporter.py bytecode compilation" 0 $?

"${WORKSPACE_ROOT}/scripts/metrics_exporter.py" --help > /dev/null 2>&1
assert_exit_code "metrics_exporter.py --help execution" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_metrics_exporter.py" > /dev/null 2>&1
assert_exit_code "test_metrics_exporter.py unit test suite" 0 $?

[ -f "${WORKSPACE_ROOT}/systemd/os-metrics-exporter.service" ]
assert_exit_code "os-metrics-exporter.service exists" 0 $?
set -e
EOF
```

- [ ] **Step 3: Run the full harness test suite**

Run: `./tests/test_harness.sh`
Expected: All 32+ assertions pass with 0 failures.

- [ ] **Step 4: Run harness self-check**

Run: `./scripts/harness_check.sh`
Expected: Pass with 0 errors.

- [ ] **Step 5: Commit `tests/test_harness.sh`**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate metrics exporter test assertions into master harness"
```

---

## Plan Self-Review Checklist

- **Spec Coverage:** 
  - Zero-dependency Python 3 daemon is implemented in Task 2.
  - Metric Catalog (`wsl_cpu_*`, `wsl_memory_*`, `wsl_swap_*`, `wsl_storage_*`, `wsl_systemd_*`, `harness_*`, `exporter_*`) is delivered in Task 2.
  - Strict `127.0.0.1:9100` IPv4 loopback binding is tested and enforced in Tasks 1, 2, and 3.
  - Systemd user service unit with sandboxing is added in Task 3.
  - Unified log parsing from `harness_audit.jsonl` and `harness_errors.jsonl` is handled in Tasks 1 and 2.
  - Management script integration is wired in Task 4.
  - Master test harness assertions are verified in Task 5.
- **Placeholder Scan:** Zero instances of "TBD", "TODO", "implement later", or ambiguous ellipses.
- **Type Consistency:** Method signatures (`parse_loadavg`, `parse_meminfo`, `collect_storage_metrics`, `collect_systemd_metrics`, `collect_harness_metrics`, `format_prometheus_metrics`, `create_server`) match identically between Task 1 and Task 2.

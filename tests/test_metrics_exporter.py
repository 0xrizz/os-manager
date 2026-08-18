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

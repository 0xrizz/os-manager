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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WORKSPACE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))


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

        workspace = getattr(self.server, "workspace_root", DEFAULT_WORKSPACE_ROOT)

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
        default=os.environ.get("WORKSPACE_ROOT", DEFAULT_WORKSPACE_ROOT),
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

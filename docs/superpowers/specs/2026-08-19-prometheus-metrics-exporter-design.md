# Technical Design Specification: Prometheus Metrics Exporter (Deliverable 3.1)

## 1. Executive Summary & Objective

This document defines the architecture, metric interfaces, security boundaries, error handling, and test strategy for the **Prometheus Metrics Exporter** (Deliverable 3.1 from `docs/PRD.md`). 

This specification introduces a zero-dependency Python 3 HTTP daemon running under systemd. The service collects WSL2 guest telemetry alongside Claude Code agent harness telemetry, exposing metrics in Prometheus text format on `127.0.0.1:9100`.

---

## 2. System Architecture & Component Design

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════
                         PROMETHEUS METRICS EXPORTER ARCHITECTURE
 ══════════════════════════════════════════════════════════════════════════════════════════════════

  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
  │ PROMETHEUS SCRAPER / LOCAL AGENT                                                            │
  │ • HTTP GET http://127.0.0.1:9100/metrics                                                    │
  └──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                                 │
 ┌───────────────────────────────────────────────▼──────────────────────────────────────────────┐
 │ EXPORTER HTTP DAEMON (`scripts/metrics_exporter.py`)                                         │
 │ • SocketServer bound strictly to IPv4 127.0.0.1:9100                                         │
 │ • Custom `MetricsHTTPRequestHandler` (disallows non-GET, non-localhost traffic)             │
 └───────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                                 │
        ┌────────────────────────────────────────┼────────────────────────────────────────┐
        ▼                                        ▼                                        ▼
 ┌───────────────────────────┐    ┌───────────────────────────┐    ┌────────────────────────────┐
 │ KERNEL & OS COLLECTOR     │    │ SYSTEMD SERVICE COLLECTOR │    │ AGENT HARNESS COLLECTOR    │
 ├───────────────────────────┤    ├───────────────────────────┤    ├────────────────────────────┤
 │ • /proc/loadavg           │    │ • systemctl is-system-    │    │ • backups/logs/            │
 │ • /proc/meminfo           │    │   running                 │    │   harness_audit.jsonl      │
 │ • /proc/stat, os.cpu_count│    │ • systemctl --failed      │    │ • backups/logs/            │
 │ • os.statvfs('/')         │    │   --no-legend             │    │   harness_errors.jsonl     │
 └───────────────────────────┘    └───────────────────────────┘    └────────────────────────────┘
```

### 2.1 Component Breakdown

1. **Daemon Engine (`scripts/metrics_exporter.py`)**:
   - Implements a single-threaded, non-blocking HTTP server using standard library `http.server.HTTPServer` and `http.server.BaseHTTPRequestHandler`.
   - Listens exclusively on IPv4 loopback `127.0.0.1` on port `9100`.
   - Implements a request router serving:
     - `GET /metrics`: Generates and streams dynamic Prometheus metrics with `Content-Type: text/plain; version=0.0.4; charset=utf-8`.
     - `GET /health` or `GET /`: Returns HTTP 200 with JSON payload `{"status":"healthy","uptime_seconds":...}`.
     - Any other path or HTTP verb: Returns HTTP 404 or HTTP 405.

2. **System Collectors**:
   - **CPU Collector**: Reads `/proc/loadavg` directly to extract 1-minute, 5-minute, and 15-minute load averages. Reads `os.cpu_count()` for total vCPU allocation.
   - **Memory & Swap Collector**: Parses `/proc/meminfo` to extract total memory, available memory, free memory, cached memory, buffers, total swap, and free swap. Calculates active swap pressure.
   - **Storage Collector**: Invokes `os.statvfs('/')` to compute total bytes, free bytes, available bytes, and utilization percentage for the native ext4 root partition.
   - **Systemd Health Collector**: Invokes `systemctl --user is-system-running` and `systemctl is-system-running` along with `systemctl --failed --no-legend` via `subprocess.run` with a strict 1-second timeout.
   - **Agent Harness Collector**: Scans `backups/logs/harness_audit.jsonl` and `backups/logs/harness_errors.jsonl` to aggregate total hook executions by hook name, successful executions, blocked violations, and logged runtime tool errors.

3. **Lifecycle & Process Management (`systemd/os-metrics-exporter.service`)**:
   - Configured as a systemd user service unit.
   - Managed through `./scripts/manage_timers.sh` or dedicated exporter commands.
   - Restarts automatically on failure with exponential backoff (`Restart=on-failure`, `RestartSec=5s`).

---

## 3. Metric Definitions & Prometheus Exposition Format

All metrics follow official Prometheus naming conventions, declaring `# HELP` and `# TYPE` headers for every metric family.

### 3.1 Metric Catalog

| Metric Name | Type | Description | Labels |
|---|---|---|---|
| `wsl_cpu_cores_total` | Gauge | Total virtual CPU cores allocated to WSL2 | None |
| `wsl_cpu_load_average` | Gauge | System load average over 1, 5, and 15 minutes | `period="1m"`, `period="5m"`, `period="15m"` |
| `wsl_memory_bytes_total` | Gauge | Total physical RAM allocated to the WSL2 VM in bytes | None |
| `wsl_memory_bytes_available` | Gauge | Available memory for starting new applications without swapping | None |
| `wsl_memory_bytes_free` | Gauge | Unused physical RAM in bytes | None |
| `wsl_memory_bytes_cached` | Gauge | Memory used for disk caching in bytes | None |
| `wsl_memory_bytes_buffers` | Gauge | Memory used for temporary file buffers in bytes | None |
| `wsl_swap_bytes_total` | Gauge | Total configured swap space in bytes | None |
| `wsl_swap_bytes_free` | Gauge | Unused swap space in bytes | None |
| `wsl_swap_bytes_used` | Gauge | Consumed swap space in bytes | None |
| `wsl_storage_bytes_total` | Gauge | Total capacity of the native ext4 root partition (`/`) in bytes | `mount="/"`, `fstype="ext4"` |
| `wsl_storage_bytes_free` | Gauge | Total free space on the ext4 partition in bytes | `mount="/"`, `fstype="ext4"` |
| `wsl_storage_bytes_available` | Gauge | Available space for non-privileged users in bytes | `mount="/"`, `fstype="ext4"` |
| `wsl_systemd_failed_units` | Gauge | Number of failed systemd units in the system scope | `scope="system"` |
| `wsl_systemd_user_failed_units` | Gauge | Number of failed systemd units in the user session scope | `scope="user"` |
| `wsl_systemd_running_status` | Gauge | Systemd runtime status (1 = running, 0 = degraded/other) | `scope="system"`, `scope="user"` |
| `harness_hook_executions_total` | Counter | Total invocations of Claude Code lifecycle hooks | `hook="SessionStart"`, `hook="PreToolUse"`, `hook="PostToolUse"`, `hook="PostToolUseFailure"`, `hook="PreCompact"`, `hook="SessionEnd"` |
| `harness_hook_blocks_total` | Counter | Total invocations blocked by security guardrails (Exit Code 2) | `hook="PreToolUse"`, `reason="tier3_violation"` |
| `harness_tool_failures_total` | Counter | Total tool execution errors logged to error telemetry | `source="PostToolUseFailure"` |
| `exporter_scrape_duration_seconds` | Gauge | Time taken to collect all metrics and render the payload | None |
| `exporter_up` | Gauge | Exporter operational status indicator (always 1 when responding) | None |

### 3.2 Sample Prometheus Output

```text
# HELP wsl_cpu_cores_total Total virtual CPU cores allocated to WSL2.
# TYPE wsl_cpu_cores_total gauge
wsl_cpu_cores_total 16

# HELP wsl_cpu_load_average System load average over 1, 5, and 15 minutes.
# TYPE wsl_cpu_load_average gauge
wsl_cpu_load_average{period="1m"} 0.42
wsl_cpu_load_average{period="5m"} 0.38
wsl_cpu_load_average{period="15m"} 0.29

# HELP wsl_memory_bytes_total Total physical RAM allocated to the WSL2 VM in bytes.
# TYPE wsl_memory_bytes_total gauge
wsl_memory_bytes_total 33285996544

# HELP wsl_memory_bytes_available Available memory for starting new applications without swapping.
# TYPE wsl_memory_bytes_available gauge
wsl_memory_bytes_available 28439126016

# HELP wsl_memory_bytes_free Unused physical RAM in bytes.
# TYPE wsl_memory_bytes_free gauge
wsl_memory_bytes_free 24159191040

# HELP wsl_swap_bytes_total Total configured swap space in bytes.
# TYPE wsl_swap_bytes_total gauge
wsl_swap_bytes_total 8589934592

# HELP wsl_swap_bytes_used Consumed swap space in bytes.
# TYPE wsl_swap_bytes_used gauge
wsl_swap_bytes_used 0

# HELP wsl_storage_bytes_total Total capacity of the native ext4 root partition in bytes.
# TYPE wsl_storage_bytes_total gauge
wsl_storage_bytes_total{mount="/",fstype="ext4"} 1081101172736

# HELP wsl_storage_bytes_available Available space for non-privileged users in bytes.
# TYPE wsl_storage_bytes_available gauge
wsl_storage_bytes_available{mount="/",fstype="ext4"} 985123954688

# HELP wsl_systemd_failed_units Number of failed systemd units in the system scope.
# TYPE wsl_systemd_failed_units gauge
wsl_systemd_failed_units{scope="system"} 0

# HELP harness_hook_executions_total Total invocations of Claude Code lifecycle hooks.
# TYPE harness_hook_executions_total counter
harness_hook_executions_total{hook="SessionStart"} 14
harness_hook_executions_total{hook="PreToolUse"} 128
harness_hook_executions_total{hook="PostToolUse"} 92
harness_hook_executions_total{hook="PostToolUseFailure"} 3
harness_hook_executions_total{hook="PreCompact"} 2
harness_hook_executions_total{hook="SessionEnd"} 12

# HELP harness_hook_blocks_total Total invocations blocked by security guardrails.
# TYPE harness_hook_blocks_total counter
harness_hook_blocks_total{hook="PreToolUse",reason="tier3_violation"} 4

# HELP exporter_scrape_duration_seconds Time taken to collect all metrics and render the payload.
# TYPE exporter_scrape_duration_seconds gauge
exporter_scrape_duration_seconds 0.0084

# HELP exporter_up Exporter operational status indicator.
# TYPE exporter_up gauge
exporter_up 1
```

---

## 4. Endpoint Security & Operational Constraints

### 4.1 Binding and Isolation Invariants
- **Loopback Address Restriction**: The socket binds explicitly to IPv4 address `127.0.0.1`. Binding to `0.0.0.0`, wildcard `::`, or external network interfaces is strictly forbidden.
- **Client IP Verification**: The request handler verifies that `self.client_address[0]` matches `127.0.0.1` or `localhost`. Requests originating from any other address receive an immediate socket termination or HTTP 403 Forbidden response.
- **Method Restriction**: Only `GET` and `HEAD` requests are permitted. `POST`, `PUT`, `DELETE`, and `OPTIONS` return HTTP 405 Method Not Allowed.
- **Request Size Limiting**: Request headers are capped at 8KB to prevent memory exhaustion attacks.

### 4.2 Resource Budget & Performance Guarantees
- **Resident Set Size (RSS) Memory**: Memory consumption must remain under 25MB RSS during continuous operation. (Standard Python 3 base runtime consumes ~12MB to 16MB).
- **CPU Utilization**: CPU overhead must remain under 1% during continuous 15-second scrape intervals.
- **Scrape Latency**: Metric generation and payload serialization must complete in under 50 milliseconds per request.

---

## 5. Resilience & Error Handling Strategy

1. **Proc Filesystem Fallback**:
   - When `/proc/loadavg` or `/proc/meminfo` cannot be read, the collector logs a warning to `stderr`. The scraper receives `NaN` or `0` for the affected metrics without daemon crashes.
2. **Missing or Inaccessible Subprocess Utilities**:
   - If `systemctl` is unavailable or returns a non-zero exit code, `wsl_systemd_failed_units` emits `0` and flags `wsl_systemd_running_status{scope="..."} 0`.
   - Subprocess executions maintain a strict 1.0-second timeout to prevent hung calls from blocking requests.
3. **Log File Rotation & Parsing Resilience**:
   - Telemetry readers handle missing or malformed log files gracefully. The reader skips invalid lines without raising uncaught exceptions, returning current counter tallies.
4. **Port Collision Handling**:
   - If port 9100 is already bound by another service, the daemon logs an error to `stderr` with Exit Code 1 and clear diagnostic output indicating the collision.

---

## 6. Systemd Integration & Service Lifecycle

### 6.1 Service Definition (`systemd/os-metrics-exporter.service`)

```ini
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
```

### 6.2 Management Script Updates (`scripts/manage_timers.sh`)

Update `./scripts/manage_timers.sh` to support `exporter-start`, `exporter-stop`, and `exporter-status` actions, or automatically install the exporter unit alongside `os-maintenance.timer`.

---

## 7. Verification & Automated Testing Plan

### 7.1 Unit & Integration Test Suite (`tests/test_metrics_exporter.py`)
1. **Metric Rendering Tests**:
   - Test `/proc/meminfo` parser with mock file contents.
   - Test `/proc/loadavg` parser with known values.
   - Test `statvfs` calculation helper for byte-to-GB accuracy.
   - Test JSONL parser on valid, invalid, and empty log files.
2. **HTTP Endpoint Contract Tests**:
   - Spawn daemon on a high ephemeral port (e.g., `9199`).
   - Send `GET /metrics` and verify HTTP 200 status code and `Content-Type: text/plain; version=0.0.4`.
   - Validate that metric lines match Prometheus format specification (`[a-zA-Z_:][a-zA-Z0-9_:]*`).
   - Send `GET /health` and verify valid JSON response.
   - Send `POST /metrics` and verify HTTP 405 response.
   - Send `GET /invalid` and verify HTTP 404 response.
3. **Resource & Memory Guard Verification**:
   - Measure RSS memory of the running process to confirm memory consumption remains under 25MB.

### 7.2 Harness Integration Test Suite (`tests/test_harness.sh`)
- Add test assertions to `tests/test_harness.sh`:
  - Assert that `scripts/metrics_exporter.py` passes `python3 -m py_compile` and executes `--help` cleanly.
  - Assert that `systemd/os-metrics-exporter.service` passes `systemd-analyze verify`.

---

## 8. Backup & Alternative Architectural Plans

As requested, the alternative approaches are documented below as fallback strategies if the primary approach encounters unforeseen environmental constraints.

### 8.1 Backup Plan: POSIX Shell and OpenBSD Netcat (`nc`) Loop
- **Overview**: A lightweight shell script executing `nc -l -p 9100 -e ./scripts/generate_metrics.sh`.
- **Activation Trigger**: If the Python 3 runtime is corrupted or if extreme memory optimization (<5MB RAM) becomes necessary.
- **Trade-offs**: Lower static memory, but higher process-fork overhead and variable netcat argument compatibility across Linux distributions.

### 8.2 Backup Plan: Out-of-Band Metric File Generation with Static Web Server
- **Overview**: A systemd timer triggers `scripts/generate_metrics.sh` every 15 seconds to write `/tmp/metrics.prom`. A micro HTTP server (such as Python `http.server` or a minimal C binary) serves the static file on port 9100.
- **Activation Trigger**: If collection latency on live `/metrics` requests exceeds the 50ms budget during high I/O workloads.
- **Trade-offs**: Decouples metric generation from scrape requests, but introduces metric staleness up to the timer period.

---

## 9. Deliverables & File Changes Summary

1. `scripts/metrics_exporter.py` - Core Python 3 zero-dependency Prometheus exporter daemon.
2. `systemd/os-metrics-exporter.service` - Systemd user service unit for daemon supervision.
3. `scripts/manage_timers.sh` - Enhanced to manage the exporter lifecycle.
4. `tests/test_metrics_exporter.py` - Automated test suite for exporter metric collectors and HTTP endpoints.
5. `tests/test_harness.sh` - Extended with test assertions for the exporter and service units.
6. `CLAUDE.md` & `.claude/rules/safety-tiers.md` - Updated to whitelist the exporter script in Tier 2.

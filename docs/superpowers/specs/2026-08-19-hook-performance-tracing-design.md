# Technical Design Specification: Hook Performance Tracing (Deliverable 3.4)

## 1. Executive Summary and Objective

This document defines the technical specification for Hook Performance Tracing (Deliverable 3.4 from `docs/PRD.md`).

Autonomous coding agents execute hundreds of tool operations during iterative development. Each tool call triggers lifecycle hooks for security inspection, syntax validation, and telemetry recording. To guarantee that agent execution loops experience zero perceptible friction, Non-Functional Requirement 1 (NFR-1) mandates that hook latency remain under 100 milliseconds at the 99th percentile.

This specification introduces a zero-overhead monotonic tracing engine (`scripts/hooks/lib/trace_helper.sh`) across all six lifecycle hooks. The engine measures nanosecond-level execution durations, capturing structured trace events into `backups/logs/harness_audit.jsonl`. It also provides a benchmark reporting utility (`scripts/hook_benchmark.sh`) to analyze latency percentiles (p50, p95, p99).

---

## 2. System Architecture and Component Design

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════
                         HOOK PERFORMANCE TRACING ARCHITECTURE
 ══════════════════════════════════════════════════════════════════════════════════════════════════

  CLAUDE CODE HARNESS INVOCATION
  (SessionStart | PreToolUse | PostToolUse | PostToolUseFailure | PreCompact | SessionEnd)
                                │
 ┌──────────────────────────────▼───────────────────────────────────────────────────────────────┐
 │ TARGET HOOK ENTRYPOINT (e.g., `scripts/hooks/pre_tool_guard.sh`)                             │
 │ • Sources `scripts/hooks/lib/trace_helper.sh`                                                │
 │ • Invokes `trace_start "PreToolUse" "Bash"` (Captures Monotonic Nanoseconds T0)              │
 │ • Sets POSIX Trap: `trap 'trace_finish $?' EXIT`                                             │
 └──────────────────────────────┬───────────────────────────────────────────────────────────────┘
                                │
 ┌──────────────────────────────▼───────────────────────────────────────────────────────────────┐
 │ HOOK CORE LOGIC EXECUTION                                                                    │
 │ • Evaluates security matrix / Runs linters / Captures telemetry                              │
 │ • Completes execution with Exit Code (0 = Pass, 2 = Block/Fail)                              │
 │ • Non-blocking notification dispatch for Tier 3 blocks via background subshell               │
 └──────────────────────────────┬───────────────────────────────────────────────────────────────┘
                                │
 ┌──────────────────────────────▼───────────────────────────────────────────────────────────────┐
 │ POSIX EXIT TRAP DISPATCHER (`trace_finish`)                                                  │
 │ • Captures Monotonic Nanoseconds T1 via `date +%s%N`                                         │
 │ • Computes Delta: duration_us and duration_ms via pure Bash 64-bit integer arithmetic        │
 │ • Appends structured JSON line to `backups/logs/harness_audit.jsonl`                         │
 │ • Propagates original exit code faithfully                                                   │
 └──────────────────────────────┬───────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
 ┌─────────────────────────────┐         ┌──────────────────────────────┐
 │ PROMETHEUS METRICS EXPORTER │         │ LATENCY BENCHMARK ANALYZER   │
 │ • `harness_hook_executions` │         │ • `scripts/hook_benchmark.sh`│
 │ • `harness_hook_duration_ms`│         │ • Computes p50, p95, p99 ms  │
 └─────────────────────────────┘         └──────────────────────────────┘
```

### 2.1 Component Breakdown

1. **Shared Tracing Library (`scripts/hooks/lib/trace_helper.sh`)**:
   - Provides `trace_start(hook_name, target_tool)` and `trace_finish(exit_code)` functions.
   - Uses built-in Linux nanosecond timers (`date +%s%N`) and pure 64-bit integer arithmetic in Bash.
   - Captures telemetry without spawning secondary Python or Node processes, keeping tracing overhead below 1.0 millisecond.
   - Employs POSIX `EXIT` traps to guarantee execution recording even on early exits, syntax errors, or unhandled failures.

2. **Instrumented Lifecycle Hooks**:
   - `scripts/hooks/session_preflight.sh` (`SessionStart`)
   - `scripts/hooks/pre_tool_guard.sh` (`PreToolUse`)
   - `scripts/hooks/post_tool_lint.sh` (`PostToolUse`)
   - `scripts/hooks/post_tool_failure.sh` (`PostToolUseFailure`)
   - `scripts/hooks/pre_compact_state.sh` (`PreCompact`)
   - `scripts/hooks/session_cleanup.sh` (`SessionEnd`)

3. **Latency Benchmark Analyzer (`scripts/hook_benchmark.sh`)**:
   - Parses `backups/logs/harness_audit.jsonl` to calculate execution statistics.
   - Reports sample count, min, mean, p50, p95, p99, and max latencies per hook.
   - Highlights any hook exceeding the 100ms threshold in red terminal output.
   - Supports structured JSON output via `--json` for automated regression testing.

---

## 3. Telemetry Schema and Event Fields

Every hook invocation appends one line to `backups/logs/harness_audit.jsonl`.

### 3.1 Unified Trace Event JSON Schema

The schema is shared across Hook Performance Tracing (3.4) and the Prometheus Metrics Exporter (3.1):

```json
{
  "timestamp_iso": "2026-08-19T14:32:05.123Z",
  "timestamp_epoch": 1787149925,
  "hook_name": "PreToolUse",
  "target_tool": "Bash",
  "duration_ms": 14.82,
  "duration_us": 14820,
  "exit_code": 0
}
```

### 3.2 Field Catalog

| Field | Type | Description | Example |
|---|---|---|---|
| `timestamp_iso` | String (ISO-8601) | UTC timestamp of event completion | `"2026-08-19T14:32:05.123Z"` |
| `timestamp_epoch` | Integer | Unix epoch timestamp in seconds | `1787149925` |
| `hook_name` | String | Name of the lifecycle hook | `"PreToolUse"`, `"PostToolUse"` |
| `target_tool` | String or null | Target tool from tool invocation payload | `"Bash"`, `"Edit"`, `"Write"`, `null` |
| `duration_ms` | Float | Wall-clock execution time in milliseconds | `14.82` |
| `duration_us` | Integer | Wall-clock execution time in microseconds | `14820` |
| `exit_code` | Integer | Process termination exit code | `0`, `2` |

---

## 4. Implementation Details and Helper Engine

### 4.1 Zero-Fork Helper Implementation (`scripts/hooks/lib/trace_helper.sh`)

```bash
#!/usr/bin/env bash
# scripts/hooks/lib/trace_helper.sh - High-resolution hook execution tracing library
set -euo pipefail

TRACE_HOOK_NAME=""
TRACE_TARGET_TOOL=""
TRACE_START_NS=0

trace_start() {
    TRACE_HOOK_NAME="$1"
    TRACE_TARGET_TOOL="${2:-null}"
    TRACE_START_NS="$(date +%s%N)"
    trap 'trace_finish $?' EXIT
}

trace_finish() {
    local exit_code="$1"
    local end_ns
    end_ns="$(date +%s%N)"
    
    # Calculate duration in microseconds and fractional milliseconds using pure bash integer arithmetic
    local elapsed_ns=$((end_ns - TRACE_START_NS))
    local duration_us=$((elapsed_ns / 1000))
    local ms_int=$((elapsed_ns / 1000000))
    local ms_frac=$(((elapsed_ns % 1000000) / 10000))
    local duration_ms
    printf -v duration_ms "%d.%02d" "${ms_int}" "${ms_frac}"
    
    local timestamp_iso
    timestamp_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    local timestamp_epoch
    timestamp_epoch="$(date +%s)"
    
    local audit_log="${WORKSPACE_ROOT:-.}/backups/logs/harness_audit.jsonl"
    
    if [ -d "$(dirname "${audit_log}")" ]; then
        if [ "${TRACE_TARGET_TOOL}" = "null" ]; then
            printf '{"timestamp_iso":"%s","timestamp_epoch":%d,"hook_name":"%s","target_tool":null,"duration_ms":%s,"duration_us":%d,"exit_code":%d}\n' \
                "${timestamp_iso}" "${timestamp_epoch}" "${TRACE_HOOK_NAME}" "${duration_ms}" "${duration_us}" "${exit_code}" >> "${audit_log}" 2>/dev/null || true
        else
            printf '{"timestamp_iso":"%s","timestamp_epoch":%d,"hook_name":"%s","target_tool":"%s","duration_ms":%s,"duration_us":%d,"exit_code":%d}\n' \
                "${timestamp_iso}" "${timestamp_epoch}" "${TRACE_HOOK_NAME}" "${TRACE_TARGET_TOOL}" "${duration_ms}" "${duration_us}" "${exit_code}" >> "${audit_log}" 2>/dev/null || true
        fi
    fi
    
    exit "${exit_code}"
}
```

---

## 5. Benchmark Reporting Utility (`scripts/hook_benchmark.sh`)

The benchmarking script aggregates historical hook runs to verify latency distributions.

### 5.1 Command-Line Interface

```text
Usage: ./scripts/hook_benchmark.sh [OPTIONS]

Options:
  --samples <N>    Analyze the last N events (default: 500)
  --hook <name>    Filter statistics by hook name
  --json           Output statistics in JSON format
  --assert-p99     Exit with code 1 if any hook p99 exceeds 100ms
  --help, -h       Display this help message
```

### 5.2 Sample Terminal Report

```text
================================================================================
                    CLAUDE CODE HOOK LATENCY BENCHMARK REPORT
================================================================================
Sample Window: Last 500 events from backups/logs/harness_audit.jsonl

HOOK NAME             COUNT     MIN (ms)   P50 (ms)   P95 (ms)   P99 (ms)   MAX (ms)   STATUS
--------------------------------------------------------------------------------
SessionStart             24        18.20      24.10      38.50      44.10      48.20   OK (<100ms)
PreToolUse              312         4.10       7.80      18.20      26.40      34.10   OK (<100ms)
PostToolUse             140         8.40      16.20      42.10      68.30      79.50   OK (<100ms)
PostToolUseFailure        6         3.20       4.10       6.80       7.20       7.20   OK (<100ms)
PreCompact                4         5.10       6.40       9.10       9.80       9.80   OK (<100ms)
SessionEnd               14         2.80       3.60       5.10       6.20       6.50   OK (<100ms)
================================================================================
OVERALL VERDICT: PASS (100% of hooks meet the sub-100ms p99 requirement)
================================================================================
```

---

## 6. Performance Budget and Security Invariants

### 6.1 Overhead Budget
- **Tracing Latency Overhead**: Sourcing `trace_helper.sh` and calculating timestamps adds less than 1.0 millisecond per hook execution.
- **Fail-Safe Logging**: Logging errors or permission issues in writing to `harness_audit.jsonl` are swallowed (`|| true`), ensuring telemetry errors never disrupt hook outcomes.

### 6.2 Security Classification
- **Tier 2 Whitelist**: `scripts/hook_benchmark.sh` is registered as an authorized maintenance script in `scripts/hooks/pre_tool_guard.sh` and `.claude/rules/safety-tiers.md`.

---

## 7. Verification and Automated Testing Plan

### 7.1 Unit and Script Testing (`tests/test_hook_tracing.sh`)
- Test `trace_helper.sh` timing calculations against synthetic delays (`sleep 0.05`).
- Test that exit codes (0, 1, 2) propagate accurately through `trace_finish`.
- Test that `scripts/hook_benchmark.sh` computes percentiles accurately against fixture data.
- Test that `--assert-p99` exits with code 1 when mock data contains slow events (>100ms).

### 7.2 Harness Integration Test Suite (`tests/test_harness.sh`)
- Assert `scripts/hooks/lib/trace_helper.sh` and `scripts/hook_benchmark.sh` pass `bash -n` and `shellcheck`.
- Assert hook invocations generate valid JSON lines in `backups/logs/harness_audit.jsonl` adhering to the unified schema.
- Assert `./scripts/hook_benchmark.sh --json` emits valid structured output.

---

## 8. Rollout Sequence and Implementation DAG

Hook Performance Tracing belongs to Stage 1 of the implementation plan:

1. **Stage 1 (Foundation Libraries and Tracing)**:
   - Deliverable 3.4: Hook Performance Tracing (`scripts/hooks/lib/trace_helper.sh`, `scripts/hook_benchmark.sh`).
   - Deliverable 4.1: Cross-Distribution Engine (`scripts/lib/distro.sh`, generalized package guardrails).
2. **Stage 2 (Base System Services, Notifications, and Sandbox)**:
   - Deliverable 3.1: Prometheus Metrics Exporter (`scripts/metrics_exporter.py`).
   - Deliverable 3.3: Desktop Notification Bridge (`scripts/notify_host.sh`).
   - Deliverable 3.2: Automated Host Disk Compaction (`scripts/compact_host_disk.sh`).
   - Deliverable 4.4: Agent Workspace Virtualization (`scripts/sandbox_exec.sh`).
3. **Stage 3 (Multi-Agent Mesh and Disaster Recovery)**:
   - Deliverable 4.2: Inter-Agent Message Bus (`scripts/agent_bus.py`, `scripts/bus_send.sh`).
   - Deliverable 4.3: Automated Disaster Recovery Provisioning (`scripts/bootstrap_wsl.ps1`, `scripts/post_bootstrap.sh`).

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
    if [ "${elapsed_ns}" -lt 0 ]; then
        elapsed_ns=0
    fi
    local duration_us=$((elapsed_ns / 1000))
    local ms_int=$((elapsed_ns / 1000000))
    local ms_frac=$(((elapsed_ns % 1000000) / 10000))
    local duration_ms
    printf -v duration_ms "%d.%02d" "${ms_int}" "${ms_frac}"

    local timestamp_iso
    timestamp_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    local timestamp_epoch
    timestamp_epoch="$(date +%s)"

    local audit_log="${HARNESS_AUDIT_LOG:-${WORKSPACE_ROOT:-.}/backups/logs/harness_audit.jsonl}"

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

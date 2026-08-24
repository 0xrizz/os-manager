#!/usr/bin/env bash
# scripts/hooks/pre_tool_guard.sh - PreToolUse deterministic security policy engine
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Read JSON payload from stdin
INPUT_JSON="$(cat)"

if [ -z "${INPUT_JSON}" ]; then
    exit 0
fi

# Extract tool name using jq (fail closed on malformed JSON)
if ! TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.tool_name // .name // empty' 2>/dev/null)"; then
    echo "[HARNESS SECURITY] Failed to parse tool execution JSON payload. Failing closed." >&2
    exit 2
fi

# Source Performance Tracing Helper
if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "PreToolUse" "${TOOL_NAME:-null}"
fi

notify_security_violation() {
    local reason="$1"
    local notifier="${WORKSPACE_ROOT}/scripts/notify_host.sh"
    if [ -x "${notifier}" ]; then
        "${notifier}" --type security --title "Security Blocked" --message "${reason}" --async 2>/dev/null & disown || true
    fi
}

# 1. Primary Security Gate: Python AST Semantic Guard
PYTHON_BIN="${WORKSPACE_ROOT}/.venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

if "${PYTHON_BIN}" -c "import os_manager.security.ast_guard" 2>/dev/null; then
    AST_OUTPUT="$(echo "${INPUT_JSON}" | "${PYTHON_BIN}" -m os_manager.security.ast_guard 2>&1)" || {
        RC=$?
        echo "${AST_OUTPUT}" >&2
        notify_security_violation "${AST_OUTPUT}"
        exit "${RC}"
    }

    # If sandbox recommended, notify telemetry
    if echo "${AST_OUTPUT}" | grep -q "\[SANDBOX_RECOMMENDED\]"; then
        if command -v bwrap >/dev/null 2>&1 || command -v podman >/dev/null 2>&1; then
            echo "[SANDBOXED EXECUTION - Changes isolated to ephemeral jail]"
        fi
    fi
    exit 0
fi

# 2. Fallback: Legacy Path & Regex Evaluator (used if python environment uninitialized)
if [[ "${TOOL_NAME}" =~ ^(Edit|Write|Read)$ ]]; then
    TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
    if [ -n "${TARGET_PATH}" ]; then
        CANONICAL_PATH="${TARGET_PATH}"
        if command -v realpath >/dev/null 2>&1 && realpath -m "${TARGET_PATH}" >/dev/null 2>&1; then
            CANONICAL_PATH="$(realpath -m "${TARGET_PATH}" 2>/dev/null || echo "${TARGET_PATH}")"
        fi

        if [[ "${CANONICAL_PATH}" =~ ^/mnt/c/(Windows|Program\ Files|Program\ Files\ \(x86\)|Users/[^/]+/AppData) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of Windows Host System files is strictly forbidden: ${TARGET_PATH}" >&2
                notify_security_violation "Modification of Windows Host System files blocked: ${TARGET_PATH}"
                exit 2
            fi
        fi

        if [[ "${CANONICAL_PATH}" =~ ^/(etc/shadow|etc/passwd|boot/|dev/) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of core Linux system files is strictly forbidden: ${TARGET_PATH}" >&2
                notify_security_violation "Modification of core Linux system files blocked: ${TARGET_PATH}"
                exit 2
            fi
        fi
    fi
    exit 0
fi

if [ "${TOOL_NAME}" = "Bash" ]; then
    CMD="$(echo "${INPUT_JSON}" | jq -r '.tool_input.command // empty')"
    if [ -z "${CMD}" ]; then
        exit 0
    fi

    # Invariant Block: Destructive Root Deletion
    # shellcheck disable=SC2016
    if echo "${CMD}" | grep -qE '\brm\s+-[rRfF]*\s+(/|/\*|~|~/\*|\$HOME|\$HOME/\*|/home/[^/]+/?(\*|\.))([;&|[:space:]]|$)'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive deletion of root or home directory is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Root or home deletion blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: WSL Lifecycle
    if echo "${CMD}" | grep -qE '\b(wsl|wsl\.exe)\s+--(unregister|shutdown|terminate)\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): WSL instance lifecycle termination commands are strictly forbidden: ${CMD}" >&2
        notify_security_violation "WSL instance termination blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: Raw Disk Formatting
    if echo "${CMD}" | grep -qE '\b(mkfs(\.[a-z0-9]+)?|fdisk|parted|dd\s+if=.*of=/dev/sd[a-z])\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Raw disk formatting and block device alteration is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Raw disk formatting blocked: ${CMD}"
        exit 2
    fi
fi

exit 0

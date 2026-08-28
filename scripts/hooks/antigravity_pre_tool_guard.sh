#!/usr/bin/env bash
# scripts/hooks/antigravity_pre_tool_guard.sh - Antigravity PreToolUse security policy engine
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Read JSON payload from stdin
INPUT_JSON="$(cat)"

if [ -z "${INPUT_JSON}" ]; then
    echo '{"decision": "allow"}'
    exit 0
fi

# Source Performance Tracing Helper if available
if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.toolCall.name // .tool_name // empty' 2>/dev/null || echo "")"
    trace_start "AntigravityPreToolUse" "${TOOL_NAME:-null}"
fi

# 1. Primary Security Gate: Python AST Semantic Guard
PYTHON_BIN="${WORKSPACE_ROOT}/.venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

if "${PYTHON_BIN}" -c "import os_manager.security.ast_guard" 2>/dev/null; then
    "${PYTHON_BIN}" -m os_manager.security.ast_guard --antigravity <<< "${INPUT_JSON}"
    exit 0
fi

# 2. Fallback Regex Guard if Python environment is uninitialized
TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.toolCall.name // .tool_name // empty' 2>/dev/null || echo "")"

if [[ "${TOOL_NAME}" =~ ^(write_to_file|replace_file_content|multi_replace_file_content|Edit|Write)$ ]]; then
    TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.toolCall.args.TargetFile // .toolCall.args.AbsolutePath // .tool_input.file_path // empty')"
    if [ -n "${TARGET_PATH}" ]; then
        CANONICAL_PATH="${TARGET_PATH}"
        if command -v realpath >/dev/null 2>&1 && realpath -m "${TARGET_PATH}" >/dev/null 2>&1; then
            CANONICAL_PATH="$(realpath -m "${TARGET_PATH}" 2>/dev/null || echo "${TARGET_PATH}")"
        fi

        if [[ "${CANONICAL_PATH}" =~ ^/mnt/c/(Windows|Program\ Files|Program\ Files\ \(x86\)|Users/[^/]+/AppData) ]] || [[ "${CANONICAL_PATH}" =~ ^/(etc/shadow|etc/passwd|boot/|dev/) ]]; then
            REASON="[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of protected system path is forbidden: ${TARGET_PATH}"
            jq -n --arg reason "${REASON}" '{"decision": "deny", "reason": $reason}'
            exit 0
        fi
    fi
fi

if [[ "${TOOL_NAME}" =~ ^(run_command|Bash)$ ]]; then
    CMD="$(echo "${INPUT_JSON}" | jq -r '.toolCall.args.CommandLine // .tool_input.command // empty')"
    if [ -n "${CMD}" ]; then
        # shellcheck disable=SC2016
        if echo "${CMD}" | grep -qE '\brm\s+-[rRfF]*\s+(/|/\*|~|~/\*|\$HOME|\$HOME/\*|/home/[^/]+/?(\*|\.))([;&|[:space:]]|$)'; then
            REASON="[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive deletion of root or home directory is forbidden: ${CMD}"
            jq -n --arg reason "${REASON}" '{"decision": "deny", "reason": $reason}'
            exit 0
        fi

        if echo "${CMD}" | grep -qE '\b(wsl|wsl\.exe)\s+--(unregister|shutdown|terminate)\b'; then
            REASON="[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): WSL lifecycle sabotage commands are strictly forbidden: ${CMD}"
            jq -n --arg reason "${REASON}" '{"decision": "deny", "reason": $reason}'
            exit 0
        fi
    fi
fi

echo '{"decision": "allow"}'
exit 0

#!/usr/bin/env bash
# scripts/hooks/antigravity_post_tool_lint.sh - Antigravity PostToolUse auto-linter and quality gate
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

INPUT_JSON="$(cat)"

if [ -z "${INPUT_JSON}" ]; then
    echo '{}'
    exit 0
fi

TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.toolCall.name // .tool_name // empty' 2>/dev/null || echo "")"
if [[ ! "${TOOL_NAME}" =~ ^(write_to_file|replace_file_content|multi_replace_file_content|Edit|Write)$ ]]; then
    echo '{}'
    exit 0
fi

# Source Performance Tracing Helper if available
if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "AntigravityPostToolUse" "${TOOL_NAME}"
fi

TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.toolCall.args.TargetFile // .toolCall.args.AbsolutePath // .tool_input.file_path // empty')"
if [ -z "${TARGET_PATH}" ] || [ ! -f "${TARGET_PATH}" ]; then
    echo '{}'
    exit 0
fi

# 1. Shell Script Validation (.sh or bash shebang)
if [[ "${TARGET_PATH}" =~ \.sh$ ]] || head -n 1 "${TARGET_PATH}" 2>/dev/null | grep -qE '^#!.*(bash|sh)'; then
    if ! BASH_ERR="$(bash -n "${TARGET_PATH}" 2>&1)"; then
        echo "[HARNESS QUALITY GATE] Shell syntax error detected in ${TARGET_PATH}:" >&2
        echo "${BASH_ERR}" >&2
    fi

    if command -v shellcheck >/dev/null 2>&1; then
        if ! SC_ERR="$(shellcheck -e SC1090,SC1091 "${TARGET_PATH}" 2>&1)"; then
            echo "[HARNESS QUALITY GATE] ShellCheck issues detected in ${TARGET_PATH}:" >&2
            echo "${SC_ERR}" >&2
        fi
    fi
fi

# 2. JSON File Validation (.json)
if [[ "${TARGET_PATH}" =~ \.json$ ]]; then
    if ! JQ_ERR="$(jq empty "${TARGET_PATH}" 2>&1)"; then
        echo "[HARNESS QUALITY GATE] Invalid JSON formatting detected in ${TARGET_PATH}:" >&2
        echo "${JQ_ERR}" >&2
    fi
fi

# 3. Python File Validation (.py)
if [[ "${TARGET_PATH}" =~ \.py$ ]]; then
    if command -v python3 >/dev/null 2>&1; then
        if ! PY_ERR="$(python3 -m py_compile "${TARGET_PATH}" 2>&1)"; then
            echo "[HARNESS QUALITY GATE] Python compilation error detected in ${TARGET_PATH}:" >&2
            echo "${PY_ERR}" >&2
        fi
    fi
fi

echo '{}'
exit 0

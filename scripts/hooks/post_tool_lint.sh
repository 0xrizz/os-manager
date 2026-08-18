#!/usr/bin/env bash
# scripts/hooks/post_tool_lint.sh - PostToolUse auto-healing linter and syntax validator
set -euo pipefail

INPUT_JSON="$(cat)"

if [ -z "${INPUT_JSON}" ]; then
    exit 0
fi

TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.tool_name // .name // empty' 2>/dev/null || echo "")"
if [[ ! "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
    exit 0
fi

TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.tool_input.file_path // empty')"
if [ -z "${TARGET_PATH}" ] || [ ! -f "${TARGET_PATH}" ]; then
    exit 0
fi

# 1. Shell Script Validation (.sh or bash shebang)
if [[ "${TARGET_PATH}" =~ \.sh$ ]] || head -n 1 "${TARGET_PATH}" 2>/dev/null | grep -qE '^#!.*(bash|sh)'; then
    # Syntax check with bash -n
    if ! BASH_ERR="$(bash -n "${TARGET_PATH}" 2>&1)"; then
        echo "[HARNESS QUALITY GATE] Shell syntax error detected in ${TARGET_PATH}:" >&2
        echo "${BASH_ERR}" >&2
        echo "Please correct the syntax error immediately." >&2
        exit 2
    fi

    # Optional shellcheck check if installed
    if command -v shellcheck >/dev/null 2>&1; then
        if ! SC_ERR="$(shellcheck -e SC1090,SC1091 "${TARGET_PATH}" 2>&1)"; then
            echo "[HARNESS QUALITY GATE] ShellCheck issues detected in ${TARGET_PATH}:" >&2
            echo "${SC_ERR}" >&2
            echo "Please resolve these linting warnings." >&2
            exit 2
        fi
    fi
fi

# 2. JSON File Validation (.json)
if [[ "${TARGET_PATH}" =~ \.json$ ]]; then
    if ! JQ_ERR="$(jq empty "${TARGET_PATH}" 2>&1)"; then
        echo "[HARNESS QUALITY GATE] Invalid JSON formatting detected in ${TARGET_PATH}:" >&2
        echo "${JQ_ERR}" >&2
        echo "Please fix the JSON syntax." >&2
        exit 2
    fi
fi

# 3. Python File Validation (.py)
if [[ "${TARGET_PATH}" =~ \.py$ ]]; then
    if command -v python3 >/dev/null 2>&1; then
        if ! PY_ERR="$(python3 -m py_compile "${TARGET_PATH}" 2>&1)"; then
            echo "[HARNESS QUALITY GATE] Python compilation error detected in ${TARGET_PATH}:" >&2
            echo "${PY_ERR}" >&2
            echo "Please fix the Python syntax error." >&2
            exit 2
        fi
    fi
fi

exit 0

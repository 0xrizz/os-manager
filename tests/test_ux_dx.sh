#!/usr/bin/env bash
# tests/test_ux_dx.sh - Unit tests for UX and DX Enhancements
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOKS_DIR="${WORKSPACE_ROOT}/scripts/hooks"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_exit_code() {
    local test_name="$1"
    local expected_code="$2"
    local actual_code="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ "${actual_code}" -eq "${expected_code}" ]; then
        echo "  [PASS] ${test_name} (exit code: ${actual_code})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected: ${expected_code}, got: ${actual_code})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

assert_output_contains() {
    local test_name="$1"
    local expected_text="$2"
    local actual_output="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "${actual_output}" | grep -qF "${expected_text}"; then
        echo "  [PASS] ${test_name} (found '${expected_text}')"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (missing '${expected_text}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running UX & DX Enhancements Test Suite"
echo "=================================================="

echo "--- 1. Testing Hard Veto vs Auto-Sandbox Fallback ---"
set +e

# Hard Veto: Windows Host Sabotage
PAYLOAD_WINDOWS_EDIT="{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"/mnt/c/Windows/System32/drivers/etc/hosts\",\"old_string\":\"a\",\"new_string\":\"b\"}}"
OUT_WIN=$(echo "${PAYLOAD_WINDOWS_EDIT}" | "${HOOKS_DIR}/pre_tool_guard.sh" 2>&1)
assert_exit_code "Hard Veto: Windows System File Modification" 2 $?
assert_output_contains "Hard Veto Diagnostic Message" "strictly forbidden" "${OUT_WIN}"

# Hard Veto: Root Obliteration
PAYLOAD_ROOT_RM='{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}'
OUT_ROOT=$(echo "${PAYLOAD_ROOT_RM}" | "${HOOKS_DIR}/pre_tool_guard.sh" 2>&1)
assert_exit_code "Hard Veto: Root Obliteration (rm -rf /)" 2 $?
assert_output_contains "Hard Veto Root Message" "strictly forbidden" "${OUT_ROOT}"

# Auto-Sandbox: Risky Project Deletion (rm -rf ./temp_build)
PAYLOAD_RISKY_RM='{"tool_name":"Bash","tool_input":{"command":"rm -rf ./temp_build"}}'
OUT_RISKY=$(echo "${PAYLOAD_RISKY_RM}" | "${HOOKS_DIR}/pre_tool_guard.sh" 2>&1)
assert_exit_code "Auto-Sandbox: Project Deletion (rm -rf ./temp_build)" 0 $?
if command -v podman >/dev/null 2>&1; then
    assert_output_contains "Auto-Sandbox: Notice Emitted" "SANDBOXED EXECUTION" "${OUT_RISKY}"
fi

echo "--- 2. Testing Micro-Badges & Dashboard in sys_diag.sh ---"
# Default Compact ASCII Card
DIAG_OUTPUT=$("${WORKSPACE_ROOT}/scripts/sys_diag.sh" 2>&1)
assert_exit_code "sys_diag.sh Execution" 0 $?
assert_output_contains "Dashboard Card Header" "os-manager" "${DIAG_OUTPUT}"
assert_output_contains "Micro-Badge [OK]" "[OK]" "${DIAG_OUTPUT}"

# JSON Output Mode
DIAG_JSON=$("${WORKSPACE_ROOT}/scripts/sys_diag.sh" --json 2>&1)
assert_exit_code "sys_diag.sh --json Execution" 0 $?
assert_output_contains "JSON Schema Field (status)" '"status"' "${DIAG_JSON}"

echo "--- 3. Testing Installer Idempotency ---"
TEMP_INSTALL_DIR=$(mktemp -d)
mkdir -p "${TEMP_INSTALL_DIR}/.claude"
echo '{"permissions":{"allow":["git status"]}}' > "${TEMP_INSTALL_DIR}/.claude/settings.json"

# First install pass
"${WORKSPACE_ROOT}/install.sh" --project "${TEMP_INSTALL_DIR}" > /dev/null 2>&1
assert_exit_code "Installer First Run" 0 $?

# Second install pass (Idempotency)
"${WORKSPACE_ROOT}/install.sh" --project "${TEMP_INSTALL_DIR}" > /dev/null 2>&1
assert_exit_code "Installer Second Run (Idempotency)" 0 $?

# Validate valid JSON preserved
jq empty "${TEMP_INSTALL_DIR}/.claude/settings.json" > /dev/null 2>&1
assert_exit_code "Settings JSON Valid After Merge" 0 $?
rm -rf "${TEMP_INSTALL_DIR}"

set -e

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

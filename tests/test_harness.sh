#!/usr/bin/env bash
# tests/test_harness.sh - Test suite for os-manager Claude Harness
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

echo "=================================================="
echo "Running Claude Code Harness Test Suite"
echo "=================================================="

echo "--- Testing Session Preflight & Cleanup Hooks ---"
set +e
"${HOOKS_DIR}/session_preflight.sh" > /dev/null 2>&1
assert_exit_code "session_preflight.sh execution" 0 $?

"${HOOKS_DIR}/session_cleanup.sh" > /dev/null 2>&1
assert_exit_code "session_cleanup.sh execution" 0 $?
set -e

echo "--- Testing PreToolGuard 4-Tier Security Matrix ---"
set +e

# Tier 0 Allow: git status
PAYLOAD_TIER0='{"tool_name":"Bash","tool_input":{"command":"git status"}}'
echo "${PAYLOAD_TIER0}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 0 Read-Only Command (git status)" 0 $?

# Tier 1 Allow: Workspace file edit
PAYLOAD_TIER1="{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"${WORKSPACE_ROOT}/CLAUDE.md\",\"old_string\":\"a\",\"new_string\":\"b\"}}"
echo "${PAYLOAD_TIER1}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 1 Workspace Contained Edit" 0 $?

# Tier 2 Allow: Maintenance script
PAYLOAD_TIER2='{"tool_name":"Bash","tool_input":{"command":"./scripts/sys_diag.sh"}}'
echo "${PAYLOAD_TIER2}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 2 Whitelisted Script (sys_diag.sh)" 0 $?

# Tier 3 Block: Root obliteration
PAYLOAD_TIER3_ROOT='{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}'
echo "${PAYLOAD_TIER3_ROOT}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (rm -rf /)" 2 $?

# Tier 3 Block: WSL lifecycle sabotage
PAYLOAD_TIER3_WSL='{"tool_name":"Bash","tool_input":{"command":"wsl.exe --unregister Debian"}}'
echo "${PAYLOAD_TIER3_WSL}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (wsl --unregister)" 2 $?

# Tier 3 Block: Windows System Host Write
PAYLOAD_TIER3_WIN='{"tool_name":"Write","tool_input":{"file_path":"/mnt/c/Windows/System32/drivers/etc/hosts","content":"127.0.0.1 test"}}'
echo "${PAYLOAD_TIER3_WIN}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (Windows System Host Write)" 2 $?

set -e

echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi

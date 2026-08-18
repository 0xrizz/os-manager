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

# Test PreToolGuard exists
if [ ! -f "${HOOKS_DIR}/pre_tool_guard.sh" ]; then
    echo "  [FAIL] scripts/hooks/pre_tool_guard.sh does not exist"
    exit 1
fi

echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi

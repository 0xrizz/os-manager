#!/usr/bin/env bash
# tests/test_sandbox.sh - Unit tests for Agent Workspace Virtualization
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SANDBOX_SCRIPT="${WORKSPACE_ROOT}/scripts/sandbox_exec.sh"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_contains() {
    local test_name="$1"
    local haystack="$2"
    local needle="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "${haystack}" | grep -qF -- "${needle}"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected to contain '${needle}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

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
echo "Running Agent Workspace Virtualization Unit Tests"
echo "=================================================="

# 1. Script existence and executable permission
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${SANDBOX_SCRIPT}" ]; then
    echo "  [PASS] sandbox_exec.sh exists and is executable"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] sandbox_exec.sh missing or not executable at ${SANDBOX_SCRIPT}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Test --help flag
set +e
HELP_OUT="$("${SANDBOX_SCRIPT}" --help 2>&1)"
assert_exit_code "--help flag exit code" 0 $?
assert_contains "--help output content" "${HELP_OUT}" "Usage:"
set -e

# 3. Test --dry-run standard container assembly
DRY_RUN_OUT="$("${SANDBOX_SCRIPT}" --dry-run --target-dir "${WORKSPACE_ROOT}" -- echo "hello")"
assert_contains "dry-run contains podman run" "${DRY_RUN_OUT}" "podman run"
assert_contains "dry-run contains --read-only" "${DRY_RUN_OUT}" "--read-only"
assert_contains "dry-run contains --userns=keep-id" "${DRY_RUN_OUT}" "--userns=keep-id"
assert_contains "dry-run contains --cap-drop=ALL" "${DRY_RUN_OUT}" "--cap-drop=ALL"
assert_contains "dry-run contains --security-opt=no-new-privileges" "${DRY_RUN_OUT}" "--security-opt=no-new-privileges"
assert_contains "dry-run contains --pids-limit=256" "${DRY_RUN_OUT}" "--pids-limit=256"
assert_contains "dry-run contains workspace mount" "${DRY_RUN_OUT}" "-v ${WORKSPACE_ROOT}:/workspace:rw,z"
assert_contains "dry-run contains target command" "${DRY_RUN_OUT}" "echo hello"

# 4. Test resource constraints and network flags
CUSTOM_DRY="$("${SANDBOX_SCRIPT}" --dry-run --target-dir "${WORKSPACE_ROOT}" --mem 512m --cpus 1 --network slirp4netns --read-only -- ls -la)"
assert_contains "custom memory limit" "${CUSTOM_DRY}" "--memory=512m"
assert_contains "custom cpus limit" "${CUSTOM_DRY}" "--cpus=1"
assert_contains "custom network mode" "${CUSTOM_DRY}" "--network=slirp4netns"
assert_contains "read-only mount mode" "${CUSTOM_DRY}" ":ro,z"

# 5. Test workspace boundary violation (target directory outside dev root)
EXPECTED_DEV_ROOT="$(realpath -m "${OSM_DEV_ROOT:-${HOME}/dev}")"
set +e
BOUNDARY_OUT="$("${SANDBOX_SCRIPT}" --dry-run --target-dir "/etc" -- echo "fail" 2>&1)"
BOUNDARY_EXIT=$?
assert_exit_code "Boundary violation blocked with Exit 2" 2 "${BOUNDARY_EXIT}"
assert_contains "Boundary violation error message" "${BOUNDARY_OUT}" "must reside strictly under ${EXPECTED_DEV_ROOT}"

WINDOWS_MOUNT_OUT="$("${SANDBOX_SCRIPT}" --dry-run --target-dir "/mnt/c/Windows" -- echo "fail" 2>&1)"
WINDOWS_MOUNT_EXIT=$?
assert_exit_code "Windows mount target blocked with Exit 2" 2 "${WINDOWS_MOUNT_EXIT}"
assert_contains "Windows mount error message" "${WINDOWS_MOUNT_OUT}" "must reside strictly under ${EXPECTED_DEV_ROOT}"
set -e

echo "=================================================="
echo "Workspace Virtualization Unit Tests Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

#!/usr/bin/env bash
# tests/test_installer.sh - Unit tests for standalone shell installer
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALLER="${WORKSPACE_ROOT}/install.sh"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_equals() {
    local test_name="$1"
    local expected="$2"
    local actual="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ "${expected}" = "${actual}" ]; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected: '${expected}', got: '${actual}')"
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
echo "Running Shell Installer Unit Tests"
echo "=================================================="

# 1. Check installer existence
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -f "${INSTALLER}" ]; then
    echo "  [PASS] install.sh exists"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] install.sh missing at ${INSTALLER}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Test Help Flag
set +e
HELP_OUT="$("${INSTALLER}" --help 2>&1)"
HELP_RC=$?
set -e
assert_exit_code "Installer --help exit code" 0 "${HELP_RC}"

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if grep -q "Usage:" <<< "${HELP_OUT}"; then
    echo "  [PASS] Installer --help text content"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Installer --help missing usage text"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 3. Test Dry Run Flag
set +e
DRY_RUN_OUT="$("${INSTALLER}" --dry-run 2>&1)"
DRY_RUN_RC=$?
set -e
assert_exit_code "Installer --dry-run exit code" 0 "${DRY_RUN_RC}"

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if grep -q "\[DRY RUN\]" <<< "${DRY_RUN_OUT}"; then
    echo "  [PASS] Installer --dry-run indicator"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Installer --dry-run missing indicator"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 4. Test Project Scaffolding
TEST_PROJECT_DIR="/tmp/test_osm_scaffold_$$"
mkdir -p "${TEST_PROJECT_DIR}"

set +e
"${INSTALLER}" --project "${TEST_PROJECT_DIR}" > /dev/null 2>&1
SCAFFOLD_RC=$?
set -e
assert_exit_code "Installer --project scaffolding exit code" 0 "${SCAFFOLD_RC}"

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -d "${TEST_PROJECT_DIR}/.claude" ] && [ -f "${TEST_PROJECT_DIR}/.claude/settings.json" ]; then
    echo "  [PASS] Scaffolding directory structure created"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Scaffolding failed to create .claude/settings.json"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

rm -rf "${TEST_PROJECT_DIR}"

# 5. Test Installation and Uninstallation
MOCK_USER_HOME="/tmp/mock_home_installer_$$"
mkdir -p "${MOCK_USER_HOME}"

set +e
HOME="${MOCK_USER_HOME}" "${INSTALLER}" > /dev/null 2>&1
INSTALL_RC=$?
set -e
assert_exit_code "Standard installation exit code" 0 "${INSTALL_RC}"

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -L "${MOCK_USER_HOME}/.local/bin/osm" ] || [ -f "${MOCK_USER_HOME}/.local/bin/osm" ]; then
    echo "  [PASS] Binary symlink created in ~/.local/bin/osm"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Binary symlink missing in ~/.local/bin/osm"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -d "${MOCK_USER_HOME}/.local/state/os-manager/logs" ]; then
    echo "  [PASS] State directory created in ~/.local/state/os-manager/logs"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] State directory missing in ~/.local/state/os-manager/logs"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test Uninstall
set +e
HOME="${MOCK_USER_HOME}" "${INSTALLER}" --uninstall > /dev/null 2>&1
UNINSTALL_RC=$?
set -e
assert_exit_code "Installer --uninstall exit code" 0 "${UNINSTALL_RC}"

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ ! -e "${MOCK_USER_HOME}/.local/bin/osm" ]; then
    echo "  [PASS] Binary symlink removed on uninstall"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Binary symlink persists after uninstall"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

rm -rf "${MOCK_USER_HOME}"

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi

#!/usr/bin/env bash
# tests/test_install_github_cli.sh - Unit tests for GitHub CLI installer script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALLER="${WORKSPACE_ROOT}/scripts/install_github_cli.sh"

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
    local output="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "${output}" | grep -F -- "${expected_text}" > /dev/null; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected '${expected_text}' in output)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running GitHub CLI Installer Test Suite"
echo "=================================================="

# 1. Script existence and executable check
assert_exit_code "Installer script is executable" 0 $([ -x "${INSTALLER}" ] && echo 0 || echo 1)

# 2. Help flag check
HELP_OUT="$("${INSTALLER}" --help 2>&1 || true)"
assert_output_contains "Installer prints help text" "Usage: install_github_cli.sh" "${HELP_OUT}"
assert_output_contains "Installer documents --dry-run" "--dry-run" "${HELP_OUT}"
assert_output_contains "Installer documents --check" "--check" "${HELP_OUT}"

# 3. Dry-run output check
DRY_OUT="$("${INSTALLER}" --dry-run 2>&1 || true)"
assert_output_contains "Dry run includes keyring URL" "cli.github.com/packages/githubcli-archive-keyring.gpg" "${DRY_OUT}"
assert_output_contains "Dry run references expected SHA256" "6084d5d7bd8e288441e0e94fc6275570895da18e6751f70f057485dc2d1a811b" "${DRY_OUT}"
assert_output_contains "Dry run targets /etc/apt/keyrings" "/etc/apt/keyrings" "${DRY_OUT}"
assert_output_contains "Dry run targets /etc/apt/sources.list.d/github-cli.list" "/etc/apt/sources.list.d/github-cli.list" "${DRY_OUT}"

# 4. Unknown option rejection
set +e
"${INSTALLER}" --invalid-flag >/dev/null 2>&1
INVALID_RC=$?
set -e
assert_exit_code "Installer rejects invalid flags with exit code 1" 1 "${INVALID_RC}"

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

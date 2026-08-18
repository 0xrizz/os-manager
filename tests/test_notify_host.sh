#!/usr/bin/env bash
# tests/test_notify_host.sh - Unit tests for Desktop Notification Bridge
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NOTIFIER_SCRIPT="${WORKSPACE_ROOT}/scripts/notify_host.sh"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_contains() {
    local test_name="$1"
    local haystack="$2"
    local needle="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "${haystack}" | grep -qF "${needle}"; then
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
echo "Running Desktop Notification Bridge Unit Tests"
echo "=================================================="

# 1. Script existence and executable permission
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${NOTIFIER_SCRIPT}" ]; then
    echo "  [PASS] notify_host.sh exists and is executable"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] notify_host.sh missing or not executable at ${NOTIFIER_SCRIPT}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Test --help flag
set +e
HELP_OUT="$("${NOTIFIER_SCRIPT}" --help 2>&1)"
assert_exit_code "--help flag exit code" 0 $?
assert_contains "--help output content" "${HELP_OUT}" "Usage:"
set -e

# 3. Test --dry-run standard toast generation
DRY_RUN_OUT="$("${NOTIFIER_SCRIPT}" --dry-run --title "Test Title" --message "Test Message" --type info)"
assert_contains "dry-run contains title" "${DRY_RUN_OUT}" "Test Title"
assert_contains "dry-run contains message" "${DRY_RUN_OUT}" "Test Message"
assert_contains "dry-run contains WinRT Toast XML" "${DRY_RUN_OUT}" "ToastNotificationManager"
assert_contains "dry-run contains audio cue" "${DRY_RUN_OUT}" "Notification.Default"

# 4. Test security alert audio mapping
SEC_OUT="$("${NOTIFIER_SCRIPT}" --dry-run --title "Security Block" --message "Invariant Blocked" --type security)"
assert_contains "security alert urgent sound" "${SEC_OUT}" "Notification.Urgent"

# 5. Test XML entity and shell special character escaping
# shellcheck disable=SC2016
ESCAPE_OUT="$("${NOTIFIER_SCRIPT}" --dry-run --title "Alert & <Special>" --message 'Quotes "and" $variables and `backticks`' --type error)"
assert_contains "XML ampersand escaping" "${ESCAPE_OUT}" "Alert &amp; &lt;Special&gt;"
assert_contains "XML quote escaping" "${ESCAPE_OUT}" '&quot;and&quot;'
# shellcheck disable=SC2016
assert_contains "PowerShell variable escaping" "${ESCAPE_OUT}" '`$variables'
# shellcheck disable=SC2016
assert_contains "PowerShell backtick escaping" "${ESCAPE_OUT}" '``backticks``'

# 6. Test --silent flag suppresses audio
SILENT_OUT="$("${NOTIFIER_SCRIPT}" --dry-run --title "Silent" --message "Shh" --silent)"
assert_contains "silent attribute enabled" "${SILENT_OUT}" 'silent="true"'

# 7. Test rate limiting / debouncing
set +e
RATE_LIMIT_CAT="unit_test_debounce"
"${NOTIFIER_SCRIPT}" --title "Rate1" --message "M1" --category "${RATE_LIMIT_CAT}" > /dev/null 2>&1
FIRST_EXIT=$?
"${NOTIFIER_SCRIPT}" --title "Rate2" --message "M2" --category "${RATE_LIMIT_CAT}" > /dev/null 2>&1
SECOND_EXIT=$?
assert_exit_code "First notification succeeds" 0 ${FIRST_EXIT}
assert_exit_code "Rapid duplicate category debounced cleanly" 0 ${SECOND_EXIT}
set -e

# Clean up temporary test rate-limiting lockfiles
rm -f /tmp/.os_manager_notify_ratelimit_"${RATE_LIMIT_CAT}"

echo "=================================================="
echo "Notification Bridge Unit Tests Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

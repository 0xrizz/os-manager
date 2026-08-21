#!/usr/bin/env bash
# tests/test_switch_boot.sh - Unit tests for switch_boot_to_new_root.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SWITCH_SCRIPT="${WORKSPACE_ROOT}/scripts/migration/switch_boot_to_new_root.sh"

TOTAL_TESTS=0
PASSED_TESTS=0

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
        exit 1
    fi
}

echo "=================================================="
echo " Running GRUB Boot Switch Unit Tests              "
echo "=================================================="

# 1. Script existence and executable check
test -x "${SWITCH_SCRIPT}"
assert_exit_code "switch_boot_to_new_root.sh is executable" 0 $?

# 2. Syntax validation
bash -n "${SWITCH_SCRIPT}"
assert_exit_code "switch_boot_to_new_root.sh syntax check (bash -n)" 0 $?

# 3. Help dialog test
"${SWITCH_SCRIPT}" --help >/dev/null 2>&1
assert_exit_code "switch_boot_to_new_root.sh --help" 0 $?

# 4. Dry-run execution test
"${SWITCH_SCRIPT}" --dry-run >/dev/null 2>&1
assert_exit_code "switch_boot_to_new_root.sh --dry-run" 0 $?

# 5. Custom parameters in dry-run
"${SWITCH_SCRIPT}" --dry-run --root /dev/nvme0n1p2 --efi /dev/nvme0n1p1 >/dev/null 2>&1
assert_exit_code "switch_boot_to_new_root.sh --dry-run with --root and --efi" 0 $?

# 6. Zero personal path leaks check
! grep -rnI "/home/rizz" "${SWITCH_SCRIPT}" >/dev/null 2>&1
assert_exit_code "Zero personal path leaks in switch_boot_to_new_root.sh" 0 $?

echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} tests passed."

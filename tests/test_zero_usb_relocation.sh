#!/usr/bin/env bash
# tests/test_zero_usb_relocation.sh - Unit & integration tests for Zero-USB root relocation
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RELOCATE_SCRIPT="${WORKSPACE_ROOT}/scripts/migration/zero_usb_root_relocate.sh"

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

assert_true() {
    local test_name="$1"
    local condition="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if eval "${condition}"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name}"
        exit 1
    fi
}

echo "=================================================="
echo " Running Zero-USB Root Relocation Unit Tests      "
echo "=================================================="

# 1. Script existence and executable permissions
assert_true "zero_usb_root_relocate.sh exists and is executable" "[[ -x '${RELOCATE_SCRIPT}' ]]"

# 2. Script syntax check
bash -n "${RELOCATE_SCRIPT}"
assert_exit_code "zero_usb_root_relocate.sh syntax check (bash -n)" 0 $?

# 3. Help dialog check
"${RELOCATE_SCRIPT}" --help >/dev/null 2>&1
assert_exit_code "zero_usb_root_relocate.sh --help" 0 $?

# 4. Dry-run execution check
"${RELOCATE_SCRIPT}" --dry-run >/dev/null 2>&1
assert_exit_code "zero_usb_root_relocate.sh --dry-run" 0 $?

# 5. Custom disk parameter check in dry-run
"${RELOCATE_SCRIPT}" --dry-run --disk /dev/nvme0n1 >/dev/null 2>&1
assert_exit_code "zero_usb_root_relocate.sh --dry-run with --disk" 0 $?

# 6. Verify script contains Zero-Data-Loss UUID guardrail
grep -q "6C7AB7E37AB7A7EA" "${RELOCATE_SCRIPT}"
assert_exit_code "Partition 4 DATA_STORE UUID Guardrail (6C7AB7E37AB7A7EA) present" 0 $?

# 7. Verify script contains rsync exclusions for virtual filesystems
grep -q -- "--exclude=" "${RELOCATE_SCRIPT}"
assert_exit_code "Virtual filesystem exclusions present in rsync command" 0 $?

# 8. Verify no personal username path leaks (/home/rizz)
assert_true "Zero personal path leaks (/home/rizz) in script" "! grep -q '/home/rizz' '${RELOCATE_SCRIPT}'"

# 9. Verify dynamic swapfile allocation is present
grep -q "mkswap" "${RELOCATE_SCRIPT}"
assert_exit_code "Dynamic swapfile allocation present in script" 0 $?

# 10. Verify systemd one-shot expansion service staging is present
grep -q "zero-usb-finalize-expansion.service" "${RELOCATE_SCRIPT}"
assert_exit_code "Systemd one-shot expansion service staging present" 0 $?

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} tests passed."
echo "=================================================="

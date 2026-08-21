#!/usr/bin/env bash
# tests/test_upgrade_preflight.sh - Unit & Mock Test Suite for Debian 13 Upgrade Preflight & Backup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
UPGRADE_SCRIPT="${WORKSPACE_ROOT}/scripts/upgrade_debian_trixie.sh"

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

echo "=================================================="
echo "Running Debian 13 Upgrade Pre-Flight Test Suite"
echo "=================================================="

# 1. Script existence and executable permission
assert_exit_code "Script exists and is executable" 0 $([ -x "${UPGRADE_SCRIPT}" ] && echo 0 || echo 1)

# 2. Help output test
set +e
HELP_OUT="$("${UPGRADE_SCRIPT}" --help 2>&1)"
HELP_RC=$?
set -e
assert_exit_code "--help returns exit code 0" 0 "${HELP_RC}"
assert_contains "--help documents --check" "${HELP_OUT}" "--check"
assert_contains "--help documents --dry-run" "${HELP_OUT}" "--dry-run"
assert_contains "--help documents --backup-only" "${HELP_OUT}" "--backup-only"
assert_contains "--help documents --allow-unattached" "${HELP_OUT}" "--allow-unattached"

# 3. AC Power Check Failure (Battery only simulation)
set +e
POWER_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_POWER_AC=0 "${UPGRADE_SCRIPT}" --check 2>&1)"
POWER_FAIL_RC=$?
set -e
assert_exit_code "Running on battery fails with code 2" 2 "${POWER_FAIL_RC}"
assert_contains "Power failure outputs AC adapter error" "${POWER_FAIL_OUT}" "AC power adapter is not connected"

# 4. Low Virtual Memory Headroom (< 2048 MB)
set +e
MEM_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_MEM_AVAIL_KB=1000000 OSM_MOCK_SWAP_TOTAL_KB=500000 "${UPGRADE_SCRIPT}" --check 2>&1)"
MEM_FAIL_RC=$?
set -e
assert_exit_code "Insufficient virtual memory fails with code 2" 2 "${MEM_FAIL_RC}"
assert_contains "Memory failure outputs virtual memory error" "${MEM_FAIL_OUT}" "Insufficient available virtual memory"

# 5. Multiplexer Session Check (Unattached terminal should fail without flag)
set +e
UNATTACHED_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=0 TMUX="" STY="" "${UPGRADE_SCRIPT}" --check 2>&1)"
UNATTACHED_RC=$?
set -e
assert_exit_code "Unattached terminal without tmux fails with code 2" 2 "${UNATTACHED_RC}"
assert_contains "Unattached terminal displays tmux warning" "${UNATTACHED_OUT}" "tmux or screen session"

# 6. Multiplexer Session Check (With simulated TMUX)
set +e
ATTACHED_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 "${UPGRADE_SCRIPT}" --check 2>&1)"
ATTACHED_RC=$?
set -e
assert_exit_code "Pre-flight passes inside simulated tmux" 0 "${ATTACHED_RC}"
assert_contains "Pre-flight logs Multiplexer pass" "${ATTACHED_OUT}" "Terminal Multiplexer"

# 7. Low Root Disk Space Check (15 GB threshold)
set +e
ROOT_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_ROOT_FREE_KB=12000000 "${UPGRADE_SCRIPT}" --check 2>&1)"
ROOT_FAIL_RC=$?
set -e
assert_exit_code "Insufficient / root space (<15GB) fails with code 2" 2 "${ROOT_FAIL_RC}"
assert_contains "Insufficient / root space outputs headroom error" "${ROOT_FAIL_OUT}" "Insufficient free space on /"

# 8. Boot Headroom Check (1.0 GB threshold)
set +e
BOOT_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_BOOT_FREE_KB=500000 "${UPGRADE_SCRIPT}" --check 2>&1)"
BOOT_FAIL_RC=$?
set -e
assert_exit_code "Insufficient /boot space fails with code 2" 2 "${BOOT_FAIL_RC}"
assert_contains "Insufficient /boot space outputs headroom error" "${BOOT_FAIL_OUT}" "Insufficient free space on /boot"

# 9. Unmounted /boot/efi Detection
set +e
EFI_UNMOUNT_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_EFI_MOUNTED=0 "${UPGRADE_SCRIPT}" --check 2>&1)"
EFI_UNMOUNT_RC=$?
set -e
assert_exit_code "Unmounted /boot/efi fails with code 2" 2 "${EFI_UNMOUNT_RC}"
assert_contains "Unmounted /boot/efi outputs mountpoint error" "${EFI_UNMOUNT_OUT}" "/boot/efi is not a mounted filesystem"

# 10. Debconf Pre-Seeding Execution
set +e
DEBCONF_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 "${UPGRADE_SCRIPT}" --check 2>&1)"
DEBCONF_RC=$?
set -e
assert_exit_code "Debconf pre-seeding completes" 0 "${DEBCONF_RC}"
assert_contains "Logs debconf pre-seeding" "${DEBCONF_OUT}" "Pre-seeding debconf selections for GRUB EFI"

# 11. Network connectivity failure
set +e
NET_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_NETWORK_FAIL=1 "${UPGRADE_SCRIPT}" --check 2>&1)"
NET_FAIL_RC=$?
set -e
assert_exit_code "Network probe failure fails with code 2" 2 "${NET_FAIL_RC}"
assert_contains "Network probe failure outputs mirror error" "${NET_FAIL_OUT}" "Cannot reach Debian mirror"

# 12. Broken DPKG audit check
set +e
DPKG_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_DPKG_AUDIT_FAIL=1 "${UPGRADE_SCRIPT}" --check 2>&1)"
DPKG_FAIL_RC=$?
set -e
assert_exit_code "Broken dpkg audit fails with code 2" 2 "${DPKG_FAIL_RC}"
assert_contains "Broken dpkg outputs audit error" "${DPKG_FAIL_OUT}" "Broken or inconsistent packages detected"

echo "=================================================="
echo "Task 1 Pre-Flight Tests: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

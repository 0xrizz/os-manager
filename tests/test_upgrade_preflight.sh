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

# --- Task 2: Backup & Manifest Tests ---
echo "=================================================="
echo "Running Debian 13 State Backup & Dual-Target Tests"
echo "=================================================="

TEST_BACKUP_DIR="$(mktemp -d /tmp/osm_test_backup_XXXXXX)"
TEST_SECONDARY_DIR="$(mktemp -d /tmp/osm_test_secondary_XXXXXX)"
trap 'rm -rf "${TEST_BACKUP_DIR}" "${TEST_SECONDARY_DIR}"' EXIT

set +e
BACKUP_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_BACKUP_DIR="${TEST_BACKUP_DIR}" OSM_SECONDARY_BACKUP_DIR="${TEST_SECONDARY_DIR}" "${UPGRADE_SCRIPT}" --backup-only 2>&1)"
BACKUP_RC=$?
set -e

assert_exit_code "--backup-only exits 0" 0 "${BACKUP_RC}"
assert_contains "Logs backup initiation" "${BACKUP_OUT}" "Phase 1: State Backup & Manifest Snapshot"
assert_contains "Logs backup completion" "${BACKUP_OUT}" "Phase 1 Backup completed successfully"

# Check created primary artifacts
assert_exit_code "APT backup directory exists" 0 $([ -d "${TEST_BACKUP_DIR}/apt" ] && echo 0 || echo 1)
assert_exit_code "etc_config_snapshot.tar.gz exists" 0 $([ -s "${TEST_BACKUP_DIR}/etc_config_snapshot.tar.gz" ] && echo 0 || echo 1)
assert_exit_code "dpkg_selections.txt exists" 0 $([ -s "${TEST_BACKUP_DIR}/dpkg_selections.txt" ] && echo 0 || echo 1)
assert_exit_code "apt_manual_pkgs.txt exists" 0 $([ -s "${TEST_BACKUP_DIR}/apt_manual_pkgs.txt" ] && echo 0 || echo 1)
assert_exit_code "upgrade_manifest.json exists" 0 $([ -s "${TEST_BACKUP_DIR}/upgrade_manifest.json" ] && echo 0 || echo 1)

# Check secondary NTFS tarball mirror
assert_exit_code "Secondary tarball mirror created" 0 $(ls "${TEST_SECONDARY_DIR}"/apt_pre_trixie_*.tar.gz >/dev/null 2>&1 && echo 0 || echo 1)
assert_exit_code "Emergency rescue script created" 0 $([ -x "${TEST_SECONDARY_DIR}/emergency_rescue.sh" ] && echo 0 || echo 1)

# Validate emergency_rescue.sh content
RESCUE_CONTENT="$(cat "${TEST_SECONDARY_DIR}/emergency_rescue.sh")"
assert_contains "Rescue script contains efivars bind mount" "${RESCUE_CONTENT}" "/sys/firmware/efi/efivars"
assert_contains "Rescue script contains offline dpkg --root" "${RESCUE_CONTENT}" 'dpkg --root="${TARGET_MOUNT}" --configure -a'
assert_contains "Rescue script contains GPU recovery flags" "${RESCUE_CONTENT}" "nouveau.modeset=0"

# Validate upgrade_manifest.json schema using python
set +e
python3 -c "
import json
with open('${TEST_BACKUP_DIR}/upgrade_manifest.json') as f:
    data = json.load(f)
assert 'timestamp' in data
assert 'kernel' in data
assert 'architecture' in data
assert 'source_version' in data
assert data['target_suite'] == 'trixie'
" 2>&1
JSON_VALID_RC=$?
set -e
assert_exit_code "upgrade_manifest.json contains required telemetry keys" 0 "${JSON_VALID_RC}"

# --- Task 3: Edge Cases & Non-Mutation Tests ---
echo "=================================================="
echo "Running Edge Cases & Non-Mutation Tests"
echo "=================================================="

# 1. Invalid argument rejection
set +e
INVALID_OUT="$("${UPGRADE_SCRIPT}" --invalid-flag 2>&1)"
INVALID_RC=$?
set -e
assert_exit_code "Invalid option exits with code 1" 1 "${INVALID_RC}"
assert_contains "Invalid option outputs error" "${INVALID_OUT}" "Unknown option: --invalid-flag"

# 2. Non-mutation verification in dry-run
SOURCES_HASH_BEFORE="$(sha256sum /etc/apt/sources.list 2>/dev/null || echo "none")"
set +e
DRY_RUN_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 "${UPGRADE_SCRIPT}" --dry-run 2>&1)"
DRY_RUN_RC=$?
set -e
SOURCES_HASH_AFTER="$(sha256sum /etc/apt/sources.list 2>/dev/null || echo "none")"

assert_exit_code "--dry-run exits with code 0" 0 "${DRY_RUN_RC}"
assert_contains "--dry-run indicates simulation" "${DRY_RUN_OUT}" "simulation mode"
assert_exit_code "/etc/apt/sources.list unchanged during dry-run" 0 $([ "${SOURCES_HASH_BEFORE}" == "${SOURCES_HASH_AFTER}" ] && echo 0 || echo 1)

# Syntax check
assert_exit_code "Script passes bash syntax check" 0 $(bash -n "${UPGRADE_SCRIPT}" && echo 0 || echo 1)

echo "=================================================="
echo "Preflight Test Suite Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

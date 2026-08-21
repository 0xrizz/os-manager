#!/usr/bin/env bash
# tests/test_upgrade_pipeline.sh - Unit & Pipeline Tests for Debian 13 Upgrade Engine
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
echo "Running Debian 13 deb822 Transition & Pipeline Tests"
echo "=================================================="

# 1. Script check
assert_exit_code "Upgrade script is executable" 0 $([ -x "${UPGRADE_SCRIPT}" ] && echo 0 || echo 1)

# 2. Test sandbox deb822 transition
SANDBOX_DIR="$(mktemp -d /tmp/osm_sandbox_apt_XXXXXX)"
SANDBOX_BACKUP="$(mktemp -d /tmp/osm_sandbox_backup_XXXXXX)"
trap 'rm -rf "${SANDBOX_DIR}" "${SANDBOX_BACKUP}"' EXIT

mkdir -p "${SANDBOX_DIR}/sources.list.d"
echo "deb http://deb.debian.org/debian bookworm main" > "${SANDBOX_DIR}/sources.list"
echo "deb https://example.com/deb bookworm main" > "${SANDBOX_DIR}/sources.list.d/external.list"

set +e
TRANSITION_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_APT_DIR="${SANDBOX_DIR}" OSM_BACKUP_DIR="${SANDBOX_BACKUP}" "${UPGRADE_SCRIPT}" --transition-only 2>&1)"
TRANSITION_RC=$?
set -e

assert_exit_code "--transition-only exits 0" 0 "${TRANSITION_RC}"

# Verify debian.sources created with deb822 format
DEB_SOURCES="${SANDBOX_DIR}/sources.list.d/debian.sources"
assert_exit_code "debian.sources exists" 0 $([ -f "${DEB_SOURCES}" ] && echo 0 || echo 1)

DEB_CONTENT="$(cat "${DEB_SOURCES}" 2>/dev/null || true)"
assert_contains "deb822 Types stanza" "${DEB_CONTENT}" "Types: deb deb-src"
assert_contains "deb822 URIs stanza" "${DEB_CONTENT}" "URIs: http://deb.debian.org/debian"
assert_contains "deb822 Suites trixie" "${DEB_CONTENT}" "Suites: trixie trixie-updates trixie-backports"
assert_contains "deb822 Components non-free-firmware" "${DEB_CONTENT}" "Components: main contrib non-free non-free-firmware"
assert_contains "deb822 Security URI" "${DEB_CONTENT}" "URIs: http://security.debian.org/debian-security"
assert_contains "deb822 Security Suite" "${DEB_CONTENT}" "Suites: trixie-security"

# Verify legacy sources.list is emptied or deduplicated
LEGACY_ACTIVE="$(grep -vE '^[[:space:]]*(#|$)' "${SANDBOX_DIR}/sources.list" 2>/dev/null || true)"
assert_exit_code "Legacy sources.list has zero active lines" 0 $([ -z "${LEGACY_ACTIVE}" ] && echo 0 || echo 1)

# Verify third-party repo is disabled
assert_exit_code "External list renamed to disabled" 0 $([ -f "${SANDBOX_DIR}/sources.list.d/external.list.disabled_for_upgrade" ] && echo 0 || echo 1)

# --- Task 2: Staged Upgrade & Emergency Repair Tests ---
echo "=================================================="
echo "Running Staged Upgrade & Emergency Repair Tests"
echo "=================================================="

# 1. Test Mocked Full Pipeline Execution
set +e
APPLY_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_APT=1 OSM_APT_DIR="${SANDBOX_DIR}" OSM_BACKUP_DIR="${SANDBOX_BACKUP}" "${UPGRADE_SCRIPT}" --apply --non-interactive 2>&1)"
APPLY_RC=$?
set -e

assert_exit_code "Mocked full upgrade pipeline exits 0" 0 "${APPLY_RC}"
assert_contains "Executes Phase 0 Preflight" "${APPLY_OUT}" "Phase 0: Pre-Flight Verification Gate"
assert_contains "Executes Phase 1 Backup" "${APPLY_OUT}" "Phase 1: State Backup"
assert_contains "Executes Phase 2 Transition" "${APPLY_OUT}" "Phase 2: APT deb822 Repository Matrix Transition"
assert_contains "Point of No Return acknowledged" "${APPLY_OUT}" "POINT OF NO RETURN"
assert_contains "Executes Phase 3 Minimal Upgrade" "${APPLY_OUT}" "Phase 3: Minimal Safe Upgrade"
assert_contains "Executes intermediate cache purge" "${APPLY_OUT}" "apt-get clean"
assert_contains "Queues SOF audio firmware" "${APPLY_OUT}" "firmware-sof-signed"
assert_contains "Executes Phase 4 Full Upgrade" "${APPLY_OUT}" "Phase 4: Full Distribution Upgrade"

# 2. Test Emergency DPKG Repair Trigger on APT Failure
SANDBOX_FAIL_DIR="$(mktemp -d /tmp/osm_sandbox_fail_XXXXXX)"
SANDBOX_FAIL_BACKUP="$(mktemp -d /tmp/osm_sandbox_fail_bak_XXXXXX)"
trap 'rm -rf "${SANDBOX_DIR}" "${SANDBOX_BACKUP}" "${SANDBOX_FAIL_DIR}" "${SANDBOX_FAIL_BACKUP}"' EXIT

mkdir -p "${SANDBOX_FAIL_DIR}/sources.list.d"
echo "deb http://deb.debian.org/debian bookworm main" > "${SANDBOX_FAIL_DIR}/sources.list"

set +e
FAIL_APPLY_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_APT=1 OSM_MOCK_APT_FAIL=1 OSM_APT_DIR="${SANDBOX_FAIL_DIR}" OSM_BACKUP_DIR="${SANDBOX_FAIL_BACKUP}" "${UPGRADE_SCRIPT}" --apply --non-interactive 2>&1)"
FAIL_APPLY_RC=$?
set -e

assert_exit_code "Failed upgrade exits with code 3" 3 "${FAIL_APPLY_RC}"
assert_contains "Emergency repair triggered" "${FAIL_APPLY_OUT}" "Triggering Emergency DPKG Repair Protocol"
assert_contains "Runs dpkg configure" "${FAIL_APPLY_OUT}" "dpkg --configure -a"
assert_contains "Runs apt install -f" "${FAIL_APPLY_OUT}" "apt-get install -f"
assert_contains "Outputs efivars bind in rescue guidance" "${FAIL_APPLY_OUT}" "/sys/firmware/efi/efivars"

# --- Task 3: Syntax & Integrity Checks ---
assert_exit_code "Upgrade script syntax valid" 0 $(bash -n "${UPGRADE_SCRIPT}" && echo 0 || echo 1)
assert_exit_code "Pipeline test syntax valid" 0 $(bash -n "${WORKSPACE_ROOT}/tests/test_upgrade_pipeline.sh" && echo 0 || echo 1)

echo "=================================================="
echo "Upgrade Pipeline Test Suite Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0


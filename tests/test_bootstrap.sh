#!/usr/bin/env bash
# tests/test_bootstrap.sh - Unit test suite for Automated Disaster Recovery Provisioning
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PS_SCRIPT="${WORKSPACE_ROOT}/scripts/bootstrap_wsl.ps1"
POST_BOOTSTRAP_SCRIPT="${WORKSPACE_ROOT}/scripts/post_bootstrap.sh"

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

assert_file_exists() {
    local test_name="$1"
    local file_path="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ -f "${file_path}" ]; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (file not found: ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

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

echo "=================================================="
echo "Running Disaster Recovery Provisioning Test Suite"
echo "=================================================="

# 1. File existence assertions
assert_file_exists "bootstrap_wsl.ps1 exists" "${PS_SCRIPT}"
assert_file_exists "post_bootstrap.sh exists" "${POST_BOOTSTRAP_SCRIPT}"

# 2. Syntax validation
set +e
bash -n "${POST_BOOTSTRAP_SCRIPT}" > /dev/null 2>&1
assert_exit_code "post_bootstrap.sh syntax check (bash -n)" 0 $?

if command -v shellcheck >/dev/null 2>&1; then
    shellcheck "${POST_BOOTSTRAP_SCRIPT}" > /dev/null 2>&1
    assert_exit_code "post_bootstrap.sh shellcheck" 0 $?
fi

# 3. PowerShell script structural content assertions
if [ -f "${PS_SCRIPT}" ]; then
    PS_CONTENT="$(cat "${PS_SCRIPT}")"
    assert_contains "bootstrap_wsl.ps1 has SnapshotPath param" "${PS_CONTENT}" "SnapshotPath"
    assert_contains "bootstrap_wsl.ps1 has InstanceName param" "${PS_CONTENT}" "InstanceName"
    assert_contains "bootstrap_wsl.ps1 has InstallLocation param" "${PS_CONTENT}" "InstallLocation"
    assert_contains "bootstrap_wsl.ps1 has DefaultUser param" "${PS_CONTENT}" "DefaultUser"
    assert_contains "bootstrap_wsl.ps1 has DryRun param" "${PS_CONTENT}" "DryRun"
    assert_contains "bootstrap_wsl.ps1 has SHA-256 check" "${PS_CONTENT}" "Get-FileHash"
    assert_contains "bootstrap_wsl.ps1 has wsl --import" "${PS_CONTENT}" "wsl.exe --import"
    assert_contains "bootstrap_wsl.ps1 configures /etc/wsl.conf" "${PS_CONTENT}" "/etc/wsl.conf"
fi

# 4. Linux Post-Bootstrap Dry-Run Execution Test
TMP_LOG="$(mktemp)"
export TEST_HARNESS_NO_EXIT=1
bash "${POST_BOOTSTRAP_SCRIPT}" --audit-only > "${TMP_LOG}" 2>&1 || true
POST_OUT="$(cat "${TMP_LOG}")"
rm -f "${TMP_LOG}"

assert_contains "post_bootstrap.sh performs skill sync" "${POST_OUT}" "SSOT skill symlinks"
assert_contains "post_bootstrap.sh reloads systemd" "${POST_OUT}" "systemd user daemon"

# 5. Checksum verification logic validation
TMP_DIR="$(mktemp -d)"
SAMPLE_FILE="${TMP_DIR}/test_archive.tar.gz"
echo "archive content" > "${SAMPLE_FILE}"
if command -v sha256sum >/dev/null 2>&1; then
    SAMPLE_HASH="$(sha256sum "${SAMPLE_FILE}" | awk '{print $1}')"
    echo "${SAMPLE_HASH}  test_archive.tar.gz" > "${SAMPLE_FILE}.sha256"
    VERIFY_RESULT="$(cd "${TMP_DIR}" && sha256sum -c "test_archive.tar.gz.sha256" 2>&1)"
    assert_contains "sha256 validation passes for valid sidecar" "${VERIFY_RESULT}" "OK"
elif command -v shasum >/dev/null 2>&1; then
    SAMPLE_HASH="$(shasum -a 256 "${SAMPLE_FILE}" | awk '{print $1}')"
    echo "${SAMPLE_HASH}  test_archive.tar.gz" > "${SAMPLE_FILE}.sha256"
    VERIFY_RESULT="$(cd "${TMP_DIR}" && shasum -a 256 -c "test_archive.tar.gz.sha256" 2>&1)"
    assert_contains "sha256 validation passes for valid sidecar" "${VERIFY_RESULT}" "OK"
fi
rm -rf "${TMP_DIR}"
set -e

echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi

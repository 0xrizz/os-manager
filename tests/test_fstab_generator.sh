#!/usr/bin/env bash
# tests/test_fstab_generator.sh - Test suite for Phase 4 Post-Install Configuration & WSL Restore
# Validates fstab line formatting, safe mount flags, swapfile setup idempotency, and WSL home restoration permissions
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
POST_INSTALL_SCRIPT="${WORKSPACE_ROOT}/scripts/migration/post_install_configure.sh"
RESTORE_SCRIPT="${WORKSPACE_ROOT}/scripts/migration/restore_wsl_home.sh"

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
    if [ -f "${file_path}" ] || [ -d "${file_path}" ]; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (path not found: ${file_path})"
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

assert_not_contains() {
    local test_name="$1"
    local haystack="$2"
    local needle="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if ! echo "${haystack}" | grep -qF -- "${needle}"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected NOT to contain '${needle}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Phase 4 Post-Install & Restore Test Suite"
echo "=================================================="

# 1. Script Existence & Executable Permissions
echo "--- 1. Script Existence & Executable Permissions ---"
assert_file_exists "post_install_configure.sh exists" "${POST_INSTALL_SCRIPT}"
assert_file_exists "restore_wsl_home.sh exists" "${RESTORE_SCRIPT}"

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${POST_INSTALL_SCRIPT}" ]; then
    echo "  [PASS] post_install_configure.sh is executable (+x)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] post_install_configure.sh is not executable"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${RESTORE_SCRIPT}" ]; then
    echo "  [PASS] restore_wsl_home.sh is executable (+x)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] restore_wsl_home.sh is not executable"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Bash Syntax & ShellCheck Validation
echo "--- 2. Bash Syntax & ShellCheck Validation ---"
set +e
bash -n "${POST_INSTALL_SCRIPT}" >/dev/null 2>&1
assert_exit_code "post_install_configure.sh syntax check (bash -n)" 0 $?

bash -n "${RESTORE_SCRIPT}" >/dev/null 2>&1
assert_exit_code "restore_wsl_home.sh syntax check (bash -n)" 0 $?

if command -v shellcheck >/dev/null 2>&1; then
    shellcheck "${POST_INSTALL_SCRIPT}" >/dev/null 2>&1
    assert_exit_code "post_install_configure.sh shellcheck" 0 $?
    shellcheck "${RESTORE_SCRIPT}" >/dev/null 2>&1
    assert_exit_code "restore_wsl_home.sh shellcheck" 0 $?
fi
set -e

# 3. CLI Options & Help Dialog for post_install_configure.sh
echo "--- 3. CLI Argument Handling for post_install_configure.sh ---"
set +e
POST_HELP=$(bash "${POST_INSTALL_SCRIPT}" --help 2>&1)
assert_exit_code "post_install_configure.sh --help returns 0" 0 $?
assert_contains "Help mentions --dry-run" "${POST_HELP}" "--dry-run"
assert_contains "Help mentions --fstab-target" "${POST_HELP}" "--fstab-target"
assert_contains "Help mentions --mock-uuid" "${POST_HELP}" "--mock-uuid"

POST_INVALID=$(bash "${POST_INSTALL_SCRIPT}" --invalid-opt 2>&1)
assert_exit_code "post_install_configure.sh invalid opt returns non-zero" 1 $?
set -e

# 4. Fstab Line Formatting & Safety Flags Unit Test
echo "--- 4. Fstab Line Formatting & Safety Flags ---"
MOCK_UUID="12345678-ABCD-EF01-2345-6789ABCDEF01"
TMP_FSTAB="$(mktemp)"
echo "# Existing /etc/fstab header" > "${TMP_FSTAB}"

set +e
bash "${POST_INSTALL_SCRIPT}" --fstab-target "${TMP_FSTAB}" --mock-uuid "${MOCK_UUID}" --dry-run >/dev/null 2>&1
assert_exit_code "post_install_configure.sh --dry-run exits 0" 0 $?

# Verify dry run did NOT modify target fstab
assert_not_contains "Dry run did not write to fstab" "$(cat "${TMP_FSTAB}")" "${MOCK_UUID}"

# Now run without dry run targeting temporary fstab (mock swapfile to skip real swapon)
bash "${POST_INSTALL_SCRIPT}" --fstab-target "${TMP_FSTAB}" --mock-uuid "${MOCK_UUID}" --skip-swap-ops >/dev/null 2>&1
assert_exit_code "post_install_configure.sh targeting custom fstab exits 0" 0 $?
set -e

FSTAB_CONTENT=$(cat "${TMP_FSTAB}")
assert_contains "Fstab contains UUID entry" "${FSTAB_CONTENT}" "UUID=${MOCK_UUID}"
assert_contains "Fstab contains /mnt/data mount point" "${FSTAB_CONTENT}" "/mnt/data"
assert_contains "Fstab contains ntfs-3g filesystem" "${FSTAB_CONTENT}" "ntfs-3g"
assert_contains "Fstab contains nofail flag" "${FSTAB_CONTENT}" "nofail"
assert_contains "Fstab contains uid=1000,gid=1000" "${FSTAB_CONTENT}" "uid=1000,gid=1000"
assert_contains "Fstab contains umask=022" "${FSTAB_CONTENT}" "umask=022"
assert_contains "Fstab contains /swapfile entry" "${FSTAB_CONTENT}" "/swapfile none swap sw 0 0"

# 5. Idempotency Verification
echo "--- 5. Fstab Configuration Idempotency ---"
LINES_BEFORE=$(wc -l < "${TMP_FSTAB}")
set +e
bash "${POST_INSTALL_SCRIPT}" --fstab-target "${TMP_FSTAB}" --mock-uuid "${MOCK_UUID}" --skip-swap-ops >/dev/null 2>&1
assert_exit_code "post_install_configure.sh second run exits 0" 0 $?
set -e
LINES_AFTER=$(wc -l < "${TMP_FSTAB}")
assert_equals "Fstab lines count unchanged after re-run (idempotency)" "${LINES_BEFORE}" "${LINES_AFTER}"
rm -f "${TMP_FSTAB}"

# 6. CLI Options & Help Dialog for restore_wsl_home.sh
echo "--- 6. CLI Argument Handling for restore_wsl_home.sh ---"
set +e
RESTORE_HELP=$(bash "${RESTORE_SCRIPT}" --help 2>&1)
assert_exit_code "restore_wsl_home.sh --help returns 0" 0 $?
assert_contains "Help mentions --archive" "${RESTORE_HELP}" "--archive"
assert_contains "Help mentions --target" "${RESTORE_HELP}" "--target"
assert_contains "Help mentions --dry-run" "${RESTORE_HELP}" "--dry-run"

RESTORE_NONEXISTENT=$(bash "${RESTORE_SCRIPT}" --archive "/nonexistent/archive.tar.gz" 2>&1)
assert_exit_code "restore_wsl_home.sh with missing archive exits non-zero" 1 $?
assert_contains "Error message mentions missing archive" "${RESTORE_NONEXISTENT}" "ERROR"
set -e

# 7. WSL Home Restore & SSH Key Permission Verification
echo "--- 7. WSL Home Restore & SSH Key Permission Handling ---"
TMP_WORK_DIR="$(mktemp -d)"
TMP_ARCHIVE_DIR="${TMP_WORK_DIR}/archive_src"
TMP_RESTORE_DIR="${TMP_WORK_DIR}/target_home"
TMP_TAR="${TMP_WORK_DIR}/wsl_home_backup.tar.gz"

mkdir -p "${TMP_ARCHIVE_DIR}/.ssh" "${TMP_ARCHIVE_DIR}/dev/project" "${TMP_RESTORE_DIR}"
echo "export TEST_VAR=1" > "${TMP_ARCHIVE_DIR}/.bashrc"
echo "PRIVATE KEY" > "${TMP_ARCHIVE_DIR}/.ssh/id_rsa"
echo "ssh-rsa AAAAB3NzaC1yc2E..." > "${TMP_ARCHIVE_DIR}/.ssh/id_rsa.pub"
echo "Host *" > "${TMP_ARCHIVE_DIR}/.ssh/config"
echo "repo content" > "${TMP_ARCHIVE_DIR}/dev/project/file.txt"

# Intentionally create with permissive permissions in archive
chmod 777 "${TMP_ARCHIVE_DIR}/.ssh"
chmod 666 "${TMP_ARCHIVE_DIR}/.ssh/id_rsa"
chmod 666 "${TMP_ARCHIVE_DIR}/.ssh/config"
chmod 666 "${TMP_ARCHIVE_DIR}/.ssh/id_rsa.pub"

tar -czf "${TMP_TAR}" -C "${TMP_ARCHIVE_DIR}" .

# Test dry-run mode
set +e
DRY_OUT=$(bash "${RESTORE_SCRIPT}" --archive "${TMP_TAR}" --target "${TMP_RESTORE_DIR}" --dry-run 2>&1)
assert_exit_code "restore_wsl_home.sh --dry-run exits 0" 0 $?
assert_contains "Dry run output indicates simulation" "${DRY_OUT}" "[DRY RUN]"
set -e

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ ! -f "${TMP_RESTORE_DIR}/.bashrc" ]; then
    echo "  [PASS] Dry run did not extract files"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Dry run extracted files unexpectedly"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test live extraction mode
set +e
RESTORE_OUT=$(bash "${RESTORE_SCRIPT}" --archive "${TMP_TAR}" --target "${TMP_RESTORE_DIR}" 2>&1)
assert_exit_code "restore_wsl_home.sh extraction exits 0" 0 $?
set -e

assert_file_exists "Restored .bashrc exists" "${TMP_RESTORE_DIR}/.bashrc"
assert_file_exists "Restored .ssh dir exists" "${TMP_RESTORE_DIR}/.ssh"
assert_file_exists "Restored id_rsa exists" "${TMP_RESTORE_DIR}/.ssh/id_rsa"
assert_file_exists "Restored id_rsa.pub exists" "${TMP_RESTORE_DIR}/.ssh/id_rsa.pub"
assert_file_exists "Restored config exists" "${TMP_RESTORE_DIR}/.ssh/config"
assert_file_exists "Restored dev project exists" "${TMP_RESTORE_DIR}/dev/project/file.txt"

# Verify permissions
SSH_DIR_PERM=$(stat -c "%a" "${TMP_RESTORE_DIR}/.ssh")
ID_RSA_PERM=$(stat -c "%a" "${TMP_RESTORE_DIR}/.ssh/id_rsa")
CONFIG_PERM=$(stat -c "%a" "${TMP_RESTORE_DIR}/.ssh/config")
PUB_KEY_PERM=$(stat -c "%a" "${TMP_RESTORE_DIR}/.ssh/id_rsa.pub")

assert_equals ".ssh directory has 700 permissions" "700" "${SSH_DIR_PERM}"
assert_equals "Private key id_rsa has 600 permissions" "600" "${ID_RSA_PERM}"
assert_equals "SSH config has 600 permissions" "600" "${CONFIG_PERM}"
assert_equals "Public key id_rsa.pub has 644 permissions" "644" "${PUB_KEY_PERM}"

# Cleanup temporary work directory
rm -rf "${TMP_WORK_DIR}"

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

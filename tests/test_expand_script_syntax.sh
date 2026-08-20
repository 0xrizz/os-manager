#!/usr/bin/env bash
# tests/test_expand_script_syntax.sh - Test suite for Safe Online Root Partition Expansion
# Validates script syntax, CLI argument parsing, dry-run simulation, mock execution, and Partition 4 safety guardrail
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
EXPAND_SCRIPT="${WORKSPACE_ROOT}/scripts/migration/expand_root_partition.sh"

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

echo "=================================================="
echo "Running Safe Online Root Partition Expansion Tests"
echo "=================================================="

# 1. Script Existence & Executable Permissions
echo "--- 1. Script Existence & Executable Permissions ---"
assert_file_exists "expand_root_partition.sh exists" "${EXPAND_SCRIPT}"

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${EXPAND_SCRIPT}" ]; then
    echo "  [PASS] expand_root_partition.sh is executable (+x)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] expand_root_partition.sh is not executable"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Bash Syntax & ShellCheck Validation
echo "--- 2. Bash Syntax & ShellCheck Validation ---"
set +e
bash -n "${EXPAND_SCRIPT}" >/dev/null 2>&1
assert_exit_code "expand_root_partition.sh syntax check (bash -n)" 0 $?

if command -v shellcheck >/dev/null 2>&1; then
    shellcheck "${EXPAND_SCRIPT}" >/dev/null 2>&1
    assert_exit_code "expand_root_partition.sh shellcheck" 0 $?
fi
set -e

# 3. CLI Argument Handling & Help Dialog
echo "--- 3. CLI Argument Handling & Help Dialog ---"
set +e
HELP_OUT=$(bash "${EXPAND_SCRIPT}" --help 2>&1)
assert_exit_code "expand_root_partition.sh --help returns 0" 0 $?
assert_contains "Help text mentions --dry-run" "${HELP_OUT}" "--dry-run"
assert_contains "Help text mentions --mock-disk" "${HELP_OUT}" "--mock-disk"
assert_contains "Help text mentions --mock-part" "${HELP_OUT}" "--mock-part"
assert_contains "Help text mentions --skip-quality-gate" "${HELP_OUT}" "--skip-quality-gate"

INVALID_OUT=$(bash "${EXPAND_SCRIPT}" --unknown-option-xyz 2>&1)
assert_exit_code "expand_root_partition.sh unknown option returns non-zero" 1 $?
assert_contains "Invalid option displays error message" "${INVALID_OUT}" "ERROR: Unknown option"
set -e

# 4. Dry-Run Simulation Mode
echo "--- 4. Dry-Run Simulation Mode ---"
set +e
DRY_RUN_OUT=$(bash "${EXPAND_SCRIPT}" --dry-run --mock-disk /dev/nvme0n1 --mock-part 2 --skip-quality-gate 2>&1)
DRY_RUN_EXIT=$?
assert_exit_code "expand_root_partition.sh --dry-run returns 0" 0 "${DRY_RUN_EXIT}"
assert_contains "Dry run mentions simulated growpart" "${DRY_RUN_OUT}" "[DRY RUN]"
assert_contains "Dry run identifies target disk" "${DRY_RUN_OUT}" "/dev/nvme0n1"
assert_contains "Dry run identifies partition number" "${DRY_RUN_OUT}" "2"
set -e

# 5. Mock Execution with Supported Device Schemes
echo "--- 5. Device Resolution & Parsing Schemes ---"
set +e
# NVMe disk simulation
NVME_MOCK_OUT=$(bash "${EXPAND_SCRIPT}" --dry-run --mock-disk /dev/nvme0n1 --mock-part 3 --skip-quality-gate 2>&1)
assert_exit_code "NVMe mock partition parsing returns 0" 0 $?
assert_contains "NVMe target device correctly resolved" "${NVME_MOCK_OUT}" "Target Disk: /dev/nvme0n1 | Partition Number: 3"

# Standard SATA/SCSI (sdX) simulation
SDA_MOCK_OUT=$(bash "${EXPAND_SCRIPT}" --dry-run --mock-disk /dev/sda --mock-part 2 --skip-quality-gate 2>&1)
assert_exit_code "SDA mock partition parsing returns 0" 0 $?
assert_contains "SDA target device correctly resolved" "${SDA_MOCK_OUT}" "Target Disk: /dev/sda | Partition Number: 2"

# VirtIO (vdX) simulation
VDA_MOCK_OUT=$(bash "${EXPAND_SCRIPT}" --dry-run --mock-disk /dev/vda --mock-part 1 --skip-quality-gate 2>&1)
assert_exit_code "VDA mock partition parsing returns 0" 0 $?
assert_contains "VDA target device correctly resolved" "${VDA_MOCK_OUT}" "Target Disk: /dev/vda | Partition Number: 1"
set -e

# 6. Zero-Data-Loss Safety Guardrail: Refuse Partition 4 Target
echo "--- 6. Zero-Data-Loss Safety Guardrail (Partition 4 Protection) ---"
set +e
# Attempt to target Partition 4
P4_GUARD_OUT=$(bash "${EXPAND_SCRIPT}" --mock-disk /dev/nvme0n1 --mock-part 4 --skip-quality-gate 2>&1)
P4_GUARD_EXIT=$?
assert_exit_code "Targeting Partition 4 directly returns exit code 1" 1 "${P4_GUARD_EXIT}"
assert_contains "Partition 4 protection error message is displayed" "${P4_GUARD_OUT}" "Refusing to expand/modify Partition 4"

# Attempt to target Partition 4 in dry-run mode (must also fail-safe)
P4_DRY_GUARD_OUT=$(bash "${EXPAND_SCRIPT}" --dry-run --mock-disk /dev/nvme0n1 --mock-part 4 --skip-quality-gate 2>&1)
P4_DRY_GUARD_EXIT=$?
assert_exit_code "Targeting Partition 4 in dry-run mode returns exit code 1" 1 "${P4_DRY_GUARD_EXIT}"
assert_contains "Dry run also enforces Partition 4 guardrail" "${P4_DRY_GUARD_OUT}" "Refusing to expand/modify Partition 4"
set -e

# 7. Quality Gate Integration & Pre-requisite Check
echo "--- 7. Quality Gate Integration Pre-requisite Check ---"
set +e
# Run with a failing quality gate mock (mock-fail-datastore)
TMP_FAIL_QG="$(mktemp)"
echo '#!/usr/bin/env bash' > "${TMP_FAIL_QG}"
echo 'echo "Simulated Quality Gate Failure" >&2' >> "${TMP_FAIL_QG}"
echo 'exit 1' >> "${TMP_FAIL_QG}"
chmod +x "${TMP_FAIL_QG}"

QG_FAIL_OUT=$(bash "${EXPAND_SCRIPT}" --quality-gate-script "${TMP_FAIL_QG}" --mock-disk /dev/nvme0n1 --mock-part 2 2>&1)
QG_FAIL_EXIT=$?
assert_exit_code "Failing Quality Gate halts partition expansion with exit code 1" 1 "${QG_FAIL_EXIT}"
assert_contains "Quality Gate failure abort message displayed" "${QG_FAIL_OUT}" "ABORT: Quality gate checks failed"
rm -f "${TMP_FAIL_QG}"

# Now verify that passing quality gate allows progress
TMP_PASS_QG="$(mktemp)"
echo '#!/usr/bin/env bash' > "${TMP_PASS_QG}"
echo 'echo "Simulated Quality Gate Passed"' >> "${TMP_PASS_QG}"
echo 'exit 0' >> "${TMP_PASS_QG}"
chmod +x "${TMP_PASS_QG}"

QG_PASS_OUT=$(bash "${EXPAND_SCRIPT}" --quality-gate-script "${TMP_PASS_QG}" --dry-run --mock-disk /dev/nvme0n1 --mock-part 2 2>&1)
QG_PASS_EXIT=$?
assert_exit_code "Passing Quality Gate proceeds with expansion in dry-run" 0 "${QG_PASS_EXIT}"
assert_contains "Quality Gate passed message logged" "${QG_PASS_OUT}" "Quality gate verification passed"
rm -f "${TMP_PASS_QG}"
set -e

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

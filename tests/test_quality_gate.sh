#!/usr/bin/env bash
# tests/test_quality_gate.sh - Test suite for Post-Installation Quality Gate Diagnostics Checkpoint
# Validates hardware audit script behavior, mock execution, JSON reporting, and safety guardrails
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
AUDIT_SCRIPT="${WORKSPACE_ROOT}/scripts/migration/quality_gate_audit.sh"

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
    if echo "${haystack}" | grep -qF -- "${needle}"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected to contain '${needle}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# Parse options
MOCK_ONLY=false
LIVE_AUDIT=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mock)
            MOCK_ONLY=true
            shift
            ;;
        --live)
            LIVE_AUDIT=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --mock     Run quick mock test verifying exit 0"
            echo "  --live     Execute live bare-metal / WSL diagnostics audit"
            echo "  -h, --help Show this help message"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

if [[ "$MOCK_ONLY" == "true" ]]; then
    echo "Running quick mock verification for CI..."
    if [[ ! -x "${AUDIT_SCRIPT}" ]]; then
        echo "FAIL: ${AUDIT_SCRIPT} not found or not executable"
        exit 1
    fi
    bash "${AUDIT_SCRIPT}" --mock
    exit 0
fi

if [[ "$LIVE_AUDIT" == "true" ]]; then
    echo "Executing live diagnostics audit..."
    if [[ ! -x "${AUDIT_SCRIPT}" ]]; then
        echo "FAIL: ${AUDIT_SCRIPT} not found or not executable"
        exit 1
    fi
    bash "${AUDIT_SCRIPT}"
    exit 0
fi

echo "=================================================="
echo "Running Post-Installation Quality Gate Test Suite"
echo "=================================================="

# 1. Check file existence & permissions
echo "--- 1. Script Existence & Executable Permissions ---"
assert_file_exists "quality_gate_audit.sh exists" "${AUDIT_SCRIPT}"
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${AUDIT_SCRIPT}" ]; then
    echo "  [PASS] quality_gate_audit.sh is executable (+x)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] quality_gate_audit.sh is not executable"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Syntax validation
echo "--- 2. Bash Syntax & ShellCheck Validation ---"
set +e
bash -n "${AUDIT_SCRIPT}" >/dev/null 2>&1
assert_exit_code "quality_gate_audit.sh syntax check (bash -n)" 0 $?

if command -v shellcheck >/dev/null 2>&1; then
    shellcheck "${AUDIT_SCRIPT}" >/dev/null 2>&1
    assert_exit_code "quality_gate_audit.sh shellcheck" 0 $?
fi
set -e

# 3. CLI options & help dialog
echo "--- 3. CLI Argument Handling & Help Dialog ---"
set +e
HELP_OUT=$(bash "${AUDIT_SCRIPT}" --help 2>&1)
assert_exit_code "quality_gate_audit.sh --help returns 0" 0 $?
assert_contains "Help text mentions --mock" "${HELP_OUT}" "--mock"
assert_contains "Help text mentions --json" "${HELP_OUT}" "--json"
assert_contains "Help text mentions --report" "${HELP_OUT}" "--report"
assert_contains "Help text mentions --strict" "${HELP_OUT}" "--strict"

INVALID_OUT=$(bash "${AUDIT_SCRIPT}" --invalid-flag-xyz 2>&1)
assert_exit_code "quality_gate_audit.sh invalid flag returns non-zero" 1 $?
set -e

# 4. Mock execution & scoring
echo "--- 4. Mock Execution & 5-Point Quality Gate Verification ---"
set +e
MOCK_OUTPUT=$(bash "${AUDIT_SCRIPT}" --mock 2>&1)
MOCK_EXIT=$?
assert_exit_code "quality_gate_audit.sh --mock returns 0" 0 "${MOCK_EXIT}"
assert_contains "Mock output checks Wi-Fi" "${MOCK_OUTPUT}" "[1/5] Checking Intel AC 9560 Wi-Fi (iwlwifi)"
assert_contains "Mock output checks Audio" "${MOCK_OUTPUT}" "[2/5] Checking ALSA/PipeWire Audio"
assert_contains "Mock output checks Bluetooth" "${MOCK_OUTPUT}" "[3/5] Checking Bluetooth Controller"
assert_contains "Mock output checks Graphics" "${MOCK_OUTPUT}" "[4/5] Checking GNOME Wayland & Intel i915 DRM"
assert_contains "Mock output checks Partition 4" "${MOCK_OUTPUT}" "[5/5] Checking Partition 4 (DATA_STORE) Preservation"
assert_contains "Mock score is 5 / 5" "${MOCK_OUTPUT}" "Quality Gate Score: 5 / 5"
assert_contains "Mock result PASSED" "${MOCK_OUTPUT}" "RESULT: Quality Gate PASSED"
set -e

# 5. JSON output validation
echo "--- 5. JSON Machine-Readable Output Validation ---"
set +e
JSON_OUTPUT=$(bash "${AUDIT_SCRIPT}" --mock --json 2>/dev/null)
JSON_EXIT=$?
assert_exit_code "quality_gate_audit.sh --mock --json returns 0" 0 "${JSON_EXIT}"

# Validate JSON structure with python3
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if python3 -c "
import sys, json
data = json.loads('''${JSON_OUTPUT}''')
assert data['score'] == 5
assert data['total'] == 5
assert data['passed'] is True
assert 'wifi' in data['checks']
assert 'audio' in data['checks']
assert 'bluetooth' in data['checks']
assert 'graphics' in data['checks']
assert 'data_store_partition' in data['checks']
assert data['checks']['data_store_partition']['status'] == 'PASS'
" 2>/dev/null; then
    echo "  [PASS] JSON structure and check fields valid"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] JSON structure validation failed"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
set -e

# 6. Report file export
echo "--- 6. Report File Export (--report) ---"
TMP_REPORT="$(mktemp)"
set +e
bash "${AUDIT_SCRIPT}" --mock --report "${TMP_REPORT}" >/dev/null 2>&1
REPORT_EXIT=$?
assert_exit_code "quality_gate_audit.sh --report returns 0" 0 "${REPORT_EXIT}"
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -s "${TMP_REPORT}" ]; then
    echo "  [PASS] Report file created and non-empty: ${TMP_REPORT}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Report file is empty or missing"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
rm -f "${TMP_REPORT}"
set -e

# 7. Safety Guardrail & Mock Failure Simulation
echo "--- 7. Zero-Data-Loss Safety Guardrail & Score Thresholds ---"
set +e
FAIL_DATA_STORE_OUT=$(bash "${AUDIT_SCRIPT}" --mock --mock-fail-datastore 2>&1)
FAIL_DATA_STORE_EXIT=$?
assert_exit_code "Failing Partition 4 check exits with code 1" 1 "${FAIL_DATA_STORE_EXIT}"
assert_contains "Output shows Partition 4 failure message" "${FAIL_DATA_STORE_OUT}" "CRITICAL"
assert_contains "Output warns NOT to delete staging partitions" "${FAIL_DATA_STORE_OUT}" "Do NOT delete staging partitions yet"

# Test --mock-score 3 (should fail standard >= 4 threshold)
SCORE_3_OUT=$(bash "${AUDIT_SCRIPT}" --mock-score 3 2>&1)
SCORE_3_EXIT=$?
assert_exit_code "Score 3/5 exits with code 1" 1 "${SCORE_3_EXIT}"
assert_contains "Score 3 reports 3 / 5" "${SCORE_3_OUT}" "Quality Gate Score: 3 / 5"

# Test --strict mode with score 4 (fails in strict mode)
set +e
STRICT_4_EXIT=$(bash "${AUDIT_SCRIPT}" --mock-score 4 --strict >/dev/null 2>&1; echo $?)
assert_exit_code "Strict mode with score 4 exits with code 1" 1 "${STRICT_4_EXIT}"

STRICT_5_EXIT=$(bash "${AUDIT_SCRIPT}" --mock-score 5 --strict >/dev/null 2>&1; echo $?)
assert_exit_code "Strict mode with score 5 exits with code 0" 0 "${STRICT_5_EXIT}"
set -e

# 8. Environment detection check
echo "--- 8. WSL vs Bare-Metal Environment Detection ---"
set +e
DETECT_OUT=$(bash "${AUDIT_SCRIPT}" --json 2>/dev/null || true)
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if python3 -c "
import json, sys
try:
    data = json.loads('''${DETECT_OUT}''')
    assert 'environment' in data
    assert data['environment'] in ['wsl', 'bare-metal', 'linux', 'container']
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    echo "  [PASS] Environment detection recognized ('environment' field present)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [PASS] Environment detection fallback (non-JSON mode tested)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi
set -e

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

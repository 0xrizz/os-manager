#!/usr/bin/env bash
# tests/test_reclaim_partitions.sh - Unit tests for transition partition reclamation
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RECLAIM_SCRIPT="${WORKSPACE_ROOT}/scripts/migration/reclaim_transition_partitions.sh"

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
echo " Running Partition Reclamation Unit Tests"
echo "=================================================="

# 1. Test script syntax
bash -n "${RECLAIM_SCRIPT}"
assert_exit_code "reclaim_transition_partitions.sh syntax check (bash -n)" 0 $?

# 2. Test help flag
"${RECLAIM_SCRIPT}" --help >/dev/null 2>&1
assert_exit_code "reclaim_transition_partitions.sh --help" 0 $?

# 3. Test dry-run execution
"${RECLAIM_SCRIPT}" --dry-run >/dev/null 2>&1
assert_exit_code "reclaim_transition_partitions.sh --dry-run" 0 $?

# 4. Test protection guardrail on Partition 4 (DATA_STORE)
set +e
"${RECLAIM_SCRIPT}" --mock-target-part 4 >/dev/null 2>&1
assert_exit_code "Guardrail blocks target Partition 4 (DATA_STORE)" 1 $?

# 5. Test protection guardrail on Partition 1 (EFI ESP)
"${RECLAIM_SCRIPT}" --mock-target-part 1 >/dev/null 2>&1
assert_exit_code "Guardrail blocks target Partition 1 (EFI)" 1 $?

# 6. Test protection guardrail on Partition 6 (Active Root)
"${RECLAIM_SCRIPT}" --mock-target-part 6 >/dev/null 2>&1
assert_exit_code "Guardrail blocks target Partition 6 (Active Root)" 1 $?
set -e

echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} tests passed."

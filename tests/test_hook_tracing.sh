#!/usr/bin/env bash
# tests/test_hook_tracing.sh - Unit tests for hook performance tracing engine
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HELPER_LIB="${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
TEST_LOG="/tmp/os_manager_test_audit.jsonl"

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

assert_json_field_exists() {
    local test_name="$1"
    local json_str="$2"
    local field="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    local val
    val="$(echo "${json_str}" | jq -r ".${field} // empty" 2>/dev/null)"
    if [ -n "${val}" ] && [ "${val}" != "null" ]; then
        echo "  [PASS] ${test_name} (field '${field}' = ${val})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (missing field '${field}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Hook Performance Tracing Unit Tests"
echo "=================================================="

rm -f "${TEST_LOG}"

# 1. Test helper existence and syntax
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -f "${HELPER_LIB}" ]; then
    echo "  [PASS] trace_helper.sh exists"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] trace_helper.sh missing at ${HELPER_LIB}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Test trace execution with synthetic delay and exit code 0
TEST_SCRIPT_PASS="/tmp/test_trace_pass.sh"
cat <<TESTEOF > "${TEST_SCRIPT_PASS}"
#!/usr/bin/env bash
set -euo pipefail
WORKSPACE_ROOT="${WORKSPACE_ROOT}"
export WORKSPACE_ROOT
# Override audit log destination for testing
export HARNESS_AUDIT_LOG="${TEST_LOG}"
source "${HELPER_LIB}"
trace_start "TestHookPass" "Bash"
sleep 0.05
exit 0
TESTEOF
chmod +x "${TEST_SCRIPT_PASS}"

set +e
"${TEST_SCRIPT_PASS}" >/dev/null 2>&1
PASS_CODE=$?
set -e
rm -f "${TEST_SCRIPT_PASS}"

assert_equals "Exit code 0 propagation" "0" "${PASS_CODE}"

# 3. Test trace execution with exit code 2 (Security block)
TEST_SCRIPT_BLOCK="/tmp/test_trace_block.sh"
cat <<TESTEOF > "${TEST_SCRIPT_BLOCK}"
#!/usr/bin/env bash
set -euo pipefail
WORKSPACE_ROOT="${WORKSPACE_ROOT}"
export WORKSPACE_ROOT
export HARNESS_AUDIT_LOG="${TEST_LOG}"
source "${HELPER_LIB}"
trace_start "TestHookBlock" "Edit"
sleep 0.01
exit 2
TESTEOF
chmod +x "${TEST_SCRIPT_BLOCK}"

set +e
"${TEST_SCRIPT_BLOCK}" >/dev/null 2>&1
BLOCK_CODE=$?
set -e
rm -f "${TEST_SCRIPT_BLOCK}"

assert_equals "Exit code 2 propagation" "2" "${BLOCK_CODE}"

# 4. Verify JSON schema formatting
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -s "${TEST_LOG}" ]; then
    echo "  [PASS] Telemetry log file was created and is non-empty"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Telemetry log file missing or empty: ${TEST_LOG}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

RECORD_1="$(head -n 1 "${TEST_LOG}" 2>/dev/null || echo "{}")"
RECORD_2="$(tail -n 1 "${TEST_LOG}" 2>/dev/null || echo "{}")"

assert_json_field_exists "Record 1 contains timestamp_iso" "${RECORD_1}" "timestamp_iso"
assert_json_field_exists "Record 1 contains timestamp_epoch" "${RECORD_1}" "timestamp_epoch"
assert_json_field_exists "Record 1 contains hook_name" "${RECORD_1}" "hook_name"
assert_json_field_exists "Record 1 contains target_tool" "${RECORD_1}" "target_tool"
assert_json_field_exists "Record 1 contains duration_ms" "${RECORD_1}" "duration_ms"
assert_json_field_exists "Record 1 contains duration_us" "${RECORD_1}" "duration_us"

REC1_HOOK="$(echo "${RECORD_1}" | jq -r '.hook_name')"
assert_equals "Record 1 hook_name match" "TestHookPass" "${REC1_HOOK}"

REC1_TOOL="$(echo "${RECORD_1}" | jq -r '.target_tool')"
assert_equals "Record 1 target_tool match" "Bash" "${REC1_TOOL}"

REC1_EXIT="$(echo "${RECORD_1}" | jq -r '.exit_code')"
assert_equals "Record 1 exit_code match" "0" "${REC1_EXIT}"

REC2_EXIT="$(echo "${RECORD_2}" | jq -r '.exit_code')"
assert_equals "Record 2 exit_code match" "2" "${REC2_EXIT}"

REC2_TOOL="$(echo "${RECORD_2}" | jq -r '.target_tool')"
assert_equals "Record 2 target_tool match" "Edit" "${REC2_TOOL}"

# 5. Timing validation: Sleep was 50ms, duration should be within reasonable boundary (>= 10ms and <= 500ms for busy CI runners)
DURATION_MS="$(echo "${RECORD_1}" | jq -r '.duration_ms // empty')"
DURATION_INT="${DURATION_MS%.*}"
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -n "${DURATION_INT}" ] && [[ "${DURATION_INT}" =~ ^[0-9]+$ ]] && [ "${DURATION_INT}" -ge 10 ] && [ "${DURATION_INT}" -le 500 ]; then
    echo "  [PASS] Measured duration within expected range (${DURATION_MS}ms for ~50ms sleep)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Measured duration unexpected: ${DURATION_MS:-empty}ms"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

rm -f "${TEST_LOG}"

# 6. Test CLI Benchmark Tool
BENCHMARK_BIN="${WORKSPACE_ROOT}/scripts/hook_benchmark.sh"
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${BENCHMARK_BIN}" ]; then
    echo "  [PASS] hook_benchmark.sh is executable"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] hook_benchmark.sh missing or non-executable"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Create synthetic audit log with known latencies for benchmark validation
BENCH_AUDIT_LOG="/tmp/os_manager_bench_audit.jsonl"
cat <<BENCHEOF > "${BENCH_AUDIT_LOG}"
{"timestamp_iso":"2026-08-19T10:00:00Z","timestamp_epoch":1787149000,"hook_name":"PreToolUse","target_tool":"Bash","duration_ms":10.00,"duration_us":10000,"exit_code":0}
{"timestamp_iso":"2026-08-19T10:00:01Z","timestamp_epoch":1787149001,"hook_name":"PreToolUse","target_tool":"Bash","duration_ms":20.00,"duration_us":20000,"exit_code":0}
{"timestamp_iso":"2026-08-19T10:00:02Z","timestamp_epoch":1787149002,"hook_name":"PreToolUse","target_tool":"Bash","duration_ms":30.00,"duration_us":30000,"exit_code":0}
{"timestamp_iso":"2026-08-19T10:00:03Z","timestamp_epoch":1787149003,"hook_name":"PostToolUse","target_tool":"Edit","duration_ms":40.00,"duration_us":40000,"exit_code":0}
BENCHEOF

# Test JSON benchmark output
JSON_OUT="$("${BENCHMARK_BIN}" --log "${BENCH_AUDIT_LOG}" --json 2>/dev/null || echo "{}")"
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if echo "${JSON_OUT}" | jq -e '.PreToolUse.count == 3' >/dev/null 2>&1; then
    echo "  [PASS] hook_benchmark.sh --json computes accurate sample counts"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] hook_benchmark.sh --json failed on count assertion"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test --assert-p99 passes on fast synthetic log
set +e
"${BENCHMARK_BIN}" --log "${BENCH_AUDIT_LOG}" --assert-p99 >/dev/null 2>&1
BENCH_PASS_CODE=$?
set -e
assert_equals "hook_benchmark.sh --assert-p99 exit code on fast logs" "0" "${BENCH_PASS_CODE}"

# Test --assert-p99 fails on slow synthetic log
cat <<BENCHEOF >> "${BENCH_AUDIT_LOG}"
{"timestamp_iso":"2026-08-19T10:00:04Z","timestamp_epoch":1787149004,"hook_name":"PreToolUse","target_tool":"Bash","duration_ms":120.00,"duration_us":120000,"exit_code":0}
BENCHEOF

set +e
"${BENCHMARK_BIN}" --log "${BENCH_AUDIT_LOG}" --assert-p99 >/dev/null 2>&1
BENCH_FAIL_CODE=$?
set -e
assert_equals "hook_benchmark.sh --assert-p99 exit code on slow logs" "1" "${BENCH_FAIL_CODE}"

rm -f "${BENCH_AUDIT_LOG}"

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi

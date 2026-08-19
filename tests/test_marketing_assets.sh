#!/usr/bin/env bash
# tests/test_marketing_assets.sh - Unit tests for marketing assets & launch playbooks
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_file_exists() {
    local test_name="$1"
    local file_path="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ -f "${file_path}" ]; then
        echo "  [PASS] ${test_name} (file exists: ${file_path})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (file missing: ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

assert_file_contains() {
    local test_name="$1"
    local expected_pattern="$2"
    local file_path="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if grep -qE "${expected_pattern}" "${file_path}"; then
        echo "  [PASS] ${test_name} (matched pattern '${expected_pattern}')"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (missing pattern '${expected_pattern}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Marketing Assets & GTM Test Suite"
echo "=================================================="

echo "--- 1. Testing Charm VHS Tape Definition ---"
VHS_FILE="${WORKSPACE_ROOT}/vhs/demo.tape"
assert_file_exists "VHS Tape Existence" "${VHS_FILE}"
assert_file_contains "VHS Output Configuration" "Output\s+assets/demo.gif" "${VHS_FILE}"
assert_file_contains "VHS Command Simulation" "rm -rf" "${VHS_FILE}"
assert_file_contains "VHS Diag Command Simulation" "/diag" "${VHS_FILE}"

echo "--- 2. Testing README Hero & Quickstart Structure ---"
README_FILE="${WORKSPACE_ROOT}/README.md"
assert_file_exists "README Existence" "${README_FILE}"
assert_file_contains "README Hero Tagline" "Run Claude Code autonomously without fear" "${README_FILE}"
assert_file_contains "README 1-Line Curl Quickstart" "curl -fsSL.*install\.sh.*bash" "${README_FILE}"
assert_file_contains "README CI Badges" "img\.shields\.io" "${README_FILE}"

echo "--- 3. Testing Launch Playbooks ---"
HN_PLAYBOOK="${WORKSPACE_ROOT}/playbooks/launch_show_hn.md"
assert_file_exists "Show HN Playbook Existence" "${HN_PLAYBOOK}"
assert_file_contains "Show HN Title" "Show HN: os-manager" "${HN_PLAYBOOK}"

TWITTER_PLAYBOOK="${WORKSPACE_ROOT}/playbooks/launch_twitter_thread.md"
assert_file_exists "Twitter Thread Playbook Existence" "${TWITTER_PLAYBOOK}"
assert_file_contains "Twitter Thread 5-Post Structure" "Post 5" "${TWITTER_PLAYBOOK}"

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

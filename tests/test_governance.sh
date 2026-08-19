#!/usr/bin/env bash
# tests/test_governance.sh - Unit tests for open-source governance and CI workflows
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
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (missing at ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

assert_contains() {
    local test_name="$1"
    local file_path="$2"
    local pattern="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ -f "${file_path}" ] && grep -qi "${pattern}" "${file_path}"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (pattern '${pattern}' not found in ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Open-Source Governance Unit Tests"
echo "=================================================="

# 1. Verify Core Community Governance Documents
assert_file_exists "LICENSE exists" "${WORKSPACE_ROOT}/LICENSE"
assert_contains "LICENSE is MIT" "${WORKSPACE_ROOT}/LICENSE" "MIT License"

assert_file_exists "README.md exists" "${WORKSPACE_ROOT}/README.md"
assert_contains "README has Architecture" "${WORKSPACE_ROOT}/README.md" "Architecture"
assert_contains "README has Quickstart" "${WORKSPACE_ROOT}/README.md" "Quickstart"

assert_file_exists "CONTRIBUTING.md exists" "${WORKSPACE_ROOT}/CONTRIBUTING.md"
assert_contains "CONTRIBUTING has Testing" "${WORKSPACE_ROOT}/CONTRIBUTING.md" "Testing"

assert_file_exists "SECURITY.md exists" "${WORKSPACE_ROOT}/SECURITY.md"
assert_contains "SECURITY has Disclosure" "${WORKSPACE_ROOT}/SECURITY.md" "Reporting a Vulnerability"

assert_file_exists "CODE_OF_CONDUCT.md exists" "${WORKSPACE_ROOT}/CODE_OF_CONDUCT.md"
assert_contains "CODE_OF_CONDUCT is Contributor Covenant" "${WORKSPACE_ROOT}/CODE_OF_CONDUCT.md" "Contributor Covenant"

# 2. Verify GitHub Community Templates
assert_file_exists "Bug report template exists" "${WORKSPACE_ROOT}/.github/ISSUE_TEMPLATE/bug_report.yml"
assert_file_exists "Feature request template exists" "${WORKSPACE_ROOT}/.github/ISSUE_TEMPLATE/feature_request.yml"
assert_file_exists "Pull request template exists" "${WORKSPACE_ROOT}/.github/PULL_REQUEST_TEMPLATE.md"

# 3. Verify CI Workflow YAML Configuration
assert_file_exists "CI workflow exists" "${WORKSPACE_ROOT}/.github/workflows/ci.yml"
assert_contains "CI workflow tests Ubuntu" "${WORKSPACE_ROOT}/.github/workflows/ci.yml" "ubuntu-24.04"
assert_contains "CI workflow tests macOS" "${WORKSPACE_ROOT}/.github/workflows/ci.yml" "macos-14"

# 4. Validate YAML Syntax using Python
TOTAL_TESTS=$((TOTAL_TESTS + 1))
YAML_CHECK_RC=0
python3 -c '
import yaml, glob, sys
for yml in glob.glob("'"${WORKSPACE_ROOT}"'/.github/**/*.yml", recursive=True):
    with open(yml, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
' > /dev/null 2>&1 || YAML_CHECK_RC=$?

if [ "${YAML_CHECK_RC}" -eq 0 ]; then
    echo "  [PASS] All GitHub YAML files have valid syntax"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] YAML syntax error detected in .github/"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi

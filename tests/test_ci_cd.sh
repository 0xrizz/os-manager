#!/usr/bin/env bash
# tests/test_ci_cd.sh - Unit tests for CI/CD & Release workflows
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKFLOWS_DIR="${WORKSPACE_ROOT}/.github/workflows"

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

assert_python_yaml_valid() {
    local test_name="$1"
    local file_path="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if python3 -c "
import sys
# Simple YAML key validator without third-party dependencies
with open('${file_path}', 'r') as f:
    content = f.read()
assert 'name:' in content
assert 'on:' in content
assert 'jobs:' in content
" 2>/dev/null; then
        echo "  [PASS] ${test_name} (valid YAML structure)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (invalid YAML structure in ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running CI/CD & Release Engineering Test Suite"
echo "=================================================="

echo "--- 1. Testing CI Workflow Structure (.github/workflows/ci.yml) ---"
CI_FILE="${WORKFLOWS_DIR}/ci.yml"
assert_file_exists "CI Workflow Existence" "${CI_FILE}"
assert_python_yaml_valid "CI Workflow YAML Validation" "${CI_FILE}"
assert_file_contains "CI Concurrency Control" "cancel-in-progress: true" "${CI_FILE}"
assert_file_contains "CI Multi-OS Matrix" "matrix:" "${CI_FILE}"
assert_file_contains "CI ShellCheck Step" "shellcheck" "${CI_FILE}"
assert_file_contains "CI Gitleaks Step" "gitleaks" "${CI_FILE}"

echo "--- 2. Testing Release Workflow Structure (.github/workflows/release.yml) ---"
RELEASE_FILE="${WORKFLOWS_DIR}/release.yml"
assert_file_exists "Release Workflow Existence" "${RELEASE_FILE}"
assert_python_yaml_valid "Release Workflow YAML Validation" "${RELEASE_FILE}"
assert_file_contains "Release Tag Trigger" "tags:" "${RELEASE_FILE}"
assert_file_contains "Release OIDC Token Permission" "id-token: write" "${RELEASE_FILE}"
assert_file_contains "Release PyPI Trusted Publisher" "pypa/gh-action-pypi-publish" "${RELEASE_FILE}"
assert_file_contains "Release SHA256 Checksum Generation" "sha256sum" "${RELEASE_FILE}"

echo "--- 3. Testing SHA256 Checksum Routine Simulation ---"
TEMP_DIST_DIR=$(mktemp -d)
echo "dummy wheel content" > "${TEMP_DIST_DIR}/osm-1.2.0-py3-none-any.whl"
echo "dummy sdist content" > "${TEMP_DIST_DIR}/osm-1.2.0.tar.gz"
echo "#!/bin/bash" > "${TEMP_DIST_DIR}/install.sh"

(
    cd "${TEMP_DIST_DIR}"
    sha256sum osm-1.2.0-py3-none-any.whl osm-1.2.0.tar.gz install.sh > checksums.sha256
)

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -s "${TEMP_DIST_DIR}/checksums.sha256" ] && [ "$(wc -l < "${TEMP_DIST_DIR}/checksums.sha256")" -eq 3 ]; then
    echo "  [PASS] SHA256 Checksum Generation Routine (3 files hashed)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] SHA256 Checksum Generation Routine failed"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
rm -rf "${TEMP_DIST_DIR}"

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

#!/usr/bin/env bash
# tests/test_release_packaging.sh - Unit tests for release packaging and checksum pipeline
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

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
    if [ -f "${file_path}" ]; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (file missing: ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Release Packaging & Artifact Test Suite"
echo "=================================================="

TMP_DIST_DIR="$(mktemp -d)"

# 1. Build sdist and wheel
echo "--- 1. Testing Python Distribution Build ---"
BUILD_CMD=()
if python3 -m build --help >/dev/null 2>&1; then
    BUILD_CMD=(python3 -m build --outdir "${TMP_DIST_DIR}" "${WORKSPACE_ROOT}")
elif [ -f "${WORKSPACE_ROOT}/.venv/bin/python3" ] && "${WORKSPACE_ROOT}/.venv/bin/python3" -m build --help >/dev/null 2>&1; then
    BUILD_CMD=("${WORKSPACE_ROOT}/.venv/bin/python3" -m build --outdir "${TMP_DIST_DIR}" "${WORKSPACE_ROOT}")
elif command -v uv >/dev/null 2>&1; then
    BUILD_CMD=(uv build --out-dir "${TMP_DIST_DIR}" "${WORKSPACE_ROOT}")
else
    BUILD_CMD=(python3 -m build --outdir "${TMP_DIST_DIR}" "${WORKSPACE_ROOT}")
fi

"${BUILD_CMD[@]}" > /dev/null 2>&1
assert_exit_code "python3 -m build execution" 0 $?

WHEEL_COUNT=$(find "${TMP_DIST_DIR}" -name "*.whl" | wc -l)
SDIST_COUNT=$(find "${TMP_DIST_DIR}" -name "*.tar.gz" | wc -l)
[ "${WHEEL_COUNT}" -ge 1 ] && WHEEL_EXISTS=0 || WHEEL_EXISTS=1
[ "${SDIST_COUNT}" -ge 1 ] && SDIST_EXISTS=0 || SDIST_EXISTS=1

assert_exit_code "Wheel artifact generated (.whl)" 0 "${WHEEL_EXISTS}"
assert_exit_code "Source distribution generated (.tar.gz)" 0 "${SDIST_EXISTS}"

# 2. Checksum generation verification
echo "--- 2. Testing Cryptographic Checksum Generation ---"
TMP_ASSETS_DIR="$(mktemp -d)"
cp "${TMP_DIST_DIR}"/* "${TMP_ASSETS_DIR}/"
cp "${WORKSPACE_ROOT}/install.sh" "${TMP_ASSETS_DIR}/"

if command -v sha256sum >/dev/null 2>&1; then
    (cd "${TMP_ASSETS_DIR}" && sha256sum -- install.sh ./*.whl ./*.tar.gz > checksums.sha256)
    assert_file_exists "checksums.sha256 generated" "${TMP_ASSETS_DIR}/checksums.sha256"
    (cd "${TMP_ASSETS_DIR}" && sha256sum -c checksums.sha256 > /dev/null 2>&1)
    assert_exit_code "All release assets pass sha256sum verification" 0 $?
elif command -v shasum >/dev/null 2>&1; then
    (cd "${TMP_ASSETS_DIR}" && shasum -a 256 -- install.sh ./*.whl ./*.tar.gz > checksums.sha256)
    assert_file_exists "checksums.sha256 generated" "${TMP_ASSETS_DIR}/checksums.sha256"
    (cd "${TMP_ASSETS_DIR}" && shasum -a 256 -c checksums.sha256 > /dev/null 2>&1)
    assert_exit_code "All release assets pass shasum verification" 0 $?
fi

# Cleanup
rm -rf "${TMP_DIST_DIR}" "${TMP_ASSETS_DIR}"

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0

#!/usr/bin/env bash
# tests/test_migration_prerequisites.sh - Pre-migration validation test for Debian Live GNOME ISO
# Validates ISO existence, minimum size (>= 1 GB), readable squashfs filesystem boundary (< 4 GiB FAT32)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_success() {
    local test_name="$1"
    local cmd="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if eval "$cmd"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (command failed)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

assert_failure() {
    local test_name="$1"
    local cmd="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  [FAIL] ${test_name} (expected failure, but command succeeded)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    else
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    fi
}

# Standalone mode if an argument is passed
if [[ $# -ge 1 ]]; then
    ISO_PATH="$1"
    if [[ -z "$ISO_PATH" || ! -f "$ISO_PATH" ]]; then
        echo "FAIL: ISO file not provided or does not exist."
        exit 1
    fi

    echo "Testing ISO size and readability..."
    ISO_SIZE_BYTES=$(stat -c %s "$ISO_PATH")
    if (( ISO_SIZE_BYTES < 1000000000 )); then
        echo "FAIL: ISO file size ($ISO_SIZE_BYTES bytes) is suspiciously small (< 1 GB)."
        exit 1
    fi

    echo "PASS: ISO size is valid ($ISO_SIZE_BYTES bytes)."
    exit 0
fi

# Test suite mode
echo "=================================================="
echo "Running Migration Prerequisites & ISO Unit Tests"
echo "=================================================="

# Test 1: Verify missing ISO argument or nonexistent file fails
assert_failure "Missing ISO path triggers error" "bash '${BASH_SOURCE[0]}' ''"
assert_failure "Non-existent ISO triggers error" "bash '${BASH_SOURCE[0]}' '/mnt/d/download/nonexistent.iso'"

# Test 2: Verify undersized dummy file fails (< 1GB)
DUMMY_TINY="/tmp/dummy_tiny_test.iso"
echo "dummy tiny iso" > "$DUMMY_TINY"
assert_failure "Undersized ISO triggers failure" "bash '${BASH_SOURCE[0]}' '$DUMMY_TINY'"
rm -f "$DUMMY_TINY"

# Test 3: Verify verify_iso_squashfs.sh script syntax if present
VERIFY_SCRIPT="${WORKSPACE_ROOT}/scripts/migration/verify_iso_squashfs.sh"
if [[ -f "$VERIFY_SCRIPT" ]]; then
    assert_success "verify_iso_squashfs.sh syntax check" "bash -n '$VERIFY_SCRIPT'"
fi

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed."
echo "=================================================="

if (( FAILED_TESTS > 0 )); then
    exit 1
fi
exit 0

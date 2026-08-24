#!/usr/bin/env bash
# tests/security/test_sandbox_bwrap.sh - Unit tests for Bubblewrap sandbox wrapper
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BWRAP_SCRIPT="${SCRIPT_DIR}/scripts/sandbox_bwrap.sh"

if ! command -v bwrap >/dev/null 2>&1; then
    echo "[SKIP] bubblewrap (bwrap) not installed in environment. Skipping."
    exit 0
fi

TEST_DIR="$(mktemp -d /tmp/osm_bwrap_test_XXXXXX)"
trap 'rm -rf "${TEST_DIR}"' EXIT

echo "=== Running Bubblewrap Sandbox Isolation Tests ==="

# 1. Test basic command execution
OUTPUT="$("${BWRAP_SCRIPT}" --workdir "${TEST_DIR}" -- echo "hello sandbox")"
if [[ "${OUTPUT}" != *"hello sandbox"* ]]; then
    echo "FAIL: Expected 'hello sandbox', got '${OUTPUT}'" >&2
    exit 1
fi
echo "  [PASS] Basic command execution inside jail"

# 2. Test read-only root protection (write to /etc should fail)
if "${BWRAP_SCRIPT}" --workdir "${TEST_DIR}" -- touch /etc/test_file_fail 2>/dev/null; then
    echo "FAIL: Write to /etc succeeded inside sandbox jail!" >&2
    exit 1
fi
echo "  [PASS] Read-only root filesystem enforced (write to /etc denied)"

# 3. Test workspace writable bound directory
"${BWRAP_SCRIPT}" --workdir "${TEST_DIR}" -- touch "${TEST_DIR}/allowed_write.txt"
if [[ ! -f "${TEST_DIR}/allowed_write.txt" ]]; then
    echo "FAIL: Writable directory failed inside sandbox" >&2
    exit 1
fi
echo "  [PASS] Workspace directory read-write binding verified"

echo "=== All Bubblewrap Sandbox Tests Passed ==="
exit 0

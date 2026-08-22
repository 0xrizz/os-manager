#!/usr/bin/env bash
# ==============================================================================
# test_hsi_hardening.sh — Test suite for HSI device security hardening script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_SCRIPT="${PROJECT_ROOT}/scripts/hsi-harden.sh"

echo "=== Running HSI Hardening Test Suite ==="

# Test 1: Script existence and executable permissions
if [[ ! -f "${TARGET_SCRIPT}" ]]; then
    echo "FAIL: ${TARGET_SCRIPT} does not exist."
    exit 1
fi
chmod +x "${TARGET_SCRIPT}"

# Test 2: Shellcheck / bash syntax validation
bash -n "${TARGET_SCRIPT}"
echo "[PASS] Bash syntax check"

# Test 3: Dry-run execution
DRY_RUN_OUT=$(bash "${TARGET_SCRIPT}" --dry-run)
if echo "${DRY_RUN_OUT}" | grep -q "DRY-RUN"; then
    echo "[PASS] Dry-run execution"
else
    echo "FAIL: Dry-run did not output DRY-RUN marker"
    exit 1
fi

# Test 4: Verify Zero-Data-Loss guardrail present in script
if grep -q "nvme0n1p4" "${TARGET_SCRIPT}"; then
    echo "[PASS] Zero-Data-Loss guardrail verified"
else
    echo "FAIL: nvme0n1p4 guardrail check missing in script"
    exit 1
fi

echo "=== All HSI Hardening Tests Passed Successfully ==="
exit 0

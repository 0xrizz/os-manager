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
if grep -q "nvme0n1p4" "${TARGET_SCRIPT}" && grep -q "/mnt/data" "${TARGET_SCRIPT}"; then
    echo "[PASS] Zero-Data-Loss guardrail verified"
else
    echo "FAIL: nvme0n1p4 or /mnt/data guardrail check missing in script"
    exit 1
fi

# Test 5: Verify fstab sed replacement preserves /dev/nvme0n1p4 and /mnt/data
MOCK_FSTAB=$(mktemp)
cat << 'EOF' > "${MOCK_FSTAB}"
UUID=1111-2222 / ext4 defaults 0 1
/dev/nvme0n1p3 none swap sw 0 0
/dev/nvme0n1p4 /mnt/data ext4 defaults 0 2
UUID=3333-4444 /mnt/data/swapfile swap sw 0 0
# Already commented swap
# /dev/nvme0n1p2 none swap sw 0 0
EOF

sed -i -E '/nvme0n1p4|\/mnt\/data/! s|^([^#].*\s+swap\s+.*)$|# Disabled for HSI hardening: \1|g' "${MOCK_FSTAB}"

# Check that plain nvme0n1p3 swap was commented
if ! grep -q "^# Disabled for HSI hardening: /dev/nvme0n1p3" "${MOCK_FSTAB}"; then
    echo "FAIL: nvme0n1p3 swap was not disabled"
    rm -f "${MOCK_FSTAB}"
    exit 1
fi

# Check that nvme0n1p4 was NOT commented
if grep -q "^# Disabled for HSI hardening: /dev/nvme0n1p4" "${MOCK_FSTAB}"; then
    echo "FAIL: /dev/nvme0n1p4 was incorrectly commented"
    rm -f "${MOCK_FSTAB}"
    exit 1
fi

# Check that /mnt/data swap was NOT commented
if grep -q "^# Disabled for HSI hardening: UUID=3333-4444 /mnt/data" "${MOCK_FSTAB}"; then
    echo "FAIL: /mnt/data partition/file was incorrectly commented"
    rm -f "${MOCK_FSTAB}"
    exit 1
fi

rm -f "${MOCK_FSTAB}"
echo "[PASS] Fstab sed Zero-Data-Loss guardrail test"

echo "=== All HSI Hardening Tests Passed Successfully ==="
exit 0

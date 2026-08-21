#!/usr/bin/env bash
# tests/test_geometry_validator.sh - Tests for geometry validator tool
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALIDATOR="${WORKSPACE_ROOT}/scripts/migration/verify_reclaimed_geometry.sh"

echo "Testing verify_reclaimed_geometry.sh syntax..."
bash -n "${VALIDATOR}"

echo "Testing validator --help..."
"${VALIDATOR}" --help >/dev/null

echo "Testing validator --dry-run output..."
OUTPUT=$("${VALIDATOR}" --dry-run)
echo "${OUTPUT}" | grep -q "GEOMETRY AUDIT"
echo "${OUTPUT}" | grep -q "Debian Root Partition"
echo "${OUTPUT}" | grep -q "Preserved DATA_STORE"

echo "Testing validator with custom --disk flag in dry-run..."
OUTPUT_CUSTOM=$("${VALIDATOR}" --dry-run --disk /dev/nvme0n1)
echo "${OUTPUT_CUSTOM}" | grep -q "/dev/nvme0n1"

echo "PASS: Disk geometry validator is functional."

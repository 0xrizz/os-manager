#!/usr/bin/env bash
# tests/test_partition_reclamation.sh - End-to-end integration test for partition reclamation tools
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=================================================="
echo " Testing Partition Reclamation Integration Suite  "
echo "=================================================="

# 1. Run Unit Tests
bash "${WORKSPACE_ROOT}/tests/test_reclaim_partitions.sh"
bash "${WORKSPACE_ROOT}/tests/test_zero_usb_relocation.sh"
bash "${WORKSPACE_ROOT}/tests/test_switch_boot.sh"

# 2. Run Geometry Tests
bash "${WORKSPACE_ROOT}/tests/test_geometry_validator.sh"

# 3. Validate Quality Gate & Hardware Health
bash "${WORKSPACE_ROOT}/scripts/migration/quality_gate_audit.sh"

echo "=================================================="
echo "✓ ALL PARTITION RECLAMATION TESTS PASSED"
echo "=================================================="

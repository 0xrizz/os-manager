#!/usr/bin/env bash
# ==============================================================================
# run_all_tests.sh — Master E2E Test Suite for Tmux Modernization
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

echo "========================================================"
echo "    🧪 RUNNING TMUX MODERNIZATION VERIFICATION SUITE"
echo "========================================================"

run_test() {
  local t="$1"
  echo ""
  echo "--- Running $t ---"
  if bash "$SCRIPT_DIR/$t"; then
    echo "✅ $t PASSED"
  else
    echo "❌ $t FAILED"
    FAILED=$((FAILED + 1))
  fi
}

run_test "test_core_config.sh"
run_test "test_popups_statusline.sh"
run_test "test_tpm_plugins.sh"
run_test "test_agents_orchestrator.sh"
run_test "test_skill_docs.sh"

echo ""
echo "========================================================"
if [ "$FAILED" -eq 0 ]; then
  echo "🎉 ALL TESTS PASSED SUCCESSFULLY!"
  exit 0
else
  echo "💥 $FAILED TEST(S) FAILED."
  exit 1
fi

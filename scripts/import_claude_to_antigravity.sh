#!/usr/bin/env bash
# scripts/import_claude_to_antigravity.sh - Standalone import and naturalization CLI wrapper
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${WORKSPACE_ROOT}/.venv/bin/python"

if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

echo "=========================================================="
echo "   Claude-to-Antigravity Standalone Naturalizer & Importer "
echo "=========================================================="

"${PYTHON_BIN}" "${WORKSPACE_ROOT}/scripts/naturalize_antigravity_harness.py" "$@"

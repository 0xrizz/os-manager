"""Harness self-check and test runner command."""

import subprocess
import sys
from typing import List


def run_check(args: List[str]) -> int:
    """Run master test suite."""
    print("=== Running OS-Manager Master Harness Check ===")
    try:
        res = subprocess.run(["./tests/test_harness.sh"], check=False)
        return res.returncode
    except Exception as exc:
        print(f"Error executing test harness: {exc}", file=sys.stderr)
        return 1

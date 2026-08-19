"""Harness self-check and test runner command."""

import subprocess
import sys


def run_check(args: list[str]) -> int:
    """Run master test suite."""
    print("=== Running OS-Manager Master Harness Check ===")
    try:
        res = subprocess.run(["./tests/test_harness.sh"], check=False)
        return res.returncode
    except Exception as exc:
        print(f"Error executing test harness: {exc}", file=sys.stderr)
        return 1

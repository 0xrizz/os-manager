"""tests/cpu/test_affinity.py - Unit tests for process affinity execution and PID pinning."""

import os
import unittest
from unittest.mock import MagicMock, patch

from os_manager.cpu.affinity import (
    audit_process_affinity,
    execute_with_affinity,
    pin_pid_affinity,
)
from os_manager.cpu.topology import CpuTopology


class TestCpuAffinity(unittest.TestCase):
    """Test suite for imperative CPU affinity execution and PID pinning."""

    def setUp(self):
        self.mock_topo = CpuTopology(
            total_cpus=8,
            is_heterogeneous=True,
            detection_method="core_type",
            p_cores=[0, 1, 2, 3],
            e_cores=[4, 5, 6, 7],
            p_core_mask="0-3",
            e_core_mask="4-7",
            all_cores_mask="0-7",
        )

    def test_execute_with_affinity_p_core(self):
        """Verify command execution bound to P-cores."""
        with patch("os_manager.cpu.affinity.detect_cpu_topology", return_value=self.mock_topo), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            code = execute_with_affinity(["cargo", "build", "--release"], target="p-core")
            self.assertEqual(code, 0)
            mock_run.assert_called_once()
            called_cmd = mock_run.call_args[0][0]
            self.assertEqual(called_cmd, ["taskset", "-c", "0-3", "cargo", "build", "--release"])

    def test_execute_with_affinity_e_core(self):
        """Verify command execution bound to E-cores."""
        with patch("os_manager.cpu.affinity.detect_cpu_topology", return_value=self.mock_topo), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            code = execute_with_affinity(["pytest"], target="e-core")
            self.assertEqual(code, 0)
            mock_run.assert_called_once()
            called_cmd = mock_run.call_args[0][0]
            self.assertEqual(called_cmd, ["taskset", "-c", "4-7", "pytest"])

    def test_pin_pid_affinity_success(self):
        """Verify pinning existing PID affinity."""
        with patch("os_manager.cpu.affinity.detect_cpu_topology", return_value=self.mock_topo), \
             patch("os.sched_setaffinity") as mock_sched:
            res = pin_pid_affinity(pid=1234, target="p-core")
            self.assertTrue(res["success"])
            self.assertEqual(res["pid"], 1234)
            self.assertEqual(res["target"], "p-core")
            self.assertEqual(res["mask"], "0-3")
            mock_sched.assert_called_once_with(1234, {0, 1, 2, 3})

    def test_pin_pid_affinity_taskset_fallback(self):
        """Verify fallback to taskset command if os.sched_setaffinity raises PermissionError / OSError."""
        with patch("os_manager.cpu.affinity.detect_cpu_topology", return_value=self.mock_topo), \
             patch("os.sched_setaffinity", side_effect=PermissionError("Permission denied")), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="pid 1234's current affinity mask: ff\n")
            res = pin_pid_affinity(pid=1234, target="e-core")
            self.assertTrue(res["success"])
            self.assertEqual(res["mask"], "4-7")
            mock_run.assert_called_once_with(["taskset", "-cp", "4-7", "1234"], capture_output=True, text=True, check=False)

    def test_audit_process_affinity(self):
        """Verify auditing current process or target PID affinity."""
        with patch("os.sched_getaffinity", return_value={0, 1, 2, 3}):
            res = audit_process_affinity(pid=0)
            self.assertEqual(res["affinity_cores"], [0, 1, 2, 3])
            self.assertEqual(res["affinity_mask"], "0-3")

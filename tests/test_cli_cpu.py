"""tests/test_cli_cpu.py - Unit tests for osm cpu CLI subcommands."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from os_manager.cli import main
from os_manager.cpu.topology import CpuCore, CpuTopology


class TestCliCpu(unittest.TestCase):
    """Test suite for osm cpu CLI argument parsing and routing."""

    def setUp(self):
        self.mock_topo = CpuTopology(
            total_cpus=8,
            is_heterogeneous=True,
            detection_method="core_type",
            cores=[
                CpuCore(cpu_id=0, core_type="performance", max_freq_khz=4800000),
                CpuCore(cpu_id=4, core_type="efficiency", max_freq_khz=3200000),
            ],
            p_cores=[0, 1, 2, 3],
            e_cores=[4, 5, 6, 7],
            p_core_mask="0-3",
            e_core_mask="4-7",
            all_cores_mask="0-7",
        )

    def test_osm_cpu_topology_json(self):
        """Test 'osm cpu topology --json' output."""
        with patch("os_manager.commands.cpu.detect_cpu_topology", return_value=self.mock_topo), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["cpu", "topology", "--json"])
            self.assertEqual(code, 0)
            data = json.loads(mock_out.getvalue())
            self.assertEqual(data["total_cpus"], 8)
            self.assertTrue(data["is_heterogeneous"])
            self.assertEqual(data["p_core_mask"], "0-3")

    def test_osm_cpu_run_p_core(self):
        """Test 'osm cpu run --p-core echo hello'."""
        with patch("os_manager.commands.cpu.execute_with_affinity", return_value=0) as mock_exec:
            code = main(["cpu", "run", "--p-core", "echo", "hello"])
            self.assertEqual(code, 0)
            mock_exec.assert_called_once_with(["echo", "hello"], target="p-core")

    def test_osm_cpu_pin_pid(self):
        """Test 'osm cpu pin --pid 1234 --p-core'."""
        with patch("os_manager.commands.cpu.pin_pid_affinity", return_value={"success": True, "pid": 1234, "target": "p-core", "mask": "0-3"}) as mock_pin:
            code = main(["cpu", "pin", "--pid", "1234", "--p-core"])
            self.assertEqual(code, 0)
            mock_pin.assert_called_once_with(pid=1234, target="p-core")

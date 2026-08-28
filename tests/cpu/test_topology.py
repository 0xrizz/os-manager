"""tests/cpu/test_topology.py - Unit tests for CPU topology detection and cpuset range formatting."""

import os
import tempfile
import unittest
from pathlib import Path

from os_manager.cpu.topology import (
    CpuCore,
    CpuTopology,
    detect_cpu_topology,
    format_cpu_range,
)


class TestCpuTopology(unittest.TestCase):
    """Test suite for CPU topology discovery across Intel Hybrid, ARM/AMD capacity, frequency, and fallback."""

    def test_format_cpu_range_contiguous_and_disjoint(self):
        """Test formatting integer core lists to cpuset range strings."""
        self.assertEqual(format_cpu_range([]), "")
        self.assertEqual(format_cpu_range([0]), "0")
        self.assertEqual(format_cpu_range([0, 1, 2, 3]), "0-3")
        self.assertEqual(format_cpu_range([0, 1, 2, 3, 8, 9, 10, 11]), "0-3,8-11")
        self.assertEqual(format_cpu_range([0, 2, 4, 6]), "0,2,4,6")
        self.assertEqual(format_cpu_range([3, 2, 1, 0]), "0-3")

    def test_detect_cpu_topology_tier1_intel_hybrid(self):
        """Test Tier 1 detection via topology/core_type (Alder/Raptor/Arrow Lake)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create 4 P-cores (core_type: intel_core / 0x40) and 4 E-cores (core_type: intel_atom / 0x20)
            for i in range(4):
                cpu_dir = root / f"cpu{i}" / "topology"
                cpu_dir.mkdir(parents=True)
                (cpu_dir / "core_type").write_text("intel_core\n", encoding="utf-8")
            for i in range(4, 8):
                cpu_dir = root / f"cpu{i}" / "topology"
                cpu_dir.mkdir(parents=True)
                (cpu_dir / "core_type").write_text("intel_atom\n", encoding="utf-8")

            topo = detect_cpu_topology(sysfs_root=str(root))
            self.assertEqual(topo.total_cpus, 8)
            self.assertTrue(topo.is_heterogeneous)
            self.assertEqual(topo.detection_method, "core_type")
            self.assertEqual(topo.p_cores, [0, 1, 2, 3])
            self.assertEqual(topo.e_cores, [4, 5, 6, 7])
            self.assertEqual(topo.p_core_mask, "0-3")
            self.assertEqual(topo.e_core_mask, "4-7")
            self.assertEqual(topo.all_cores_mask, "0-7")

    def test_detect_cpu_topology_tier2_cpu_capacity(self):
        """Test Tier 2 detection via cpu_capacity (ARM big.LITTLE / DynamIQ)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # 2 P-cores (capacity 1024), 4 E-cores (capacity 446)
            for i in range(2):
                cpu_dir = root / f"cpu{i}"
                cpu_dir.mkdir(parents=True)
                (cpu_dir / "cpu_capacity").write_text("1024\n", encoding="utf-8")
            for i in range(2, 6):
                cpu_dir = root / f"cpu{i}"
                cpu_dir.mkdir(parents=True)
                (cpu_dir / "cpu_capacity").write_text("446\n", encoding="utf-8")

            topo = detect_cpu_topology(sysfs_root=str(root))
            self.assertEqual(topo.total_cpus, 6)
            self.assertTrue(topo.is_heterogeneous)
            self.assertEqual(topo.detection_method, "cpu_capacity")
            self.assertEqual(topo.p_cores, [0, 1])
            self.assertEqual(topo.e_cores, [2, 3, 4, 5])
            self.assertEqual(topo.p_core_mask, "0-1")
            self.assertEqual(topo.e_core_mask, "2-5")

    def test_detect_cpu_topology_tier3_max_freq(self):
        """Test Tier 3 detection via cpufreq/cpuinfo_max_freq."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # 4 High-freq cores (4800000 kHz), 4 Low-freq cores (3200000 kHz)
            for i in range(4):
                freq_dir = root / f"cpu{i}" / "cpufreq"
                freq_dir.mkdir(parents=True)
                (freq_dir / "cpuinfo_max_freq").write_text("4800000\n", encoding="utf-8")
            for i in range(4, 8):
                freq_dir = root / f"cpu{i}" / "cpufreq"
                freq_dir.mkdir(parents=True)
                (freq_dir / "cpuinfo_max_freq").write_text("3200000\n", encoding="utf-8")

            topo = detect_cpu_topology(sysfs_root=str(root))
            self.assertEqual(topo.total_cpus, 8)
            self.assertTrue(topo.is_heterogeneous)
            self.assertEqual(topo.detection_method, "max_freq")
            self.assertEqual(topo.p_cores, [0, 1, 2, 3])
            self.assertEqual(topo.e_cores, [4, 5, 6, 7])

    def test_detect_cpu_topology_tier4_homogeneous_fallback(self):
        """Test Tier 4 fallback for homogeneous systems (or WSL2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # 8 Identical cores with same freq
            for i in range(8):
                freq_dir = root / f"cpu{i}" / "cpufreq"
                freq_dir.mkdir(parents=True)
                (freq_dir / "cpuinfo_max_freq").write_text("3500000\n", encoding="utf-8")

            topo = detect_cpu_topology(sysfs_root=str(root))
            self.assertEqual(topo.total_cpus, 8)
            self.assertFalse(topo.is_heterogeneous)
            self.assertEqual(topo.detection_method, "homogeneous")
            self.assertEqual(topo.p_cores, [0, 1, 2, 3])
            self.assertEqual(topo.e_cores, [4, 5, 6, 7])
            self.assertEqual(topo.p_core_mask, "0-3")
            self.assertEqual(topo.e_core_mask, "4-7")
            self.assertEqual(topo.all_cores_mask, "0-7")

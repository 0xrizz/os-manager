"""tests/memory/test_psi_parser.py - Unit tests for Linux PSI metrics parser."""

import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from os_manager.memory.psi_daemon import (
    PsiMetrics,
    PsiReading,
    PsiThresholds,
    collect_psi_metrics,
    parse_psi_file,
    parse_psi_line,
)


class TestPsiParser(unittest.TestCase):
    """Test suite for parsing /proc/pressure/{cpu,memory,io} records."""

    def test_parse_psi_line_valid_some(self):
        """Verify parsing standard 'some' PSI line."""
        line = "some avg10=1.23 avg60=4.56 avg300=7.89 total=1234567"
        res = parse_psi_line(line)
        self.assertIsNotNone(res)
        prefix, reading = res
        self.assertEqual(prefix, "some")
        self.assertEqual(reading.avg10, 1.23)
        self.assertEqual(reading.avg60, 4.56)
        self.assertEqual(reading.avg300, 7.89)
        self.assertEqual(reading.total, 1234567)

    def test_parse_psi_line_valid_full(self):
        """Verify parsing standard 'full' PSI line."""
        line = "full avg10=0.00 avg60=0.15 avg300=0.26 total=32458166"
        res = parse_psi_line(line)
        self.assertIsNotNone(res)
        prefix, reading = res
        self.assertEqual(prefix, "full")
        self.assertEqual(reading.avg10, 0.0)
        self.assertEqual(reading.avg60, 0.15)
        self.assertEqual(reading.avg300, 0.26)
        self.assertEqual(reading.total, 32458166)

    def test_parse_psi_line_invalid(self):
        """Verify parsing invalid or empty line returns None."""
        self.assertIsNone(parse_psi_line(""))
        self.assertIsNone(parse_psi_line("invalid line without metrics"))

    def test_parse_psi_file_memory(self):
        """Verify parsing simulated /proc/pressure/memory content."""
        content = (
            "some avg10=10.50 avg60=5.20 avg300=1.10 total=500000\n"
            "full avg10=2.00 avg60=0.50 avg300=0.10 total=100000\n"
        )
        with patch("pathlib.Path.is_file", return_value=True), \
             patch("pathlib.Path.read_text", return_value=content):
            parsed = parse_psi_file("/proc/pressure/memory")
            self.assertIn("some", parsed)
            self.assertIn("full", parsed)
            self.assertEqual(parsed["some"].avg10, 10.5)
            self.assertEqual(parsed["full"].avg10, 2.0)

    def test_parse_psi_file_missing(self):
        """Verify parsing nonexistent PSI file returns empty dict."""
        with patch("pathlib.Path.is_file", return_value=False):
            parsed = parse_psi_file("/proc/pressure/nonexistent")
            self.assertEqual(parsed, {})

    def test_collect_psi_metrics_success(self):
        """Verify collect_psi_metrics aggregates cpu, memory, and io metrics."""
        sample_cpu = "some avg10=1.00 avg60=2.00 avg300=3.00 total=100\n"
        sample_mem = (
            "some avg10=4.00 avg60=5.00 avg300=6.00 total=200\n"
            "full avg10=7.00 avg60=8.00 avg300=9.00 total=300\n"
        )
        sample_io = (
            "some avg10=10.00 avg60=11.00 avg300=12.00 total=400\n"
            "full avg10=13.00 avg60=14.00 avg300=15.00 total=500\n"
        )

        def mock_read(self, *args, **kwargs):
            path_str = str(self)
            if "cpu" in path_str:
                return sample_cpu
            elif "memory" in path_str:
                return sample_mem
            elif "io" in path_str:
                return sample_io
            return ""

        with patch("pathlib.Path.is_file", return_value=True), \
             patch("pathlib.Path.read_text", mock_read):
            metrics = collect_psi_metrics()
            self.assertIsNotNone(metrics)
            self.assertEqual(metrics.cpu_some.avg10, 1.0)
            self.assertEqual(metrics.memory_some.avg10, 4.0)
            self.assertEqual(metrics.memory_full.avg10, 7.0)
            self.assertEqual(metrics.io_some.avg10, 10.0)
            self.assertEqual(metrics.io_full.avg10, 13.0)
            self.assertTrue(len(metrics.timestamp) > 0)

    def test_collect_psi_metrics_unsupported(self):
        """Verify collect_psi_metrics returns None if PSI sysfs path missing."""
        with patch("pathlib.Path.is_file", return_value=False):
            self.assertIsNone(collect_psi_metrics())

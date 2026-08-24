"""Tests for empirical benchmarking engine (osm perf)."""

import json
import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.perf import (
    run_audio_jitter_benchmark,
    run_cpu_benchmark,
    run_io_benchmark,
    run_memory_benchmark,
    run_perf,
)


class TestPerfEngine(unittest.TestCase):
    def test_run_cpu_benchmark_quick(self):
        with patch("shutil.which", return_value="/usr/bin/sysbench"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="events per second: 12500.42\ntotal time: 2.0001s\n",
                    stderr="",
                )
                res = run_cpu_benchmark(quick=True)
                self.assertTrue(res["available"])
                self.assertEqual(res["score"], 12500.42)
                self.assertEqual(res["max_prime"], 10000)
                self.assertEqual(res["threads"], 8)

    def test_run_cpu_benchmark_full(self):
        with patch("shutil.which", return_value="/usr/bin/sysbench"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="events per second: 9800.10\ntotal time: 10.0001s\n",
                    stderr="",
                )
                res = run_cpu_benchmark(quick=False)
                self.assertTrue(res["available"])
                self.assertEqual(res["score"], 9800.10)
                self.assertEqual(res["max_prime"], 30000)

    def test_run_cpu_benchmark_not_installed(self):
        with patch("shutil.which", return_value=None):
            res = run_cpu_benchmark(quick=True)
            self.assertFalse(res["available"])
            self.assertIn("reason", res)

    def test_run_cpu_benchmark_error(self):
        with patch("shutil.which", return_value="/usr/bin/sysbench"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="sysbench: command failed",
                )
                res = run_cpu_benchmark(quick=True)
                self.assertFalse(res["available"])
                self.assertEqual(res["error"], "sysbench: command failed")

    def test_run_memory_benchmark(self):
        with patch("shutil.which", return_value="/usr/bin/sysbench"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="Total operations: 1048576 (524288.00 per second)\n4096.00 MB transferred (20480.00 MB/sec)\n",
                    stderr="",
                )
                res = run_memory_benchmark(quick=True)
                self.assertTrue(res["available"])
                self.assertEqual(res["throughput_mb_s"], 20480.00)
                self.assertEqual(res["size"], "1G")

    def test_run_memory_benchmark_not_installed(self):
        with patch("shutil.which", return_value=None):
            res = run_memory_benchmark(quick=True)
            self.assertFalse(res["available"])
            self.assertIn("reason", res)

    def test_run_memory_benchmark_error(self):
        with patch("shutil.which", return_value="/usr/bin/sysbench"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="sysbench: memory error",
                )
                res = run_memory_benchmark(quick=True)
                self.assertFalse(res["available"])
                self.assertEqual(res["error"], "sysbench: memory error")

    def test_run_io_benchmark_fio(self):
        with patch("shutil.which", return_value="/usr/bin/fio"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="READ: bw=450MiB/s\nWRITE: bw=380MiB/s (398MB/s), 95000 IOPS\n",
                    stderr="",
                )
                res = run_io_benchmark(quick=True)
                self.assertTrue(res["available"])
                self.assertEqual(res["engine"], "fio")
                self.assertEqual(res["write_iops"], 95000)
                self.assertEqual(res["throughput_mb_s"], 380.0)

    def test_run_io_benchmark_fio_k_iops(self):
        with patch("shutil.which", return_value="/usr/bin/fio"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="WRITE: bw=500MiB/s (524MB/s), IOPS=120k, runt=3000msec\n",
                    stderr="",
                )
                res = run_io_benchmark(quick=True)
                self.assertTrue(res["available"])
                self.assertEqual(res["engine"], "fio")
                self.assertEqual(res["write_iops"], 120000)
                self.assertEqual(res["throughput_mb_s"], 500.0)

    def test_run_io_benchmark_fio_error(self):
        with patch("shutil.which", return_value="/usr/bin/fio"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="fio: engine libaio failed",
                )
                res = run_io_benchmark(quick=True)
                self.assertFalse(res["available"])
                self.assertEqual(res["error"], "fio: engine libaio failed")

    def test_run_io_benchmark_python_fallback(self):
        with patch("shutil.which", return_value=None):
            with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
                with patch("os.fsync"):
                    with patch("os.path.exists", return_value=True):
                        with patch("os.remove"):
                            res = run_io_benchmark(quick=True, target_path="/tmp/test_io.tmp")
                            self.assertTrue(res["available"])
                            self.assertEqual(res["engine"], "python_sync")
                            self.assertIn("write_iops", res)
                            self.assertIn("throughput_mb_s", res)

    def test_run_audio_jitter_benchmark(self):
        with patch("shutil.which", return_value="/usr/bin/pw-top"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="S ID QUANT RATE WAIT BUSY W/Q B/Q ERR NAME\n! 42 256 48000 12us 50us 0.05 0.10 3 Built-in Audio\n",
                    stderr="",
                )
                res = run_audio_jitter_benchmark()
                self.assertTrue(res["available"])
                self.assertEqual(res["xruns"], 3)
                self.assertEqual(res["active_quantum"], 256)
                self.assertEqual(res["active_rate"], 48000)

    def test_run_audio_jitter_benchmark_not_installed(self):
        with patch("shutil.which", return_value=None):
            res = run_audio_jitter_benchmark()
            self.assertFalse(res["available"])
            self.assertIn("reason", res)

    def test_run_perf_all_json(self):
        with patch("os_manager.commands.perf.run_cpu_benchmark", return_value={"available": True, "score": 100}), \
             patch("os_manager.commands.perf.run_memory_benchmark", return_value={"available": True, "throughput_mb_s": 5000}), \
             patch("os_manager.commands.perf.run_io_benchmark", return_value={"available": True, "write_iops": 50000}), \
             patch("os_manager.commands.perf.run_audio_jitter_benchmark", return_value={"available": True, "xruns": 0}):
            ret = run_perf(["all", "--json"])
            self.assertEqual(ret, 0)

    def test_run_perf_subaction_cpu(self):
        with patch("os_manager.commands.perf.run_cpu_benchmark", return_value={"available": True, "score": 15000}) as mock_cpu, \
             patch("os_manager.commands.perf.run_memory_benchmark") as mock_mem:
            ret = run_perf(["cpu", "--full"])
            self.assertEqual(ret, 0)
            mock_cpu.assert_called_once_with(quick=False)
            mock_mem.assert_not_called()

    def test_run_perf_unavailable_renderer(self):
        with patch("os_manager.commands.perf.run_cpu_benchmark", return_value={"available": False, "reason": "sysbench missing"}), \
             patch("os_manager.commands.perf.run_memory_benchmark", return_value={"available": False, "error": "failed"}), \
             patch("os_manager.commands.perf.run_io_benchmark", return_value={"available": False}), \
             patch("os_manager.commands.perf.run_audio_jitter_benchmark", return_value={"available": False}):
            ret = run_perf(["all"])
            self.assertEqual(ret, 0)

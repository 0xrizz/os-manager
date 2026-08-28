"""tests/scheduler/test_scx_probe.py - Unit tests for multi-method sched_ext compatibility and state probing."""

import gzip
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.scheduler.scx import (
    discover_installed_schedulers,
    probe_sched_ext_support,
)


class TestScxProbing(unittest.TestCase):
    """Test suite for sched_ext kernel capability probing and active scheduler detection."""

    def test_discover_installed_schedulers(self):
        """Verify discovery of scx_* binaries in standard paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir)
            (bin_dir / "scx_lavd").touch(mode=0o755)
            (bin_dir / "scx_rusty").touch(mode=0o755)
            (bin_dir / "not_a_scheduler").touch(mode=0o755)

            found = discover_installed_schedulers(search_dirs=[str(bin_dir)])
            self.assertIn("scx_lavd", found)
            self.assertIn("scx_rusty", found)
            self.assertNotIn("not_a_scheduler", found)

    def test_probe_sched_ext_supported_sysfs_enabled(self):
        """Test probing when sysfs state node exists and is enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sysfs = Path(tmpdir) / "sched_ext"
            sysfs.mkdir(parents=True)
            (sysfs / "state").write_text("enabled\n", encoding="utf-8")
            root_dir = sysfs / "root"
            root_dir.mkdir(parents=True)
            (root_dir / "ops").write_text("lavd\n", encoding="utf-8")

            with patch("os_manager.scheduler.scx.discover_installed_schedulers", return_value=["scx_lavd"]):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0, stdout="active\n")
                    status = probe_sched_ext_support(sysfs_root=str(sysfs))

                    self.assertTrue(status.kernel_supported)
                    self.assertTrue(status.sysfs_present)
                    self.assertEqual(status.active_scheduler, "lavd")
                    self.assertIn("scx_lavd", status.installed_schedulers)
                    self.assertIn("sched_ext active", status.details)

    def test_probe_sched_ext_supported_config_file(self):
        """Test probing when sysfs is absent but /boot/config-* contains CONFIG_SCHED_CLASS_EXT=y."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sysfs_empty = Path(tmpdir) / "non_existent_sysfs"
            boot_dir = Path(tmpdir) / "boot"
            boot_dir.mkdir(parents=True)
            (boot_dir / "config-6.12.10-custom").write_text("CONFIG_SCHED_CLASS_EXT=y\nCONFIG_BPF=y\n", encoding="utf-8")

            with patch("platform.release", return_value="6.12.10-custom"):
                with patch("os_manager.scheduler.scx.discover_installed_schedulers", return_value=[]):
                    status = probe_sched_ext_support(
                        sysfs_root=str(sysfs_empty),
                        boot_dir=str(boot_dir),
                        proc_config=str(Path(tmpdir) / "config.gz"),
                    )

                    self.assertTrue(status.kernel_supported)
                    self.assertFalse(status.sysfs_present)
                    self.assertIsNone(status.active_scheduler)
                    self.assertIn("supported via kernel config", status.details)

    def test_probe_sched_ext_proc_config_gz(self):
        """Test probing via /proc/config.gz gzip archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sysfs_empty = Path(tmpdir) / "non_existent_sysfs"
            boot_empty = Path(tmpdir) / "boot"
            boot_empty.mkdir(parents=True)
            gz_path = Path(tmpdir) / "config.gz"
            with gzip.open(gz_path, "wt", encoding="utf-8") as f:
                f.write("CONFIG_SCHED_CLASS_EXT=y\n")

            with patch("platform.release", return_value="6.12.0-test"):
                with patch("os_manager.scheduler.scx.discover_installed_schedulers", return_value=[]):
                    status = probe_sched_ext_support(
                        sysfs_root=str(sysfs_empty),
                        boot_dir=str(boot_empty),
                        proc_config=str(gz_path),
                    )

                    self.assertTrue(status.kernel_supported)
                    self.assertFalse(status.sysfs_present)

    def test_probe_sched_ext_unsupported_stock_kernel(self):
        """Test graceful probing on stock kernel lacking CONFIG_SCHED_CLASS_EXT."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sysfs_empty = Path(tmpdir) / "non_existent_sysfs"
            boot_dir = Path(tmpdir) / "boot"
            boot_dir.mkdir(parents=True)
            (boot_dir / "config-6.12.105+deb13-amd64").write_text("# CONFIG_SCHED_CLASS_EXT is not set\n", encoding="utf-8")

            with patch("platform.release", return_value="6.12.105+deb13-amd64"):
                with patch("os_manager.scheduler.scx.discover_installed_schedulers", return_value=[]):
                    status = probe_sched_ext_support(
                        sysfs_root=str(sysfs_empty),
                        boot_dir=str(boot_dir),
                        proc_config=str(Path(tmpdir) / "nonexistent.gz"),
                    )

                    self.assertFalse(status.kernel_supported)
                    self.assertFalse(status.sysfs_present)
                    self.assertIsNone(status.active_scheduler)
                    self.assertIn("Stock kernel detected", status.details)
                    self.assertIn("EEVDF baseline active", status.details)


if __name__ == "__main__":
    unittest.main()

"""tests/test_tune_storage.py - Unit tests for hardened ntfs3 mount and NVMe udev scheduler tuning."""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from os_manager.commands.tune import (
    audit_nvme_storage_subsystem,
    generate_hardened_fstab_ntfs3_entry,
    generate_nvme_udev_scheduler_rule,
)


class TestTuneStorage(unittest.TestCase):
    """Unit tests for storage tuning, hardened ntfs3 fstab generation, and NVMe udev rules."""

    def test_generate_hardened_fstab_ntfs3_entry(self):
        """Verify generation of hardened ntfs3 fstab entry replacing ntfs-3g."""
        sample_fstab = (
            "UUID=3E01-3117 /boot/efi vfat defaults,noatime 0 2\n"
            "UUID=6C7AB7E37AB7A7EA /mnt/data ntfs-3g defaults,uid=1000,gid=1000,umask=022,nofail 0 0\n"
        )
        updated = generate_hardened_fstab_ntfs3_entry(sample_fstab, mount_point="/mnt/data")
        self.assertIn("ntfs3", updated)
        self.assertNotIn("ntfs-3g", updated)
        self.assertIn("windows_names", updated)
        self.assertIn("prealloc", updated)
        self.assertIn("dmask=027,fmask=137", updated)
        self.assertIn("iocharset=utf8", updated)
        self.assertIn("nocase", updated)
        self.assertIn("hide_dot_files", updated)
        self.assertIn("noatime", updated)
        self.assertIn("nofail", updated)

    def test_generate_hardened_fstab_ntfs3_entry_existing_ntfs3(self):
        """Verify upgrading existing non-hardened ntfs3 fstab entry."""
        sample_fstab = (
            "UUID=6C7AB7E37AB7A7EA /mnt/data ntfs3 defaults,uid=1000,gid=1000,umask=022,nofail 0 0\n"
        )
        updated = generate_hardened_fstab_ntfs3_entry(sample_fstab, mount_point="/mnt/data")
        self.assertIn("ntfs3", updated)
        self.assertIn("windows_names", updated)
        self.assertIn("dmask=027,fmask=137", updated)

    def test_generate_hardened_fstab_ntfs3_entry_unrelated_mount(self):
        """Verify unrelated mount points are preserved untouched."""
        sample_fstab = (
            "UUID=1234-5678 / ext4 defaults,noatime 0 1\n"
            "UUID=3E01-3117 /boot/efi vfat defaults,noatime 0 2\n"
        )
        updated = generate_hardened_fstab_ntfs3_entry(sample_fstab, mount_point="/mnt/data")
        self.assertEqual(sample_fstab, updated)

    def test_generate_nvme_udev_scheduler_rule(self):
        """Verify NVMe udev rule assigns none scheduler and 256 queue depth."""
        rule = generate_nvme_udev_scheduler_rule()
        self.assertIn('KERNEL=="nvme[0-9]*n[0-9]*"', rule)
        self.assertIn('ATTR{queue/scheduler}="none"', rule)
        self.assertIn('ATTR{queue/nr_requests}="256"', rule)
        self.assertIn('ACTION=="add|change"', rule)

    def test_audit_nvme_storage_subsystem(self):
        """Verify telemetry collection for storage subsystem."""
        res = audit_nvme_storage_subsystem()
        self.assertIn("ntfs3_active", res)
        self.assertIn("ntfs_driver", res)
        self.assertIn("trim_active", res)
        self.assertIn("nvme_scheduler", res)
        self.assertIn("nvme_nr_requests", res)

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.read_text")
    @patch("os_manager.commands.tune.audit_ntfs_mount_driver")
    @patch("os_manager.commands.tune.audit_fstrim_timer_status")
    def test_audit_nvme_storage_subsystem_mocked(self, mock_trim, mock_ntfs, mock_read, mock_is_file):
        """Verify audit parsing with mocked sysfs files."""
        mock_trim.return_value = {"active": True}
        mock_ntfs.return_value = {"driver": "ntfs3", "is_inkernel": True, "mount_point": "/mnt/data"}
        mock_is_file.return_value = True

        def fake_read_text(*args, **kwargs):
            return "[none] mq-deadline kyber bfq"

        mock_read.side_effect = fake_read_text

        with patch.object(Path, "read_text", side_effect=["[none] mq-deadline", "256"]):
            res = audit_nvme_storage_subsystem()
            self.assertTrue(res["ntfs3_active"])
            self.assertEqual(res["ntfs_driver"], "ntfs3")
            self.assertTrue(res["trim_active"])
            self.assertEqual(res["nvme_scheduler"], "none")
            self.assertEqual(res["nvme_nr_requests"], "256")

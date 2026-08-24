import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from os_manager.commands.tune import (
    create_system_snapshot,
    list_system_snapshots,
    revert_system_snapshot,
)


class TestTuneRevert(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.backup_dir = os.path.join(self.test_dir, "snapshots")
        self.sample_conf = os.path.join(self.test_dir, "99-sample.conf")
        Path(self.sample_conf).write_text("vm.swappiness = 10\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_snapshot_success(self):
        snap = create_system_snapshot(
            caller="osm tune memory --apply",
            target_files=[self.sample_conf],
            backup_dir=self.backup_dir,
        )
        self.assertTrue(snap["success"])
        self.assertIn("snapshot_id", snap)
        snap_path = Path(self.backup_dir) / snap["snapshot_id"]
        self.assertTrue((snap_path / "manifest.json").is_file())
        manifest = json.loads((snap_path / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["caller"], "osm tune memory --apply")
        self.assertIn(self.sample_conf, manifest["backed_up_files"])

    def test_list_snapshots(self):
        create_system_snapshot(
            caller="test 1",
            target_files=[self.sample_conf],
            backup_dir=self.backup_dir,
        )
        snaps = list_system_snapshots(backup_dir=self.backup_dir)
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["caller"], "test 1")

    def test_revert_snapshot_success(self):
        snap = create_system_snapshot(
            caller="before modify",
            target_files=[self.sample_conf],
            backup_dir=self.backup_dir,
        )
        # Modify file
        Path(self.sample_conf).write_text("vm.swappiness = 180\n", encoding="utf-8")
        self.assertEqual(Path(self.sample_conf).read_text(encoding="utf-8").strip(), "vm.swappiness = 180")

        # Revert
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = revert_system_snapshot(snapshot_id=snap["snapshot_id"], backup_dir=self.backup_dir)
            self.assertTrue(res["success"])
            self.assertEqual(Path(self.sample_conf).read_text(encoding="utf-8").strip(), "vm.swappiness = 10")

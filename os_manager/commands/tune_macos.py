"""macOS Desktop Transformation and Customization Engine for Debian 13 GNOME."""

import datetime
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_BACKUP_DIR = os.path.expanduser("~/.config/osm/backups")


def get_backup_directory(custom_dir: str | None = None) -> Path:
    """Resolve and ensure backup directory exists."""
    p = Path(custom_dir) if custom_dir else Path(DEFAULT_BACKUP_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def create_desktop_snapshot(backup_dir: str | None = None) -> str | None:
    """Create a timestamped dconf dump of /org/gnome/ settings."""
    bdir = get_backup_directory(backup_dir)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot_file = bdir / f"desktop-{timestamp}.dconf"

    try:
        with open(snapshot_file, "w", encoding="utf-8") as f:
            res = subprocess.run(["dconf", "dump", "/org/gnome/"], stdout=f, check=False)
            if res.returncode == 0:
                return str(snapshot_file)
            return None
    except Exception:
        return None


def list_desktop_snapshots(backup_dir: str | None = None) -> list[Path]:
    """List available desktop dconf snapshots sorted by creation time."""
    bdir = get_backup_directory(backup_dir)
    snapshots = list(bdir.glob("desktop-*.dconf"))
    snapshots.sort(key=lambda p: p.name, reverse=True)
    return snapshots


def find_latest_snapshot(backup_dir: str | None = None) -> Path | None:
    """Find the most recent desktop snapshot file."""
    snapshots = list_desktop_snapshots(backup_dir)
    return snapshots[0] if snapshots else None


def restore_desktop_snapshot(snapshot_file: str | None = None, backup_dir: str | None = None) -> bool:
    """Restore GNOME desktop settings from snapshot file."""
    if snapshot_file:
        p = Path(snapshot_file)
    else:
        latest = find_latest_snapshot(backup_dir)
        if not latest:
            return False
        p = latest

    if not p.is_file():
        return False

    try:
        with open(p, "r", encoding="utf-8") as f:
            res = subprocess.run(["dconf", "load", "/org/gnome/"], stdin=f, check=False)
            return res.returncode == 0
    except Exception:
        return False

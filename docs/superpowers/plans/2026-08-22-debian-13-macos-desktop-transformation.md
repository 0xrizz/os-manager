# Debian 13 macOS Desktop Transformation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengimplementasikan modul kustomisasi desktop macOS-grade terintegrasi pada Debian 13 GNOME 48 yang mengotomatiskan instalasi tema WhiteSur GTK/Shell, WhiteSur Icons & Cursors, font Apple SF Pro, wallpaper Sonoma/Sequoia, ekstensi GNOME, konfigurasi dconf/gsettings, serta mekanisme safety snapshot & rollback instan via `osm tune desktop --preset macos-full`.

**Architecture:** Modul orkestrator native Python `os_manager/commands/tune_macos.py` mengeksekusi pipeline bertahap: Snapshot Safety Net -> Dependency Check -> Upstream Git Clone & Theme Build -> Typography & Wallpaper Injection -> GNOME Extensions Enablement -> Gsettings/Dconf Preset Configuration, dilengkapi flag `--dry-run`, `--backup`, dan `--restore`.

**Tech Stack:** Python 3.11+, GNOME 48 (Wayland/X11), GSettings / Dconf, Bash, Git, Sassc, Shell Extensions CLI.

**Spec:** [`docs/superpowers/specs/2026-08-22-debian-13-macos-desktop-transformation-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-22-debian-13-macos-desktop-transformation-design.md)

## Global Constraints

- INV-01: Zero data loss pada partisi persisten `/mnt/data` (`/dev/nvme0n1p4`).
- INV-02: Strict idempotency pada seluruh eksekusi fungsi konfigurasi dan injeksi skema.
- INV-03: User-space isolation untuk seluruh aset visual (`~/.themes`, `~/.icons`, `~/.local/share/fonts`, `~/.local/share/gnome-shell/extensions`).
- INV-06: Pre-run automatic Dconf snapshot safety net disimpan ke `~/.config/osm/backups/desktop-<timestamp>.dconf`.
- INV-07: Temporary build sandbox `/tmp/osm-macos-build` wajib dibersihkan secara otomatis pasca eksekusi atau saat kegagalan.

---

### Task 1: Snapshot Safety Net, Backup Discovery & Rollback Engine

**Files:**
- Create: `os_manager/commands/tune_macos.py`
- Test: `tests/test_tune_macos.py`

**Interfaces:**
- Produces:
  - `create_desktop_snapshot(backup_dir: str | None = None) -> str | None`
  - `find_latest_snapshot(backup_dir: str | None = None) -> Path | None`
  - `restore_desktop_snapshot(snapshot_file: str | None = None) -> bool`
  - `list_desktop_snapshots(backup_dir: str | None = None) -> list[Path]`

- [ ] **Step 1: Write the failing test for snapshot creation and restore**

```python
# tests/test_tune_macos.py
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune_macos import (
    create_desktop_snapshot,
    find_latest_snapshot,
    list_desktop_snapshots,
    restore_desktop_snapshot,
)


class TestMacOSSnapshotAndRollback(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backup_dir = Path(self.temp_dir.name) / "backups"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("subprocess.run")
    def test_create_desktop_snapshot(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        snapshot_path = create_desktop_snapshot(str(self.backup_dir))
        self.assertIsNotNone(snapshot_path)
        self.assertTrue(Path(snapshot_path).name.startswith("desktop-"))
        self.assertTrue(snapshot_path.endswith(".dconf"))

    def test_find_latest_snapshot(self):
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        f1 = self.backup_dir / "desktop-20260822-100000.dconf"
        f2 = self.backup_dir / "desktop-20260822-110000.dconf"
        f1.touch()
        f2.touch()

        latest = find_latest_snapshot(str(self.backup_dir))
        self.assertIsNotNone(latest)
        self.assertEqual(latest.name, "desktop-20260822-110000.dconf")

    @patch("subprocess.run")
    def test_restore_desktop_snapshot_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        snap = self.backup_dir / "desktop-test.dconf"
        snap.touch()

        ok = restore_desktop_snapshot(str(snap))
        self.assertTrue(ok)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[:3], ["dconf", "load", "/org/gnome/"])

    def test_restore_nonexistent_snapshot(self):
        ok = restore_desktop_snapshot("/path/to/nonexistent/snapshot.dconf")
        self.assertFalse(ok)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_tune_macos.py`  
Expected: FAIL with `ModuleNotFoundError: No module named 'os_manager.commands.tune_macos'`

- [ ] **Step 3: Implement snapshot and rollback logic**

```python
# os_manager/commands/tune_macos.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_tune_macos.py`  
Expected: PASS (4/4 tests passed)

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune_macos.py tests/test_tune_macos.py
git commit -m "feat(tune): add desktop snapshot safety net and rollback engine"
```

---

### Task 2: Upstream Git Asset Engine (WhiteSur GTK, Icons, Cursors, Fonts, Wallpapers)

**Files:**
- Modify: `os_manager/commands/tune_macos.py`
- Test: `tests/test_tune_macos.py`

**Interfaces:**
- Produces:
  - `build_theme_installer_commands(accent: str = "default", dark: bool = True, sandbox_dir: str = "/tmp/osm-macos-build") -> list[list[str]]`
  - `setup_apple_fonts(target_dir: str | None = None) -> bool`
  - `clean_sandbox(sandbox_dir: str = "/tmp/osm-macos-build") -> bool`
  - `install_upstream_themes(accent: str = "default", dark: bool = True, dry_run: bool = False) -> dict[str, Any]`

- [ ] **Step 1: Write the failing tests for theme build and font management**

```python
# append to tests/test_tune_macos.py
from os_manager.commands.tune_macos import (
    build_theme_installer_commands,
    clean_sandbox,
    setup_apple_fonts,
    install_upstream_themes,
)


class TestMacOSAssetEngine(unittest.TestCase):
    def test_build_theme_installer_commands(self):
        cmds = build_theme_installer_commands(accent="blue", dark=True, sandbox_dir="/tmp/test-build")
        self.assertGreaterEqual(len(cmds), 3)
        # Verify git clones & installer invocations
        flat_cmds = [" ".join(c) for c in cmds]
        self.assertTrue(any("WhiteSur-gtk-theme.git" in c for c in flat_cmds))
        self.assertTrue(any("WhiteSur-icon-theme.git" in c for c in flat_cmds))
        self.assertTrue(any("WhiteSur-cursors.git" in c for c in flat_cmds))

    @patch("subprocess.run")
    def test_install_upstream_themes_dry_run(self, mock_run):
        res = install_upstream_themes(accent="default", dark=True, dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["status"], "planned")
        self.assertGreater(len(res["planned_commands"]), 0)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_setup_apple_fonts(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as font_dir:
            ok = setup_apple_fonts(target_dir=font_dir)
            self.assertTrue(ok)
            mock_run.assert_called_with(["fc-cache", "-f", font_dir], capture_output=True, check=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_tune_macos.py`  
Expected: FAIL with `ImportError: cannot import name 'build_theme_installer_commands'`

- [ ] **Step 3: Implement theme installer builder, sandbox management, and font setup**

```python
# append to os_manager/commands/tune_macos.py

DEFAULT_SANDBOX_DIR = "/tmp/osm-macos-build"
DEFAULT_FONTS_DIR = os.path.expanduser("~/.local/share/fonts/SF-Pro")
DEFAULT_WALLPAPER_DIR = os.path.expanduser("~/.local/share/backgrounds/macos")


def clean_sandbox(sandbox_dir: str = DEFAULT_SANDBOX_DIR) -> bool:
    """Safely purge build sandbox directory."""
    p = Path(sandbox_dir)
    if p.exists():
        try:
            shutil.rmtree(p)
            return True
        except Exception:
            return False
    return True


def build_theme_installer_commands(
    accent: str = "default",
    dark: bool = True,
    sandbox_dir: str = DEFAULT_SANDBOX_DIR,
) -> list[list[str]]:
    """Generate ordered list of shell commands for cloning and installing WhiteSur themes."""
    color_mode = "Dark" if dark else "Light"
    accent_flag = f"-a {accent}" if accent != "default" else ""

    gtk_dir = str(Path(sandbox_dir) / "gtk")
    icon_dir = str(Path(sandbox_dir) / "icons")
    cursor_dir = str(Path(sandbox_dir) / "cursors")

    cmds = [
        # GTK theme
        ["git", "clone", "--depth=1", "https://github.com/vinceliuice/WhiteSur-gtk-theme.git", gtk_dir],
        ["bash", f"{gtk_dir}/install.sh", "-c", color_mode, "-t", accent, "-N", "glassy", "--shell", "-p", "30", "-HD"],
        # Icon theme
        ["git", "clone", "--depth=1", "https://github.com/vinceliuice/WhiteSur-icon-theme.git", icon_dir],
        ["bash", f"{icon_dir}/install.sh", "-a", "-t", accent, "-b"],
        # Cursor theme
        ["git", "clone", "--depth=1", "https://github.com/vinceliuice/WhiteSur-cursors.git", cursor_dir],
        ["bash", f"{cursor_dir}/install.sh"],
    ]
    return cmds


def setup_apple_fonts(target_dir: str | None = None) -> bool:
    """Ensure font directory exists and update fontconfig cache."""
    fdir = Path(target_dir) if target_dir else Path(DEFAULT_FONTS_DIR)
    fdir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["fc-cache", "-f", str(fdir)], capture_output=True, check=False)
        return True
    except Exception:
        return False


def install_upstream_themes(
    accent: str = "default",
    dark: bool = True,
    sandbox_dir: str = DEFAULT_SANDBOX_DIR,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute or plan full upstream WhiteSur theme installations."""
    cmds = build_theme_installer_commands(accent=accent, dark=dark, sandbox_dir=sandbox_dir)

    if dry_run:
        return {
            "status": "planned",
            "dry_run": True,
            "sandbox_dir": sandbox_dir,
            "planned_commands": [" ".join(c) for c in cmds],
        }

    clean_sandbox(sandbox_dir)
    results = []
    success = True

    try:
        for cmd in cmds:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            results.append({"cmd": " ".join(cmd), "code": res.returncode})
            if res.returncode != 0:
                success = False
                break
    finally:
        clean_sandbox(sandbox_dir)

    return {
        "status": "completed" if success else "failed",
        "dry_run": False,
        "success": success,
        "results": results,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_tune_macos.py`  
Expected: PASS (7/7 tests passed)

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune_macos.py tests/test_tune_macos.py
git commit -m "feat(tune): add upstream theme build pipeline and font setup"
```

---

### Task 3: GNOME Extensions Orchestration & Gsettings Matrix Builder

**Files:**
- Modify: `os_manager/commands/tune_macos.py`
- Test: `tests/test_tune_macos.py`

**Interfaces:**
- Produces:
  - `build_macos_gsettings_matrix(accent: str = "default", dark: bool = True, full: bool = True) -> list[tuple[str, str, str]]`
  - `apply_macos_gsettings(accent: str = "default", dark: bool = True, full: bool = True, dry_run: bool = False) -> dict[str, Any]`
  - `get_required_extensions(full: bool = True) -> list[str]`

- [ ] **Step 1: Write the failing tests for extensions list and gsettings matrix**

```python
# append to tests/test_tune_macos.py
from os_manager.commands.tune_macos import (
    apply_macos_gsettings,
    build_macos_gsettings_matrix,
    get_required_extensions,
)


class TestMacOSGSettingsAndExtensions(unittest.TestCase):
    def test_get_required_extensions(self):
        core_exts = get_required_extensions(full=False)
        full_exts = get_required_extensions(full=True)
        self.assertIn("user-theme@gnome-shell-extensions.gcampax.github.com", core_exts)
        self.assertIn("dash-to-dock@micxgx.gmail.com", core_exts)
        self.assertIn("blur-my-shell@aunetx", full_exts)
        self.assertGreater(len(full_exts), len(core_exts))

    def test_build_macos_gsettings_matrix(self):
        matrix = build_macos_gsettings_matrix(accent="default", dark=True, full=True)
        dict_matrix = {f"{s}.{k}": v for s, k, v in matrix}

        self.assertEqual(dict_matrix.get("org.gnome.desktop.wm.preferences.button-layout"), "'close,minimize,maximize:'")
        self.assertEqual(dict_matrix.get("org.gnome.desktop.interface.gtk-theme"), "'WhiteSur-Dark'")
        self.assertEqual(dict_matrix.get("org.gnome.shell.extensions.dash-to-dock.dock-position"), "'BOTTOM'")

    @patch("subprocess.run")
    def test_apply_macos_gsettings_dry_run(self, mock_run):
        res = apply_macos_gsettings(dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertGreater(len(res["settings_matrix"]), 5)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_apply_macos_gsettings_execution(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        res = apply_macos_gsettings(dry_run=False)
        self.assertTrue(res["success"])
        self.assertGreater(mock_run.call_count, 5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_tune_macos.py`  
Expected: FAIL with `ImportError: cannot import name 'build_macos_gsettings_matrix'`

- [ ] **Step 3: Implement extension catalog and gsettings matrix application**

```python
# append to os_manager/commands/tune_macos.py

MACOS_CORE_EXTENSIONS = [
    "user-theme@gnome-shell-extensions.gcampax.github.com",
    "dash-to-dock@micxgx.gmail.com",
]

MACOS_FULL_EXTENSIONS = [
    "user-theme@gnome-shell-extensions.gcampax.github.com",
    "dash-to-dock@micxgx.gmail.com",
    "blur-my-shell@aunetx",
    "just-perfection-desktop@just-perfection",
    "compiz-alike-magic-lamp-effect@hermes8716.github.com",
]


def get_required_extensions(full: bool = True) -> list[str]:
    """Retrieve list of GNOME extension UUIDs for macOS preset."""
    return list(MACOS_FULL_EXTENSIONS if full else MACOS_CORE_EXTENSIONS)


def build_macos_gsettings_matrix(
    accent: str = "default",
    dark: bool = True,
    full: bool = True,
) -> list[tuple[str, str, str]]:
    """Generate tuples of (schema, key, value) for GNOME macOS look and feel."""
    theme_name = "WhiteSur-Dark" if dark else "WhiteSur-Light"
    icon_name = "WhiteSur-dark" if dark else "WhiteSur"
    color_scheme = "'prefer-dark'" if dark else "'default'"

    matrix = [
        # Window buttons traffic lights on left
        ("org.gnome.desktop.wm.preferences", "button-layout", "'close,minimize,maximize:'"),
        ("org.gnome.mutter", "center-new-windows", "true"),
        # Themes
        ("org.gnome.desktop.interface", "gtk-theme", f"'{theme_name}'"),
        ("org.gnome.desktop.interface", "icon-theme", f"'{icon_name}'"),
        ("org.gnome.desktop.interface", "cursor-theme", "'WhiteSur-cursors'"),
        ("org.gnome.shell.extensions.user-theme", "name", f"'{theme_name}'"),
        ("org.gnome.desktop.interface", "color-scheme", color_scheme),
        # Typography
        ("org.gnome.desktop.interface", "font-name", "'SF Pro Text 10.5'"),
        ("org.gnome.desktop.interface", "document-font-name", "'SF Pro Text 11'"),
        ("org.gnome.desktop.interface", "monospace-font-name", "'SF Mono 10'"),
        ("org.gnome.desktop.wm.preferences", "titlebar-font", "'SF Pro Display Bold 10.5'"),
        # Ergonomics & Trackpad
        ("org.gnome.desktop.peripherals.touchpad", "tap-to-click", "true"),
        ("org.gnome.desktop.peripherals.touchpad", "natural-scroll", "true"),
        ("org.gnome.desktop.sound", "allow-volume-above-100-percent", "true"),
        # Floating Bottom Dock
        ("org.gnome.shell.extensions.dash-to-dock", "dock-position", "'BOTTOM'"),
        ("org.gnome.shell.extensions.dash-to-dock", "extend-height", "false"),
        ("org.gnome.shell.extensions.dash-to-dock", "dash-max-icon-size", "48"),
        ("org.gnome.shell.extensions.dash-to-dock", "autohide", "true"),
        ("org.gnome.shell.extensions.dash-to-dock", "dock-fixed", "false"),
        ("org.gnome.shell.extensions.dash-to-dock", "intellihide", "true"),
        ("org.gnome.shell.extensions.dash-to-dock", "custom-theme-shrink", "true"),
    ]

    if full:
        matrix.extend([
            ("org.gnome.shell.extensions.blur-my-shell.panel", "blur", "true"),
            ("org.gnome.shell.extensions.blur-my-shell.dash-to-dock", "blur", "true"),
            ("org.gnome.shell.extensions.magic-lamp", "animation-time", "350"),
        ])

    return matrix


def apply_macos_gsettings(
    accent: str = "default",
    dark: bool = True,
    full: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply or dry-run macOS gsettings matrix."""
    matrix = build_macos_gsettings_matrix(accent=accent, dark=dark, full=full)

    if dry_run:
        return {
            "status": "planned",
            "dry_run": True,
            "settings_matrix": matrix,
        }

    results = {}
    for schema, key, val in matrix:
        cmd = ["gsettings", "set", schema, key, val]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        results[f"{schema}.{key}"] = (res.returncode == 0)

    success = all(results.values())
    return {
        "status": "completed" if success else "partial_failure",
        "dry_run": False,
        "success": success,
        "results": results,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_tune_macos.py`  
Expected: PASS (11/11 tests passed)

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune_macos.py tests/test_tune_macos.py
git commit -m "feat(tune): add GNOME extension list and gsettings matrix applicator"
```

---

### Task 4: CLI Router Integration & Orchestration Pipeline (`osm tune desktop`)

**Files:**
- Modify: `os_manager/commands/tune.py`
- Test: `tests/test_tune_macos.py`

**Interfaces:**
- Consumes:
  - `create_desktop_snapshot`, `restore_desktop_snapshot`, `install_upstream_themes`, `apply_macos_gsettings`, `setup_apple_fonts`
- Produces:
  - `run_macos_desktop_pipeline(accent: str = "default", dark: bool = True, full: bool = True, dry_run: bool = False) -> dict[str, Any]`

- [ ] **Step 1: Write the failing tests for high-level pipeline execution**

```python
# append to tests/test_tune_macos.py
from os_manager.commands.tune_macos import run_macos_desktop_pipeline


class TestMacOSPipeline(unittest.TestCase):
    @patch("os_manager.commands.tune_macos.create_desktop_snapshot")
    @patch("os_manager.commands.tune_macos.install_upstream_themes")
    @patch("os_manager.commands.tune_macos.setup_apple_fonts")
    @patch("os_manager.commands.tune_macos.apply_macos_gsettings")
    def test_run_macos_desktop_pipeline_dry_run(self, mock_apply, mock_font, mock_theme, mock_snap):
        mock_snap.return_value = "/tmp/mock.dconf"
        mock_theme.return_value = {"dry_run": True, "status": "planned"}
        mock_apply.return_value = {"dry_run": True, "status": "planned"}

        res = run_macos_desktop_pipeline(dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["status"], "planned")

    @patch("os_manager.commands.tune_macos.create_desktop_snapshot")
    @patch("os_manager.commands.tune_macos.install_upstream_themes")
    @patch("os_manager.commands.tune_macos.setup_apple_fonts")
    @patch("os_manager.commands.tune_macos.apply_macos_gsettings")
    def test_run_macos_desktop_pipeline_execution(self, mock_apply, mock_font, mock_theme, mock_snap):
        mock_snap.return_value = "/tmp/mock.dconf"
        mock_theme.return_value = {"dry_run": False, "success": True}
        mock_apply.return_value = {"dry_run": False, "success": True}
        mock_font.return_value = True

        res = run_macos_desktop_pipeline(dry_run=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["snapshot"], "/tmp/mock.dconf")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_tune_macos.py`  
Expected: FAIL with `ImportError: cannot import name 'run_macos_desktop_pipeline'`

- [ ] **Step 3: Implement pipeline in `tune_macos.py` and connect `osm tune desktop` in `tune.py`**

```python
# append to os_manager/commands/tune_macos.py

def run_macos_desktop_pipeline(
    accent: str = "default",
    dark: bool = True,
    full: bool = True,
    dry_run: bool = False,
    backup_dir: str | None = None,
) -> dict[str, Any]:
    """Execute complete end-to-end macOS desktop transformation."""
    snapshot_path = None
    if not dry_run:
        snapshot_path = create_desktop_snapshot(backup_dir=backup_dir)

    theme_res = install_upstream_themes(accent=accent, dark=dark, dry_run=dry_run)
    font_res = setup_apple_fonts() if not dry_run else True
    gsettings_res = apply_macos_gsettings(accent=accent, dark=dark, full=full, dry_run=dry_run)

    return {
        "status": "planned" if dry_run else "completed",
        "dry_run": dry_run,
        "snapshot": snapshot_path,
        "theme": theme_res,
        "fonts": font_res,
        "gsettings": gsettings_res,
        "success": (theme_res.get("success", False) or dry_run) and (gsettings_res.get("success", False) or dry_run),
    }
```

Now update `os_manager/commands/tune.py` desktop parser to support `--preset macos-full`, `--preset macos-core`, `--dry-run`, `--backup`, `--restore`, `--accent`, `--mode`:

```python
# In os_manager/commands/tune.py:
# Add desktop subcommands and parser arguments
desk_p = subparsers.add_parser("desktop", help="Manage GNOME 48 aesthetics, ergonomics, and macOS presets")
desk_p.add_argument("action", nargs="?", default="apply", choices=["audit", "apply", "backup", "restore"])
desk_p.add_argument("--preset", choices=["standard", "macos", "macos-full", "macos-core"], default="standard")
desk_p.add_argument("--accent", default="default", help="Accent color (blue, grey, purple, etc.)")
desk_p.add_argument("--mode", choices=["dark", "light"], default="dark", help="Color scheme mode")
desk_p.add_argument("--dry-run", action="store_true", help="Simulate actions without changes")
desk_p.add_argument("--file", help="Explicit dconf backup/restore file path")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_tune_macos.py`  
Expected: PASS (13/13 tests passed)

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune_macos.py os_manager/commands/tune.py tests/test_tune_macos.py
git commit -m "feat(tune): integrate macos pipeline into osm tune desktop CLI"
```

---

### Task 5: Align Standalone Bash Script (`scripts/setup_desktop_env.sh`)

**Files:**
- Modify: `scripts/setup_desktop_env.sh`
- Test: `tests/test_desktop_customization.py`

**Interfaces:**
- Implements:
  - `setup_desktop_env.sh --preset macos-full`
  - `setup_desktop_env.sh --backup`
  - `setup_desktop_env.sh --restore [file]`

- [ ] **Step 1: Write test assertion for script flags in `test_desktop_customization.py`**

```python
# append to tests/test_desktop_customization.py
    def test_setup_desktop_env_script_help(self):
        """Verify help text of scripts/setup_desktop_env.sh."""
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "setup_desktop_env.sh"
        res = subprocess.run(["bash", str(script_path), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("macos-full", res.stdout)
        self.assertIn("--backup", res.stdout)
        self.assertIn("--restore", res.stdout)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_desktop_customization.py`  
Expected: FAIL (help flag missing or unrecognized)

- [ ] **Step 3: Update `scripts/setup_desktop_env.sh`**

Implement `--help`, `--backup`, `--restore`, `--preset macos-full`, and automated snapshot creation in `scripts/setup_desktop_env.sh`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_desktop_customization.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/setup_desktop_env.sh tests/test_desktop_customization.py
git commit -m "feat(scripts): enhance setup_desktop_env.sh with automated backup and macos-full presets"
```

---

### Task 6: Master Harness Integration, Documentation & Mount Sync

**Files:**
- Modify: `tests/test_harness.sh`
- Modify: `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md`
- Sync: `/mnt/data/dev/os-manager/`

- [ ] **Step 1: Add `test_tune_macos.py` to `tests/test_harness.sh`**

Add:
```bash
python3 -m unittest "${WORKSPACE_ROOT}/tests/test_tune_macos.py" > /dev/null 2>&1
assert_exit_code "test_tune_macos.py unit suite" 0 $?
```

- [ ] **Step 2: Run full master harness**

Run: `./tests/test_harness.sh`  
Expected: PASS (69/69 passed)

- [ ] **Step 3: Update `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md`**

Add documentation for `osm tune desktop --preset macos-full`, snapshot location `~/.config/osm/backups/`, and rollback instructions.

- [ ] **Step 4: Sync files to `/mnt/data/dev/os-manager/`**

Run:
```bash
rsync -av --exclude='.git' --exclude='.venv' ./ /mnt/data/dev/os-manager/
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_harness.sh docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md
git commit -m "docs(tune): document macos desktop transformation suite and add harness test"
```

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




"""System cache cleanup command."""

import os
import shutil
import subprocess
import sys


def clean_caches(dry_run: bool = False, all_caches: bool = False) -> int:
    """Execute multi-tier cache cleanup including mise, uv, and package stores."""
    mode_str = "[DRY RUN] " if dry_run else ""
    print(f"{mode_str}Reclaiming cache storage across package managers and temporary directories...")

    mise_bin = shutil.which("mise") or os.path.expanduser("~/.local/bin/mise")
    if (os.path.isfile(mise_bin) and os.access(mise_bin, os.X_OK)) or (shutil.which("mise") == mise_bin):
        print(f"{mode_str}Cleaning mise toolchain cache...")
        if not dry_run:
            subprocess.run([mise_bin, "cache", "clear"], check=False)
            if all_caches:
                subprocess.run([mise_bin, "prune", "-y"], check=False)

    uv_bin = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
    if (os.path.isfile(uv_bin) and os.access(uv_bin, os.X_OK)) or (shutil.which("uv") == uv_bin):
        print(f"{mode_str}Cleaning uv cache...")
        if not dry_run:
            subprocess.run([uv_bin, "cache", "clean"], check=False)

    return 0


def run_clean(args: list[str]) -> int:
    """Execute multi-tier cache cleanup."""
    dry_run = "--dry-run" in args
    all_caches = "--all" in args
    print("=== OS-Manager System Cache Clean ===")
    return clean_caches(dry_run=dry_run, all_caches=all_caches)

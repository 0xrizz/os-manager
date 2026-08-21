"""Debian 13 (Trixie) upgrade management command."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_upgrade_script_path() -> Path:
    """Resolve absolute path to scripts/upgrade_debian_trixie.sh."""
    current_dir = Path(__file__).resolve().parent
    workspace_root = current_dir.parent.parent
    return workspace_root / "scripts" / "upgrade_debian_trixie.sh"


def ensure_tmux_installed() -> bool:
    """Check if tmux is installed; offer installation if running with root privileges."""
    if shutil.which("tmux"):
        return True

    print("[WARN] tmux is not installed on this system.", file=sys.stderr)
    if os.geteuid() == 0:
        print("[INFO] Attempting to install tmux via apt-get...", file=sys.stderr)
        res = subprocess.run(["apt-get", "update"], check=False)
        if res.returncode == 0:
            install_res = subprocess.run(["apt-get", "install", "-y", "tmux"], check=False)
            return install_res.returncode == 0
    else:
        print("[ERROR] Please install tmux before running upgrade: sudo apt install -y tmux", file=sys.stderr)

    return bool(shutil.which("tmux"))


def rebuild_virtualenv(target_dir: str | None = None) -> int:
    """Rebuild Python virtual environment following Python runtime upgrades."""
    workspace_root = Path(__file__).resolve().parent.parent.parent
    venv_path = Path(target_dir) if target_dir else workspace_root / ".venv"

    print(f"[INFO] Rebuilding Python virtual environment at {venv_path}...")
    if venv_path.exists():
        print(f"[INFO] Removing outdated virtual environment: {venv_path}")
        shutil.rmtree(venv_path)

    print(f"[INFO] Creating fresh virtualenv using host Python: {sys.executable}")
    res = subprocess.run([sys.executable, "-m", "venv", str(venv_path)])
    if res.returncode != 0:
        print("[ERROR] Failed to create new virtualenv.", file=sys.stderr)
        return res.returncode

    pip_path = venv_path / "bin" / "pip"
    if pip_path.exists() and (workspace_root / "pyproject.toml").exists():
        print("[INFO] Installing project dependencies into fresh virtualenv...")
        subprocess.run([str(pip_path), "install", "-e", str(workspace_root)], check=False)

    print("[PASS] Virtual environment rebuilt successfully.")
    return 0


def run_upgrade(args: list[str]) -> int:
    """Execute upgrade CLI subcommand routing."""
    parser = argparse.ArgumentParser(
        prog="osm upgrade",
        description="Debian 13 (Trixie) distribution upgrade orchestration engine.",
    )

    subparsers = parser.add_subparsers(dest="subaction", help="Upgrade subcommands")

    # check
    subparsers.add_parser("check", help="Run Phase 0 pre-flight checks")

    # dry-run
    subparsers.add_parser("dry-run", help="Simulate upgrade pipeline without system changes")

    # start
    start_p = subparsers.add_parser("start", help="Execute live distribution upgrade")
    start_p.add_argument("--non-interactive", action="store_true", help="Run non-interactively without prompt")
    start_p.add_argument("--allow-unattached", action="store_true", help="Allow running outside tmux session")

    # verify
    subparsers.add_parser("verify", help="Run Phase 5 hardware & systemd verification")

    # rebuild-venv
    rebuild_p = subparsers.add_parser("rebuild-venv", help="Rebuild Python virtualenv post-upgrade")
    rebuild_p.add_argument("--target-dir", help="Custom virtualenv path override")

    if not args:
        parser.print_help()
        return 0

    parsed_args, unknown = parser.parse_known_args(args)
    script_path = get_upgrade_script_path()

    if parsed_args.subaction == "rebuild-venv":
        return rebuild_virtualenv(getattr(parsed_args, "target_dir", None))

    if not script_path.is_file():
        print(f"[ERROR] Engine script not found at {script_path}", file=sys.stderr)
        return 1

    cmd = [str(script_path)]

    if parsed_args.subaction == "check":
        cmd.append("--check")
    elif parsed_args.subaction == "dry-run":
        cmd.append("--dry-run")
    elif parsed_args.subaction == "verify":
        cmd.append("--verify")
    elif parsed_args.subaction == "start":
        in_tmux = bool(os.environ.get("TMUX") or os.environ.get("STY"))
        if not in_tmux and not parsed_args.allow_unattached:
            if ensure_tmux_installed():
                print("[INFO] Not in tmux session. Automatically launching inside tmux 'osm-trixie-upgrade'...")
                tmux_cmd = ["tmux", "new-session", "-s", "osm-trixie-upgrade", str(script_path), "--apply"]
                if parsed_args.non_interactive:
                    tmux_cmd.append("--non-interactive")
                return subprocess.run(tmux_cmd).returncode
            else:
                print("[ERROR] Cannot proceed without tmux or --allow-unattached flag.", file=sys.stderr)
                return 1

        if not parsed_args.non_interactive:
            confirm = input("Are you sure you want to proceed with full distribution upgrade to Debian 13? (yes/no): ")
            if confirm.strip().lower() not in ("yes", "y"):
                print("[INFO] Upgrade cancelled by user.")
                return 0
        cmd.append("--apply")
        if parsed_args.non_interactive:
            cmd.append("--non-interactive")
        if parsed_args.allow_unattached:
            cmd.append("--allow-unattached")
    else:
        parser.print_help()
        return 0

    res = subprocess.run(cmd)
    return res.returncode

"""os_manager/commands/ai_claude.py - On-Demand Claude Code Launcher."""

import os
import shutil
import subprocess
import time

from .ai import check_gateway_health, manage_services


def launch_claude(claude_args: list[str]) -> int:
    """Ensure gateways are active and execute Claude Code CLI."""
    print("=== OS-Manager Claude Code On-Demand Launcher ===")
    
    health = check_gateway_health()
    if not health["headroom"]["online"] or not health["router"]["online"]:
        print("-> AI Gateways are offline. Initializing background services...")
        manage_services("start")
        # Wait up to 5 seconds for health
        for _ in range(5):
            time.sleep(1)
            health = check_gateway_health()
            if health["headroom"]["online"] and health["router"]["online"]:
                break

    if not health["headroom"]["online"]:
        print("[Warning] Headroom proxy is not responding on :8787. Claude will attempt direct connection.")

    claude_bin = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_bin) and not shutil.which("claude"):
        print("[Error] Claude Code CLI binary not found in PATH or ~/.local/bin/claude.")
        return 1

    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:8787"
    
    cmd = [claude_bin] + claude_args
    print(f"-> Executing Claude Code with ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ...")
    
    try:
        proc = subprocess.run(cmd, env=env)
        return proc.returncode
    except Exception as exc:
        print(f"[Error] Failed to execute Claude Code: {exc}")
        return 1

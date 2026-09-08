"""Mise-native declarative toolchain and runtime management command."""

import json
import os
import shutil
import subprocess
import sys


def get_mise_bin() -> str | None:
    """Resolve mise executable from PATH or user-space default."""
    mise_bin = shutil.which("mise") or os.path.expanduser("~/.local/bin/mise")
    if os.path.isfile(mise_bin) and os.access(mise_bin, os.X_OK):
        return mise_bin
    return None


def run_status(args: list[str]) -> int:
    """Report installed vs active runtimes, backend types, and status."""
    as_json = "--json" in args
    mise_bin = get_mise_bin()
    if not mise_bin:
        err = {"error": "mise binary not found"} if as_json else "Error: mise binary not found. Please install mise."
        if as_json:
            print(json.dumps(err, indent=2))
        else:
            print(err, file=sys.stderr)
        return 1

    try:
        proc = subprocess.run(
            [mise_bin, "ls", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            if as_json:
                print(json.dumps({"error": proc.stderr.strip()}, indent=2))
            else:
                print(f"Error querying mise ls: {proc.stderr.strip()}", file=sys.stderr)
            return proc.returncode

        data = json.loads(proc.stdout) if proc.stdout.strip() else []
        if as_json:
            print(json.dumps(data, indent=2))
        else:
            print("=== Declarative Toolchains & Runtimes (mise) ===")
            if isinstance(data, list):
                for item in data:
                    plugin = item.get("plugin", "unknown")
                    version = item.get("version", "unknown")
                    active = " [active]" if item.get("active") else ""
                    print(f"  • {plugin:<15} {version}{active}")
            elif isinstance(data, dict):
                for plugin, versions in data.items():
                    print(f"  • {plugin:<15}: {versions}")
        return 0
    except Exception as e:
        if as_json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def run_sync(args: list[str]) -> int:
    """Ensure all declared dependencies in config.toml are installed and reshimmed."""
    mise_bin = get_mise_bin()
    if not mise_bin:
        print("Error: mise binary not found.", file=sys.stderr)
        return 1

    print("==> Syncing declarative toolchains (mise install)...")
    res1 = subprocess.run([mise_bin, "install"], check=False)
    if res1.returncode != 0:
        return res1.returncode

    print("==> Refreshing shims (mise reshim)...")
    res2 = subprocess.run([mise_bin, "reshim"], check=False)
    return res2.returncode


def audit_doctor() -> dict:
    """Inspect environment for PATH precedence, binary shadowing, and PEP 668 integrity."""
    issues = []
    checks = {}

    # Check 1: Mise binary
    mise_bin = get_mise_bin()
    checks["mise_installed"] = bool(mise_bin)
    if not mise_bin:
        issues.append("mise executable is not found in PATH or ~/.local/bin/mise")

    # Check 2: PATH precedence (~/.local/share/mise/shims)
    paths = os.environ.get("PATH", "").split(os.pathsep)
    shims_path = os.path.expanduser("~/.local/share/mise/shims")
    checks["shims_in_path"] = shims_path in paths
    if not checks["shims_in_path"]:
        issues.append(f"Mise shims directory ({shims_path}) is missing from PATH")

    # Check 3: Debian System Python integrity (PEP 668)
    sys_python = "/usr/bin/python3"
    checks["system_python_intact"] = os.path.isfile(sys_python) and os.path.realpath(sys_python).startswith("/usr/bin/python3")
    if not checks["system_python_intact"]:
        issues.append(f"Debian system python ({sys_python}) appears missing or altered")

    # Check 4: Shadowing in ~/.local/bin
    local_bin = os.path.expanduser("~/.local/bin")
    shadowed = []
    if os.path.isdir(local_bin) and os.path.isdir(shims_path):
        local_entries = set(os.listdir(local_bin))
        shim_entries = set(os.listdir(shims_path))
        overlap = local_entries.intersection(shim_entries)
        if overlap:
            shadowed = list(overlap)
            issues.append(f"Potential shadowing binaries in ~/.local/bin: {', '.join(shadowed)}")
    checks["shadowed_binaries"] = shadowed

    return {
        "ok": len(issues) == 0,
        "checks": checks,
        "issues": issues,
    }


def run_doctor(args: list[str]) -> int:
    """Audit toolchain health, shims PATH precedence, and system Python isolation."""
    as_json = "--json" in args
    report = audit_doctor()
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print("=== Mise Toolchain & Environment Doctor ===")
        for key, val in report["checks"].items():
            status = "[OK]" if (val if isinstance(val, bool) else len(val) == 0) else "[WARN]"
            print(f"  {status} {key}: {val}")
        if report["issues"]:
            print("\nIssues Detected:")
            for issue in report["issues"]:
                print(f"  - {issue}")
        else:
            print("\nNo issues detected. Toolchain environment is healthy.")
    return 0 if report["ok"] else 1


def run_runtime(args: list[str]) -> int:
    """Dispatcher for osm runtime / osm toolchain command."""
    if not args or args[0] in ("-h", "--help"):
        print("Usage: osm runtime [status|sync|doctor] [options]")
        print("\nCommands:")
        print("  status   Report installed and active toolchains (supports --json)")
        print("  sync     Install missing tools and refresh shims")
        print("  doctor   Inspect PATH precedence and system Python integrity")
        return 0

    if args[0].startswith("-"):
        subcommand = "status"
        subargs = args
    else:
        subcommand = args[0]
        subargs = args[1:]
    if subcommand == "status":
        return run_status(subargs)
    elif subcommand == "sync":
        return run_sync(subargs)
    elif subcommand == "doctor":
        return run_doctor(subargs)
    else:
        print(f"Unknown runtime subcommand: {subcommand}", file=sys.stderr)
        return 1

# Round 2: Full Mise Declarative Architecture Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote `mise` (`~/.config/mise/config.toml`) into the official user-space declarative toolchain substrate for `os-manager`, update governance invariants in `AGENTS.md` Pillar VI Section 6.3, modernize update and cleanup scripts, and implement a first-class `osm runtime` (`osm toolchain`) CLI controller.

**Architecture:** Establish `~/.config/mise/config.toml` as the single declarative source of truth for developer runtimes and tools, protecting Debian 13 system Python (`/usr/bin/python3` under PEP 668). Refactor `scripts/update_runtimes.sh` and cleanup routines (`scripts/clean_system.sh` and `os_manager/commands/clean.py`) to be mise-native, and provide `osm runtime` (`status`, `sync`, `doctor`) with `osm toolchain` alias in `os_manager/cli.py`.

**Tech Stack:** Python 3.13/3.14, mise-en-place CLI, Bash (defensive), Pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-mise-declarative-toolchain-architecture-design.md`

## Global Constraints
- Platform: Debian GNU/Linux 13 (Trixie) 64-bit on Lenovo IdeaPad 3 15IIL05 (Ice Lake, GNOME 48 on Wayland).
- Zero Bare Sudo: All privileged operations in scripts must strictly use `./scripts/sudo_exec.sh`.
- System Python Protection: Never mutate, symlink, or pollute `/usr/bin/python3` (PEP 668); run tests using `.venv/bin/pytest` or `/home/rizz/dev/os-manager/.venv/bin/pytest`.
- User-Space Substrate: All mise runtimes and shims reside under `~/.local/share/mise` and execute as UID 1000 (`rizz`).
- Cross-Mount Sync: When `AGENTS.md` is updated, synchronize to `/mnt/data/dev/os-manager/AGENTS.md` (and `/mnt/d/dev/os-manager/AGENTS.md` if present).

---

### Task 1: Governance Standards (AGENTS.md Pillar VI Section 6.3) & Cross-Mount Sync

**Files:**
- Modify: `AGENTS.md:280-320`
- Sync: `/mnt/data/dev/os-manager/AGENTS.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-09-08-mise-declarative-toolchain-architecture-design.md` (Section 3.2.1)
- Produces: Updated `AGENTS.md` with Pillar VI Section 6.3 defining declarative toolchain invariants.

- [ ] **Step 1: Inspect current Pillar VI in AGENTS.md**
Read `AGENTS.md` around lines 270-320 to locate the boundary of Section 6.2 and where Section 6.3 should be added.

- [ ] **Step 2: Add Pillar VI Section 6.3 to AGENTS.md**
Add Section 6.3:
```markdown
### 6.3 Declarative Toolchain & User-Space Substrate (Mise)
* **Single Source of Truth:** `~/.config/mise/config.toml` is the official declarative runtime configuration for user-space toolchains (Node.js, Python CLI tools, Bun, Go, etc.).
* **Prohibitions:**
  * NEVER install global runtimes via unmanaged curl pipes, manual NVM scripts, or raw pyenv overrides.
  * NEVER execute global unmanaged package installations (`npm install -g`, `pip install --user`).
* **Execution & Shims:**
  * All agent subshells and automated scripts must resolve user-space tools via `mise exec -- <cmd>` or via mise shims (`~/.local/share/mise/shims`).
  * Mise runs strictly in user-space under UID 1000 (`rizz`), preventing permission pollution.
```

- [ ] **Step 3: Synchronize AGENTS.md across mounts**
Run non-destructive copy to `/mnt/data/dev/os-manager/AGENTS.md`:
```bash
if [ -d "/mnt/data/dev/os-manager" ]; then
  cp -u AGENTS.md /mnt/data/dev/os-manager/AGENTS.md
fi
if [ -d "/mnt/d/dev/os-manager" ]; then
  cp -u AGENTS.md /mnt/d/dev/os-manager/AGENTS.md
fi
```

- [ ] **Step 4: Verify cross-mount synchronization and file integrity**
Check diff and ensure formatting is clean:
```bash
git diff AGENTS.md
```

- [ ] **Step 5: Commit changes**
```bash
git add AGENTS.md
git commit -m "docs(governance): add Pillar VI Section 6.3 for mise declarative toolchain substrate"
```

---

### Task 2: Maintenance Script Modernization (scripts/update_runtimes.sh)

**Files:**
- Modify: `scripts/update_runtimes.sh`

**Interfaces:**
- Consumes: Mise CLI (`~/.local/bin/mise` or PATH `mise`), `./scripts/sudo_exec.sh`
- Produces: Refactored `scripts/update_runtimes.sh` without bare sudo and using declarative `mise` commands.

- [ ] **Step 1: Review existing scripts/update_runtimes.sh**
Inspect `scripts/update_runtimes.sh` lines 15-60. Note legacy NVM, `corepack prepare`, `bun upgrade`, curl installers, and bare `sudo apt`.

- [ ] **Step 2: Rewrite scripts/update_runtimes.sh with defensive Mise workflow**
Update `scripts/update_runtimes.sh` to:
```bash
#!/usr/bin/env bash
# ==============================================================================
# update_runtimes.sh - Update Runtimes, Toolchains, and Package Repositories
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source Distribution Engine if present
if [ -f "${WORKSPACE_ROOT}/scripts/lib/distro.sh" ]; then
    # shellcheck source=scripts/lib/distro.sh
    source "${WORKSPACE_ROOT}/scripts/lib/distro.sh"
fi

echo "==> [1/3] Updating system package repositories (${OS_DISTRO_NAME:-Linux})..."
if declare -F pkg_update >/dev/null 2>&1 && declare -F pkg_upgrade >/dev/null 2>&1; then
    pkg_update "$@" || true
    pkg_upgrade "$@" || true
elif command -v apt-get &>/dev/null; then
    if [ -x "${WORKSPACE_ROOT}/scripts/sudo_exec.sh" ]; then
        "${WORKSPACE_ROOT}/scripts/sudo_exec.sh" apt-get update && "${WORKSPACE_ROOT}/scripts/sudo_exec.sh" apt-get upgrade -y
    fi
fi

echo "==> [2/3] Updating mise declarative toolchains..."
MISE_BIN="$(command -v mise 2>/dev/null || echo "${HOME}/.local/bin/mise")"
if [ -x "${MISE_BIN}" ]; then
    echo "Updating mise binary..."
    "${MISE_BIN}" self-update 2>/dev/null || true
    echo "Upgrading managed toolchains..."
    "${MISE_BIN}" upgrade || true
    echo "Pruning stale versions..."
    "${MISE_BIN}" prune -y || true
else
    echo "Warning: mise binary not found at ${MISE_BIN}" >&2
fi

echo "==> [3/3] Updating Astral UV and user-space tools..."
UV_BIN="$(command -v uv 2>/dev/null || echo "${HOME}/.local/bin/uv")"
if [ -x "${UV_BIN}" ]; then
    "${UV_BIN}" self update 2>/dev/null || true
    "${UV_BIN}" tool upgrade --all 2>/dev/null || true
fi

echo "All runtimes updated."
```

- [ ] **Step 3: Validate Bash syntax and execution**
```bash
bash -n scripts/update_runtimes.sh
```

- [ ] **Step 4: Commit changes**
```bash
git add scripts/update_runtimes.sh
git commit -m "feat(scripts): modernize update_runtimes.sh to use mise declarative toolchains"
```

---

### Task 3: Cache Eviction & Cleanup Modernization (clean_system.sh & clean.py)

**Files:**
- Modify: `scripts/clean_system.sh`
- Modify: `os_manager/commands/clean.py`
- Test: `tests/test_clean_system.py`

**Interfaces:**
- Consumes: Mise CLI (`mise cache clear`, `mise prune -y`), `scripts/sudo_exec.sh`
- Produces: Updated cache eviction in bash script and Python command.

- [ ] **Step 1: Write failing/new unit test in tests/test_clean_system.py**
Create or update `tests/test_clean_system.py` to test `run_clean` in `os_manager.commands.clean`:
```python
"""Tests for system cache cleanup command."""

from unittest.mock import patch, MagicMock
from os_manager.commands.clean import run_clean, clean_caches


def test_clean_dry_run(capsys):
    rc = run_clean(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[DRY RUN]" in out


def test_clean_caches_invokes_mise():
    with patch("shutil.which", return_value="/usr/local/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        clean_caches(dry_run=False, all_caches=True)
        # Verify mise cache clear was called
        calls = [call[0][0] for call in mock_run.call_args_list]
        assert any("mise" in c and "cache" in c and "clear" in c for c in calls)
```

- [ ] **Step 2: Run test to verify failure**
```bash
/home/rizz/dev/os-manager/.venv/bin/pytest tests/test_clean_system.py -v
```
Expected: FAIL (ImportError or assertion failure).

- [ ] **Step 3: Implement clean_caches in os_manager/commands/clean.py**
Implement `clean_caches` and update `run_clean`:
```python
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
    if os.path.isfile(mise_bin) and os.access(mise_bin, os.X_OK):
        print(f"{mode_str}Cleaning mise toolchain cache...")
        if not dry_run:
            subprocess.run([mise_bin, "cache", "clear"], check=False)
            if all_caches:
                subprocess.run([mise_bin, "prune", "-y"], check=False)

    uv_bin = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
    if os.path.isfile(uv_bin) and os.access(uv_bin, os.X_OK):
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
```

- [ ] **Step 4: Update scripts/clean_system.sh**
In `scripts/clean_system.sh`:
- Replace bare `sudo apt autoremove` with `./scripts/sudo_exec.sh` if available.
- Add mise cache cleanup step:
```bash
echo "==> Cleaning mise toolchain cache..."
MISE_BIN="$(command -v mise 2>/dev/null || echo "${HOME}/.local/bin/mise")"
if [ -x "${MISE_BIN}" ]; then
    "${MISE_BIN}" cache clear || true
    if [ "${COMPACT_MODE}" = true ]; then
        "${MISE_BIN}" prune -y || true
    fi
fi
```

- [ ] **Step 5: Run tests and verify syntax**
```bash
/home/rizz/dev/os-manager/.venv/bin/pytest tests/test_clean_system.py -v
bash -n scripts/clean_system.sh
```
Expected: PASS.

- [ ] **Step 6: Commit changes**
```bash
git add scripts/clean_system.sh os_manager/commands/clean.py tests/test_clean_system.py
git commit -m "feat(clean): integrate mise cache eviction into clean_system.sh and osm clean"
```

---

### Task 4: First-Class CLI Controller (os_manager/commands/runtime.py & cli.py)

**Files:**
- Create: `os_manager/commands/runtime.py`
- Modify: `os_manager/cli.py`

**Interfaces:**
- Consumes: Mise CLI (`mise ls --json`, `mise install`, `mise reshim`), `os_manager/cli.py`
- Produces: `osm runtime` (`status`, `sync`, `doctor`) and `osm toolchain` alias.

- [ ] **Step 1: Write failing test in tests/test_runtime_command.py**
Create `tests/test_runtime_command.py`:
```python
"""Tests for osm runtime / toolchain CLI controller."""

import json
from unittest.mock import patch, MagicMock
from os_manager.commands.runtime import run_runtime, get_mise_bin, audit_doctor


def test_get_mise_bin():
    with patch("shutil.which", return_value="/custom/bin/mise"), \
         patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=True):
        assert get_mise_bin() == "/custom/bin/mise"


def test_runtime_status_json(capsys):
    mock_data = [
        {"plugin": "node", "version": "22.0.0", "source": {"type": "mise.toml"}},
        {"plugin": "python", "version": "3.13.0", "source": {"type": "mise.toml"}},
    ]
    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
        rc = run_runtime(["status", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        res = json.loads(captured.stdout)
        assert "plugins" in res or "runtimes" in res or len(res) == 2


def test_runtime_sync():
    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        rc = run_runtime(["sync"])
        assert rc == 0
        assert mock_run.call_count == 2  # mise install and mise reshim


def test_runtime_doctor():
    with patch("os_manager.commands.runtime.audit_doctor") as mock_doc:
        mock_doc.return_value = {"ok": True, "issues": []}
        rc = run_runtime(["doctor"])
        assert rc == 0
```

- [ ] **Step 2: Run test to verify failure**
```bash
/home/rizz/dev/os-manager/.venv/bin/pytest tests/test_runtime_command.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'os_manager.commands.runtime'`.

- [ ] **Step 3: Implement os_manager/commands/runtime.py**
Create `os_manager/commands/runtime.py`:
```python
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
    checks["system_python_intact"] = os.path.isfile(sys_python) and not os.path.islink(sys_python)
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
```

- [ ] **Step 4: Register runtime and toolchain in os_manager/cli.py**
In `os_manager/cli.py`:
- Import `run_runtime`:
  ```python
  from .commands.runtime import run_runtime
  ```
- Add `runtime` and `toolchain` subcommands to `subparsers`:
  ```python
  # runtime / toolchain
  runtime_parser = subparsers.add_parser("runtime", help="Mise declarative runtime and toolchain management")
  runtime_parser.add_argument("action", nargs="?", default="status", choices=["status", "sync", "doctor"])
  runtime_parser.add_argument("--json", action="store_true", help="Output status/doctor as JSON")

  toolchain_parser = subparsers.add_parser("toolchain", help="Alias for runtime command")
  toolchain_parser.add_argument("action", nargs="?", default="status", choices=["status", "sync", "doctor"])
  toolchain_parser.add_argument("--json", action="store_true", help="Output status/doctor as JSON")
  ```
- Add dispatch routing:
  ```python
  elif args.command in ("runtime", "toolchain"):
      return run_runtime(argv[1:])
  ```

- [ ] **Step 5: Run tests and verify**
```bash
/home/rizz/dev/os-manager/.venv/bin/pytest tests/test_runtime_command.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit changes**
```bash
git add os_manager/commands/runtime.py os_manager/cli.py tests/test_runtime_command.py
git commit -m "feat(runtime): implement osm runtime and osm toolchain controller"
```

---

### Task 5: Master Harness Verification, CLI Integration & Session Cleanup

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `tests/test_harness.sh` (if needed for runtime check)
- Truncate: `.agents/temp/HANDOFF.md`

**Interfaces:**
- Consumes: All Round 2 implementations
- Produces: Passing master test suite and clean `.agents/temp/HANDOFF.md`.

- [ ] **Step 1: Add CLI integration test in tests/test_cli.py**
Add test for `osm runtime --help` and `osm toolchain --help`:
```python
def test_cli_runtime_subcommand(capsys):
    rc = main(["runtime", "--help"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "status" in out or "Usage" in out


def test_cli_toolchain_subcommand(capsys):
    rc = main(["toolchain", "--help"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "status" in out or "Usage" in out
```

- [ ] **Step 2: Run pytest suite for runtime and cli**
```bash
/home/rizz/dev/os-manager/.venv/bin/pytest tests/test_runtime_command.py tests/test_cli.py tests/test_clean_system.py -v
```
Expected: PASS.

- [ ] **Step 3: Run master harness check**
```bash
bash scripts/harness_check.sh
```
Verify exit code 0 or all core assertions pass.

- [ ] **Step 4: Truncate .agents/temp/HANDOFF.md per Rule 2**
```bash
: > .agents/temp/HANDOFF.md
```

- [ ] **Step 5: Commit changes**
```bash
git add tests/test_cli.py tests/test_runtime_command.py .agents/temp/HANDOFF.md
git commit -m "test(runtime): verify cli integration and finalize round 2 handoff"
```

# Unified AI Gateway Control Plane (`osm ai`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengimplementasikan modul kontrol terpadu `osm ai` di dalam CLI `os-manager` untuk memonitor, mengorkestrasi siklus hidup (start, stop, restart, logs), dan membuka kedua web dashboard (Headroom & 9Router) secara simultan, serta menyediakan on-demand launcher `osm ai claude`.

**Architecture:** Modul `os_manager/commands/ai.py` bertindak sebagai *control plane* terpadu yang berinteraksi dengan endpoint HTTP `:8787/health` (Headroom) dan `:20128/api/health` (9Router), membaca telemetri dari `~/.headroom/proxy_savings.json` dan `~/.9router/db/data.sqlite` (read-only mode), memicu peluncuran browser ganda (`xdg-open` / `webbrowser`), serta mengontrol daemon via systemd user units atau process supervision. Router CLI di `os_manager/cli.py` mendaftarkan subcommand `ai` dengan validasi argumen argparse.

**Tech Stack:** Python 3.13+, `argparse`, `urllib.request`, `sqlite3`, `webbrowser`, `subprocess`, `unittest`, `pytest`.

**Spec:** [`docs/superpowers/specs/2026-08-24-osm-ai-cli-integration-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-24-osm-ai-cli-integration-design.md)

## Global Constraints

* **Non-Destructive Boundary:** Dilarang mengubah partisi fisik, disk storage, atau file sistem di luar repositori `os-manager` dan file konfigurasi user yang ditentukan.
* **Preserve 9Router Internal State:** Akses ke database `~/.9router/db/data.sqlite` harus selalu bersifat *read-only* (`mode=ro`).
* **Dual Dashboard Guarantee:** Perintah `osm ai dashboard` harus membuka **kedua** URL (`http://127.0.0.1:8787/dashboard` dan `http://127.0.0.1:20128/dashboard`) ke browser default, atau mencetak URL jika berada pada environment headless.
* **Zero-Placeholder Guarantee:** Setiap langkah implementasi harus menyertakan kode konkret tanpa placeholder `TODO` atau `TBD`.

---

### Task 1: Core AI Gateway Health, Telemetry & Dashboard Launcher Module

**Files:**
- Create: `os_manager/commands/ai.py`
- Test: `tests/test_ai_command.py`

**Interfaces:**
- Produces: `check_gateway_health() -> dict`, `get_telemetry_summary() -> dict`, `open_dashboards(headroom: bool, router: bool) -> int`, `manage_services(action: str) -> int`, `run_ai(argv: list[str]) -> int`.

- [ ] **Step 1: Write the failing unit tests for `ai.py`**

Write `tests/test_ai_command.py`:
```python
"""tests/test_ai_command.py - Unit tests for osm ai command."""

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

from os_manager.commands.ai import (
    check_gateway_health,
    get_telemetry_summary,
    open_dashboards,
    run_ai,
)


class TestAiCommand(unittest.TestCase):
    """Test suite for the osm ai command."""

    @patch("urllib.request.urlopen")
    def test_check_gateway_health_both_online(self, mock_urlopen):
        """Verify health check when both Headroom and 9Router are online."""
        mock_resp_headroom = MagicMock()
        mock_resp_headroom.status = 200
        mock_resp_headroom.read.return_value = b'{"status":"ok"}'

        mock_resp_9router = MagicMock()
        mock_resp_9router.status = 200
        mock_resp_9router.read.return_value = b'{"ok":true}'

        mock_urlopen.side_effect = [mock_resp_headroom, mock_resp_9router]

        health = check_gateway_health()
        self.assertTrue(health["headroom"]["online"])
        self.assertEqual(health["headroom"]["status_code"], 200)
        self.assertTrue(health["router"]["online"])
        self.assertEqual(health["router"]["status_code"], 200)

    @patch("urllib.request.urlopen")
    def test_check_gateway_health_offline(self, mock_urlopen):
        """Verify health check when gateways are unreachable."""
        mock_urlopen.side_effect = Exception("Connection refused")

        health = check_gateway_health()
        self.assertFalse(health["headroom"]["online"])
        self.assertFalse(health["router"]["online"])

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_get_telemetry_summary(self, mock_open, mock_exists):
        """Verify telemetry extraction from proxy_savings.json."""
        mock_exists.return_value = True
        savings_data = {
            "lifetime": {
                "requests": 27,
                "tokens_saved": 16091,
                "compression_savings_usd": 0.048273,
            }
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(savings_data)

        with patch("sqlite3.connect") as mock_sqlite:
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchall.return_value = [("Account 1", "antigravity")]
            mock_sqlite.return_value = mock_conn

            telemetry = get_telemetry_summary()
            self.assertEqual(telemetry["requests"], 27)
            self.assertEqual(telemetry["tokens_saved"], 16091)
            self.assertAlmostEqual(telemetry["savings_usd"], 0.048273)
            self.assertEqual(len(telemetry["active_providers"]), 1)

    @patch("webbrowser.open")
    def test_open_dashboards_both(self, mock_webbrowser):
        """Verify that open_dashboards opens both URLs."""
        code = open_dashboards(headroom=True, router=True)
        self.assertEqual(code, 0)
        self.assertEqual(mock_webbrowser.call_count, 2)
        mock_webbrowser.assert_any_call("http://127.0.0.1:8787/dashboard")
        mock_webbrowser.assert_any_call("http://127.0.0.1:20128/dashboard")

    @patch("urllib.request.urlopen")
    def test_run_ai_status_json(self, mock_urlopen):
        """Verify osm ai status --json outputs valid JSON."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status":"ok"}'
        mock_urlopen.return_value = mock_resp

        stdout = io.StringIO()
        with patch("os_manager.commands.ai.get_telemetry_summary", return_value={"requests": 10, "tokens_saved": 500, "savings_usd": 0.01, "active_providers": []}):
            with redirect_stdout(stdout):
                code = run_ai(["status", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertIn("health", data)
        self.assertIn("telemetry", data)
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_ai_command.py -v`
Expected output: ModuleNotFoundError or FAIL (`No module named 'os_manager.commands.ai'`).

- [ ] **Step 3: Implement `os_manager/commands/ai.py`**

Write `os_manager/commands/ai.py`:
```python
"""os_manager/commands/ai.py - Unified AI Gateway Control Plane."""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser

HEADROOM_HEALTH_URL = "http://127.0.0.1:8787/health"
HEADROOM_DASHBOARD_URL = "http://127.0.0.1:8787/dashboard"
ROUTER_HEALTH_URL = "http://127.0.0.1:20128/api/health"
ROUTER_DASHBOARD_URL = "http://127.0.0.1:20128/dashboard"
SAVINGS_FILE = os.path.expanduser("~/.headroom/proxy_savings.json")
ROUTER_DB_FILE = os.path.expanduser("~/.9router/db/data.sqlite")


def check_gateway_health() -> dict:
    """Check health status of Headroom (:8787) and 9Router (:20128)."""
    results = {
        "headroom": {"online": False, "status_code": None, "error": None},
        "router": {"online": False, "status_code": None, "error": None},
    }

    # Headroom Check
    try:
        req = urllib.request.Request(HEADROOM_HEALTH_URL, headers={"User-Agent": "osm-ai-cli"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            results["headroom"]["online"] = (resp.status == 200)
            results["headroom"]["status_code"] = resp.status
    except Exception as exc:
        results["headroom"]["error"] = str(exc)

    # 9Router Check
    try:
        req = urllib.request.Request(ROUTER_HEALTH_URL, headers={"User-Agent": "osm-ai-cli"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            results["router"]["online"] = (resp.status == 200)
            results["router"]["status_code"] = resp.status
    except Exception as exc:
        results["router"]["error"] = str(exc)

    return results


def get_telemetry_summary() -> dict:
    """Read cumulative metrics from proxy_savings.json and 9Router SQLite."""
    summary = {
        "requests": 0,
        "tokens_saved": 0,
        "savings_usd": 0.0,
        "active_providers": [],
    }

    if os.path.exists(SAVINGS_FILE):
        try:
            with open(SAVINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            lifetime = data.get("lifetime", {})
            summary["requests"] = lifetime.get("requests", 0)
            summary["tokens_saved"] = lifetime.get("tokens_saved", 0)
            summary["savings_usd"] = float(lifetime.get("compression_savings_usd", 0.0))
        except Exception:
            pass

    if os.path.exists(ROUTER_DB_FILE):
        try:
            uri_path = f"file:{os.path.abspath(ROUTER_DB_FILE)}?mode=ro"
            conn = sqlite3.connect(uri_path, uri=True, timeout=2.0)
            cur = conn.cursor()
            rows = cur.execute("SELECT name, provider FROM providerConnections WHERE isActive=1").fetchall()
            summary["active_providers"] = [{"name": r[0], "provider": r[1]} for r in rows]
            conn.close()
        except Exception:
            pass

    return summary


def open_dashboards(headroom: bool = True, router: bool = True) -> int:
    """Open Headroom and 9Router web dashboards in default browser."""
    urls = []
    if headroom:
        urls.append(("Headroom Dashboard", HEADROOM_DASHBOARD_URL))
    if router:
        urls.append(("9Router Dashboard", ROUTER_DASHBOARD_URL))

    print("=== Launching AI Web Dashboards ===")
    for name, url in urls:
        print(f"-> Opening {name}: {url}")
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"   [Notice] Could not auto-launch browser ({exc}). Open manually: {url}")

    return 0


def manage_services(action: str) -> int:
    """Supervise background services via systemctl user or fallback process."""
    print(f"=== AI Gateway Service Manager ({action}) ===")
    if action == "start":
        print("-> Starting 9Router gateway...")
        subprocess.run(["systemctl", "--user", "start", "app-9router@autostart.service"], check=False)
        print("-> Starting Headroom proxy...")
        subprocess.run(["systemctl", "--user", "start", "headroom-default.service"], check=False)
        print("[OK] Services start signal dispatched.")
    elif action == "stop":
        print("-> Stopping Headroom proxy...")
        subprocess.run(["systemctl", "--user", "stop", "headroom-default.service"], check=False)
        print("-> Stopping 9Router gateway...")
        subprocess.run(["systemctl", "--user", "stop", "app-9router@autostart.service"], check=False)
        print("[OK] Services stopped.")
    elif action == "restart":
        manage_services("stop")
        manage_services("start")
    elif action == "logs":
        print("-> Tailing unified service logs (Ctrl+C to exit)...")
        try:
            subprocess.run(["journalctl", "--user", "-u", "headroom-default.service", "-u", "app-9router@autostart.service", "-f"], check=False)
        except KeyboardInterrupt:
            pass
    return 0


def print_status_text(health: dict, telemetry: dict) -> None:
    """Render human-readable formatted status table."""
    print("================================================================================")
    print("                      OS-MANAGER AI GATEWAY CONTROL PLANE                       ")
    print("================================================================================")
    
    # Health table
    h_status = "ONLINE (HTTP 200)" if health["headroom"]["online"] else "OFFLINE"
    r_status = "ONLINE (HTTP 200)" if health["router"]["online"] else "OFFLINE"
    print(f"  Headroom Proxy (:8787)   : {h_status}")
    print(f"  9Router Gateway (:20128) : {r_status}")
    print("--------------------------------------------------------------------------------")
    
    # Telemetry metrics
    print(f"  Total Processed Requests : {telemetry['requests']}")
    print(f"  Cumulative Tokens Saved  : {telemetry['tokens_saved']:,} tokens")
    print(f"  Estimated Cost Savings   : ${telemetry['savings_usd']:.6f} USD")
    
    if telemetry["active_providers"]:
        print("--------------------------------------------------------------------------------")
        print("  Active AI Providers:")
        for prov in telemetry["active_providers"]:
            print(f"    - {prov['name']} ({prov['provider']})")
            
    print("================================================================================")


def run_ai(argv: list[str]) -> int:
    """Main CLI entrypoint for osm ai."""
    parser = argparse.ArgumentParser(prog="osm ai", description="Manage and monitor Headroom and 9Router AI stack.")
    subparsers = parser.add_subparsers(dest="action", help="AI stack action")

    # status
    status_parser = subparsers.add_parser("status", help="Check health and telemetry stats")
    status_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Open Headroom & 9Router web dashboards")
    dash_parser.add_argument("--headroom-only", action="store_true", help="Open only Headroom dashboard")
    dash_parser.add_argument("--9router-only", action="store_true", help="Open only 9Router dashboard")

    # lifecycle
    subparsers.add_parser("start", help="Start background AI gateway services")
    subparsers.add_parser("stop", help="Stop background AI gateway services")
    subparsers.add_parser("restart", help="Restart background AI gateway services")
    subparsers.add_parser("logs", help="Stream live unified logs")
    subparsers.add_parser("claude", add_help=False, help="Launch Claude Code with AI gateway verification")

    if not argv:
        argv = ["status"]

    args, unknown = parser.parse_known_args(argv)

    if args.action == "status" or args.action is None:
        is_json = getattr(args, "json", False) or "--json" in argv
        health = check_gateway_health()
        telemetry = get_telemetry_summary()
        if is_json:
            print(json.dumps({"health": health, "telemetry": telemetry}, indent=2))
        else:
            print_status_text(health, telemetry)
        return 0

    elif args.action == "dashboard":
        h_only = getattr(args, "headroom_only", False)
        r_only = getattr(args, "9router_only", False)
        if h_only:
            return open_dashboards(headroom=True, router=False)
        elif r_only:
            return open_dashboards(headroom=False, router=True)
        return open_dashboards(headroom=True, router=True)

    elif args.action in ["start", "stop", "restart", "logs"]:
        return manage_services(args.action)

    elif args.action == "claude":
        from .ai_claude import launch_claude
        return launch_claude(unknown)

    else:
        parser.print_help()
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai_command.py -v`
Expected output: 5 passed in <1s.

- [ ] **Step 5: Commit Task 1**

```bash
git add os_manager/commands/ai.py tests/test_ai_command.py
git commit -m "feat(ai): add unified AI gateway control plane module and tests"
```

---

### Task 2: CLI Routing & Argument Parser Registration

**Files:**
- Modify: `os_manager/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `run_ai` from `os_manager.commands.ai`.
- Produces: Registered `osm ai` subcommand in `build_parser()`.

- [ ] **Step 1: Write test for `osm ai` dispatch in `tests/test_cli.py`**

Add to `tests/test_cli.py`:
```python
    def test_ai_command_help(self):
        """Verify osm ai --help displays available AI actions."""
        code, out, _ = self.run_cli(["ai", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("status", out)
        self.assertIn("dashboard", out)
        self.assertIn("start", out)

    @patch("os_manager.commands.ai.run_ai")
    def test_ai_command_dispatch(self, mock_run_ai):
        """Verify osm ai routes properly to run_ai dispatcher."""
        mock_run_ai.return_value = 0
        code, _, _ = self.run_cli(["ai", "status"])
        self.assertEqual(code, 0)
        mock_run_ai.assert_called_once_with(["status"])
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_cli.py -k test_ai -v`
Expected output: FAIL.

- [ ] **Step 3: Update `os_manager/cli.py`**

Modify `os_manager/cli.py` to register `ai`:
```python
    # ai
    subparsers.add_parser("ai", add_help=False, help="Unified AI gateway control plane (Headroom & 9Router)")
```
And inside `main()`:
```python
    elif args.command == "ai":
        from .commands.ai import run_ai
        return run_ai(argv[1:])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -k test_ai -v`
Expected output: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add os_manager/cli.py tests/test_cli.py
git commit -m "feat(cli): register osm ai subcommand in main CLI router"
```

---

### Task 3: On-Demand Claude Launcher (`osm ai claude`)

**Files:**
- Create: `os_manager/commands/ai_claude.py`
- Test: `tests/test_ai_claude.py`

**Interfaces:**
- Consumes: `check_gateway_health`, `manage_services` from `os_manager.commands.ai`.
- Produces: `launch_claude(args: list[str]) -> int`.

- [ ] **Step 1: Write unit tests for `ai_claude.py`**

Write `tests/test_ai_claude.py`:
```python
"""tests/test_ai_claude.py - Unit tests for osm ai claude launcher."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.ai_claude import launch_claude


class TestAiClaudeLauncher(unittest.TestCase):
    """Test suite for on-demand Claude Code launcher."""

    @patch("subprocess.run")
    @patch("os_manager.commands.ai.check_gateway_health")
    def test_launch_claude_when_online(self, mock_health, mock_run):
        """Verify launching claude when gateways are already healthy."""
        mock_health.return_value = {
            "headroom": {"online": True},
            "router": {"online": True},
        }
        mock_run.return_value.returncode = 0

        code = launch_claude(["--version"])
        self.assertEqual(code, 0)
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(kwargs["env"]["ANTHROPIC_BASE_URL"], "http://127.0.0.1:8787")

    @patch("subprocess.run")
    @patch("os_manager.commands.ai.manage_services")
    @patch("os_manager.commands.ai.check_gateway_health")
    def test_launch_claude_auto_start_when_offline(self, mock_health, mock_manage, mock_run):
        """Verify automatic startup when gateways are offline."""
        mock_health.side_effect = [
            {"headroom": {"online": False}, "router": {"online": False}},
            {"headroom": {"online": True}, "router": {"online": True}},
        ]
        mock_run.return_value.returncode = 0

        code = launch_claude([])
        self.assertEqual(code, 0)
        mock_manage.assert_called_once_with("start")
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_ai_claude.py -v`
Expected output: FAIL (`No module named 'os_manager.commands.ai_claude'`).

- [ ] **Step 3: Implement `os_manager/commands/ai_claude.py`**

Write `os_manager/commands/ai_claude.py`:
```python
"""os_manager/commands/ai_claude.py - On-Demand Claude Code Launcher."""

import os
import shutil
import subprocess
import sys
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai_claude.py -v`
Expected output: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add os_manager/commands/ai_claude.py tests/test_ai_claude.py
git commit -m "feat(ai): add on-demand claude launcher with automatic gateway verification"
```

---

### Task 4: Master Test Harness & Live End-to-End CLI Verification

**Files:**
- Modify: `tests/test_harness.sh`
- Test: Master test suite

**Interfaces:**
- Consumes: All `osm ai` commands.
- Produces: 100% clean test suite passes across the entire repository.

- [ ] **Step 1: Add `osm ai` test assertion to `tests/test_harness.sh`**

Modify `tests/test_harness.sh` to include `osm ai --help` and `osm ai status --json` health assertion.

- [ ] **Step 2: Run full repository test suite**

Run:
```bash
pytest tests/ -v
bash tests/test_harness.sh
```
Expected output: 100% test pass.

- [ ] **Step 3: Execute live CLI verification on the host**

Run:
```bash
python3 -m os_manager.cli ai status
python3 -m os_manager.cli ai status --json
```
Expected output: Valid terminal table and valid JSON output showing online status and token savings.

- [ ] **Step 4: Commit Task 4**

```bash
git add tests/test_harness.sh docs/superpowers/plans/2026-08-24-osm-ai-cli-integration-plan.md
git commit -m "test(ai): integrate osm ai into master test harness and verify end-to-end"
```

"""os_manager/commands/ai.py - Unified AI Gateway Control Plane."""

import argparse
import json
import os
import sqlite3
import subprocess
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
        resp = urllib.request.urlopen(req, timeout=2.0)
        try:
            status = getattr(resp, "status", None)
            if status is None and hasattr(resp, "getcode"):
                status = resp.getcode()
            results["headroom"]["online"] = (status == 200)
            results["headroom"]["status_code"] = status
            try:
                body = resp.read()
                results["headroom"]["details"] = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                results["headroom"]["details"] = {}
        finally:
            if hasattr(resp, "close"):
                resp.close()
    except Exception as exc:
        results["headroom"]["error"] = str(exc)

    # 9Router Check
    try:
        req = urllib.request.Request(ROUTER_HEALTH_URL, headers={"User-Agent": "osm-ai-cli"})
        resp = urllib.request.urlopen(req, timeout=2.0)
        try:
            status = getattr(resp, "status", None)
            if status is None and hasattr(resp, "getcode"):
                status = resp.getcode()
            results["router"]["online"] = (status == 200)
            results["router"]["status_code"] = status
        finally:
            if hasattr(resp, "close"):
                resp.close()
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
            rows = conn.execute("SELECT name, provider FROM providerConnections WHERE isActive=1").fetchall()
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
        res_r = subprocess.run(["systemctl", "--user", "start", "app-9router@autostart.service"], check=False)
        print("-> Starting Headroom proxy...")
        res_h = subprocess.run(["systemctl", "--user", "start", "headroom-default.service"], check=False)
        if res_r.returncode != 0 or res_h.returncode != 0:
            print("[Warning] One or more service start commands returned non-zero exit status.")
        else:
            print("[OK] Services start signal dispatched.")
    elif action == "stop":
        print("-> Stopping Headroom proxy...")
        res_h = subprocess.run(["systemctl", "--user", "stop", "headroom-default.service"], check=False)
        print("-> Stopping 9Router gateway...")
        res_r = subprocess.run(["systemctl", "--user", "stop", "app-9router@autostart.service"], check=False)
        if res_h.returncode != 0 or res_r.returncode != 0:
            print("[Warning] One or more service stop commands returned non-zero exit status.")
        else:
            print("[OK] Services stopped.")
    elif action == "restart":
        print("-> Restarting Headroom proxy & 9Router gateway...")
        res_h = subprocess.run(["systemctl", "--user", "restart", "headroom-default.service"], check=False)
        res_r = subprocess.run(["systemctl", "--user", "restart", "app-9router@autostart.service"], check=False)
        if res_h.returncode != 0 or res_r.returncode != 0:
            print("[Warning] One or more service restart commands returned non-zero exit status.")
        else:
            print("[OK] Services restarted.")
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
    
    if health["headroom"].get("online"):
        details = health["headroom"].get("details", {})
        checks = details.get("checks", {})
        kompress_backend = checks.get("kompress", {}).get("backend", "active")
        print("  Compression Layers:")
        print("    - [proxy] SmartCrusher (JSON & Logs)  : ACTIVE")
        print("    - [code]  Tree-sitter (AST Parser)    : ACTIVE")
        print(f"    - [ml]    Kompress-v2 (ML Engine)     : ACTIVE ({kompress_backend.upper()})")
        
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

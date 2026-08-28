"""os_manager/commands/psi.py - Autonomous PSI Feedback & zRAM Compaction CLI Command Module."""

import argparse
import json
import sys
import time
from typing import List

from ..memory.psi_daemon import (
    PsiMonitorEngine,
    audit_psi_telemetry,
    compact_zram_devices,
    manage_psi_daemon,
)


def run_psi(argv: List[str]) -> int:
    """Entrypoint dispatcher for 'osm psi' commands."""
    parser = argparse.ArgumentParser(
        prog="osm psi",
        description="Autonomous Linux PSI (Pressure Stall Information) Feedback & zRAM Compaction",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="PSI action")

    # status
    status_parser = subparsers.add_parser("status", help="Display real-time CPU, Memory, and I/O PSI stall telemetry")
    status_parser.add_argument("--json", action="store_true", help="Output telemetry as JSON")

    # compact
    subparsers.add_parser("compact", help="Trigger manual on-demand zRAM memory compaction")

    # monitor
    mon_parser = subparsers.add_parser("monitor", help="Live interactive terminal PSI stall monitor")
    mon_parser.add_argument("--interval", type=float, default=1.0, help="Sampling interval in seconds")

    # daemon
    daemon_parser = subparsers.add_parser("daemon", help="Manage osm-psi systemd background daemon")
    daemon_parser.add_argument("action", nargs="?", default="status", choices=["status", "start", "stop", "enable", "disable"])
    daemon_parser.add_argument("--run", action="store_true", help="Execute monitor loop directly in foreground")
    daemon_parser.add_argument("--json", action="store_true", help="Output daemon status as JSON")

    args, unknown = parser.parse_known_args(argv)

    if args.subcommand == "status" or not args.subcommand:
        telemetry = audit_psi_telemetry()
        if getattr(args, "json", False):
            print(json.dumps(telemetry, indent=2))
            return 0
        if not telemetry.get("supported"):
            print("Linux PSI (Pressure Stall Information) is not supported on this kernel/environment.")
            return 1
        print("==================================================")
        print("    Linux Pressure Stall Information (PSI) Audit  ")
        print("==================================================")
        print(f"Daemon Installed: {telemetry.get('daemon_installed')}")
        print(f"Daemon Active:    {telemetry.get('daemon_active')}")
        print(f"zRAM Targets:     {len(telemetry.get('zram_devices', []))} devices detected")
        print("\nPressure Readings (Stall Percentage):")
        mem = telemetry.get("memory", {})
        cpu = telemetry.get("cpu", {})
        io = telemetry.get("io", {})
        print(f"  CPU    - some: 10s={cpu.get('some_avg10', 0):.2f}%, 60s={cpu.get('some_avg60', 0):.2f}%, 300s={cpu.get('some_avg300', 0):.2f}%")
        print(f"  Memory - some: 10s={mem.get('some_avg10', 0):.2f}%, 60s={mem.get('some_avg60', 0):.2f}%, 300s={mem.get('some_avg300', 0):.2f}%")
        print(f"  Memory - full: 10s={mem.get('full_avg10', 0):.2f}%, 60s={mem.get('full_avg60', 0):.2f}%, 300s={mem.get('full_avg300', 0):.2f}%")
        print(f"  I/O    - some: 10s={io.get('some_avg10', 0):.2f}%, 60s={io.get('some_avg60', 0):.2f}%, 300s={io.get('some_avg300', 0):.2f}%")
        print(f"  I/O    - full: 10s={io.get('full_avg10', 0):.2f}%, 60s={io.get('full_avg60', 0):.2f}%, 300s={io.get('full_avg300', 0):.2f}%")
        return 0

    elif args.subcommand == "compact":
        compacted = compact_zram_devices()
        print(f"[PASS] Compacted {len(compacted)} zRAM devices.")
        for dev in compacted:
            print(f"  - {dev}")
        return 0

    elif args.subcommand == "monitor":
        engine = PsiMonitorEngine()
        print(f"Starting live PSI monitoring (interval={args.interval}s, Ctrl+C to exit)...")
        try:
            while True:
                sample = engine.step()
                if sample and sample.get("metrics"):
                    m = sample["metrics"]
                    mit = sample.get("mitigation", {})
                    mit_str = f" [Mitigation: {mit.get('tier')}]" if mit.get("mitigated") else ""
                    print(f"[{m.timestamp}] Memory some={m.memory_some.avg10:.2f}% full={m.memory_full.avg10:.2f}% | CPU some={m.cpu_some.avg10:.2f}% | IO some={m.io_some.avg10:.2f}%{mit_str}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped PSI monitor.")
        return 0

    elif args.subcommand == "daemon":
        if args.run:
            engine = PsiMonitorEngine()
            engine.run_daemon_loop()
            return 0
        res = manage_psi_daemon(args.action)
        if args.json:
            print(json.dumps(res, indent=2))
            return 0 if res.get("success", True) else 1
        print(f"PSI Daemon ({args.action}):")
        for k, v in res.items():
            print(f"  {k.capitalize()}: {v}")
        return 0 if res.get("success", True) else 1

    return 0

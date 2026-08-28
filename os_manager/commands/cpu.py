"""os_manager/commands/cpu.py - Heterogeneous CPU Affinity Router CLI Command Module."""

import argparse
import json
import sys
from dataclasses import asdict
from typing import List

from ..cpu import (
    audit_process_affinity,
    detect_cpu_topology,
    execute_with_affinity,
    pin_pid_affinity,
)


def run_cpu(argv: List[str]) -> int:
    """Entrypoint dispatcher for 'osm cpu' commands."""
    parser = argparse.ArgumentParser(
        prog="osm cpu",
        description="Heterogeneous CPU Core Affinity Router & Topology Partitioning",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="CPU action")

    # topology
    topo_parser = subparsers.add_parser("topology", help="Display CPU core topology and P/E partition")
    topo_parser.add_argument("--json", action="store_true", help="Output topology as JSON")

    # audit
    audit_parser = subparsers.add_parser("audit", help="Audit current process or system affinity")
    audit_parser.add_argument("--pid", type=int, default=0, help="Target process PID (default: current)")
    audit_parser.add_argument("--json", action="store_true", help="Output audit as JSON")

    # run
    run_parser = subparsers.add_parser("run", help="Execute command pinned to core partition")
    run_group = run_parser.add_mutually_exclusive_group()
    run_group.add_argument("--p-core", action="store_true", help="Run on Performance Cores (default)")
    run_group.add_argument("--e-core", action="store_true", help="Run on Efficiency Cores")
    run_group.add_argument("--all", action="store_true", help="Run across all cores")
    run_parser.add_argument("command", nargs=argparse.REMAINDER, help="Target command and arguments")

    # pin
    pin_parser = subparsers.add_parser("pin", help="Pin existing PID to core partition")
    pin_parser.add_argument("--pid", type=int, required=True, help="Target process PID")
    pin_group = pin_parser.add_mutually_exclusive_group()
    pin_group.add_argument("--p-core", action="store_true", help="Pin to Performance Cores (default)")
    pin_group.add_argument("--e-core", action="store_true", help="Pin to Efficiency Cores")
    pin_group.add_argument("--all", action="store_true", help="Pin across all cores")
    pin_parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args, unknown = parser.parse_known_args(argv)

    if args.subcommand == "topology":
        topo = detect_cpu_topology()
        if args.json:
            print(json.dumps(asdict(topo), indent=2))
            return 0
        print("==================================================")
        print("         CPU Core Topology & Partition            ")
        print("==================================================")
        print(f"Total Cores: {topo.total_cpus}")
        print(f"Heterogeneous: {'Yes' if topo.is_heterogeneous else 'No'} (via {topo.detection_method})")
        print(f"P-Cores ({len(topo.p_cores)}): {topo.p_core_mask}")
        print(f"E-Cores ({len(topo.e_cores)}): {topo.e_core_mask}")
        print(f"All Cores: {topo.all_cores_mask}")
        print("\nCore Details:")
        for c in topo.cores:
            freq_str = f"{c.max_freq_khz // 1000} MHz" if c.max_freq_khz else "N/A"
            cap_str = f"Cap: {c.capacity}" if c.capacity else ""
            print(f"  CPU {c.cpu_id:2d}: {c.core_type:<12} (Max: {freq_str}) {cap_str}")
        return 0

    elif args.subcommand == "audit":
        audit = audit_process_affinity(pid=args.pid)
        if args.json:
            print(json.dumps(audit, indent=2))
            return 0
        print(f"PID {audit.get('pid')}: Affinity Mask: {audit.get('affinity_mask', 'N/A')} (Cores: {audit.get('affinity_cores', [])})")
        return 0

    elif args.subcommand == "run":
        target = "p-core"
        if args.e_core:
            target = "e-core"
        elif args.all:
            target = "all"
        cmd = args.command
        if unknown:
            cmd = unknown + cmd
        if not cmd:
            print("Error: No command specified to run.", file=sys.stderr)
            return 1
        return execute_with_affinity(cmd, target=target)

    elif args.subcommand == "pin":
        target = "p-core"
        if args.e_core:
            target = "e-core"
        elif args.all:
            target = "all"
        res = pin_pid_affinity(pid=args.pid, target=target)
        if args.json:
            print(json.dumps(res, indent=2))
            return 0 if res.get("success") else 1
        if res.get("success"):
            print(f"[PASS] Pinned PID {args.pid} to {target} (Mask: {res.get('mask')}).")
            return 0
        else:
            print(f"[FAIL] Failed to pin PID {args.pid}: {res.get('error')}", file=sys.stderr)
            return 1

    else:
        parser.print_help()
        return 0

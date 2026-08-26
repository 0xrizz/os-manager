"""Main CLI entrypoint router."""

import argparse
import sys

from . import __version__
from .commands.check import run_check
from .commands.clean import run_clean
from .commands.diag import run_diag
from .commands.hsi import run_hsi
from .commands.init import run_init
from .commands.perf import run_perf
from .commands.service import run_service
from .commands.tune import run_tune
from .commands.upgrade import run_upgrade


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="osm",
        description="Autonomous governance harness and control plane for Claude Code.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize Claude Code harness files")
    init_parser.add_argument("--global", dest="is_global", action="store_true", help="Configure global hooks")
    init_parser.add_argument("--project", help="Target project directory")
    init_parser.add_argument("--dry-run", action="store_true", help="Simulate initialization")

    # check
    check_parser = subparsers.add_parser("check", help="Run master test harness suite")
    check_parser.add_argument("--json", action="store_true", help="Output results as JSON")

    # diag
    diag_parser = subparsers.add_parser("diag", help="Gather system and runtime diagnostics")
    diag_parser.add_argument("--json", action="store_true", help="Output telemetry as JSON")

    # clean
    clean_parser = subparsers.add_parser("clean", help="Evict cached package archives")
    clean_parser.add_argument("--dry-run", action="store_true", help="Simulate cleanup")
    clean_parser.add_argument("--all", action="store_true", help="Clean all caches")

    # perf
    subparsers.add_parser("perf", add_help=False, help="Empirical benchmark engine for storage, CPU, memory, and audio")

    # service
    service_parser = subparsers.add_parser("service", help="Manage background daemons")
    service_parser.add_argument("action", nargs="?", default="status", choices=["status", "start", "stop", "restart"])

    # upgrade
    subparsers.add_parser("upgrade", add_help=False, help="Debian 13 (Trixie) upgrade orchestration engine")

    # tune
    subparsers.add_parser("tune", add_help=False, help="Hardware, system, desktop, and terminal tuning engine")

    # hsi
    subparsers.add_parser("hsi", add_help=False, help="Host Security ID (HSI) hardware & firmware hardening engine")

    # ai
    subparsers.add_parser("ai", add_help=False, help="Unified AI gateway control plane (Headroom & 9Router)")

    # mcp
    subparsers.add_parser("mcp", add_help=False, help="Model Context Protocol (MCP) server engine")

    # gpu
    subparsers.add_parser("gpu", add_help=False, help="Dual-GPU Subsystem Management and Workload Router")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI execution entrypoint."""
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0

    args, unknown = parser.parse_known_args(argv)

    if args.command == "diag":
        return run_diag(argv[1:])
    elif args.command == "clean":
        return run_clean(argv[1:])
    elif args.command == "perf":
        return run_perf(argv[1:])
    elif args.command == "check":
        return run_check(argv[1:])
    elif args.command == "init":
        return run_init(argv[1:])
    elif args.command == "service":
        return run_service(argv[1:])
    elif args.command == "upgrade":
        return run_upgrade(argv[1:])
    elif args.command == "tune":
        return run_tune(argv[1:])
    elif args.command == "hsi":
        from .commands.hsi import run_hsi
        return run_hsi(argv[1:])
    elif args.command == "ai":
        from .commands.ai import run_ai
        return run_ai(argv[1:])
    elif args.command == "mcp":
        from .commands.mcp import run_mcp
        return run_mcp(argv[1:])
    elif args.command == "gpu":
        from .commands.gpu import run_gpu
        return run_gpu(argv[1:])
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

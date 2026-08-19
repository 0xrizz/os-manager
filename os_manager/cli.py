"""Main CLI entrypoint router."""

import argparse
import sys
from typing import Optional, List
from . import __version__
from .commands.diag import run_diag
from .commands.clean import run_clean
from .commands.perf import run_perf
from .commands.check import run_check
from .commands.init import run_init
from .commands.service import run_service


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="osm",
        description="Autonomous governance harness and control plane for Claude Code.",
    )
    parser.add_argument(
        "-v", "--version",
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
    perf_parser = subparsers.add_parser("perf", help="Benchmark filesystem I/O")
    perf_parser.add_argument("--quick", action="store_true", help="Run quick benchmark")
    perf_parser.add_argument("--json", action="store_true", help="Output metrics as JSON")

    # service
    service_parser = subparsers.add_parser("service", help="Manage background daemons")
    service_parser.add_argument("action", nargs="?", default="status", choices=["status", "start", "stop", "restart"])

    return parser


def main(argv: Optional[List[str]] = None) -> int:
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
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

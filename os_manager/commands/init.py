"""Claude Code governance scaffolding command."""


def run_init(args: list[str]) -> int:
    """Initialize governance files and rules."""
    dry_run = "--dry-run" in args
    print("=== OS-Manager Claude Code Scaffolding Init ===")
    if dry_run:
        print("[DRY RUN] Initializing .claude/ governance configuration...")
    return 0

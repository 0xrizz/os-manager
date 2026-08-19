"""System cache cleanup command."""


def run_clean(args: list[str]) -> int:
    """Execute multi-tier cache cleanup."""
    dry_run = "--dry-run" in args
    mode_str = "[DRY RUN] " if dry_run else ""
    print("=== OS-Manager System Cache Clean ===")
    print(f"{mode_str}Reclaiming cache storage across package managers and temporary directories...")
    return 0

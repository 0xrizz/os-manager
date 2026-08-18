# /clean: Safe System Cleanup Command

Perform safe cleanup of package caches, temporary build artifacts, and package manager storage without altering configuration files.

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/clean_system.sh "$@"
```

## Description
Safely reclaims disk space on the ext4 WSL root volume:
- Cleans APT package archives and metadata (`sudo apt-get clean`, `sudo apt-get autoclean`)
- Prunes unreferenced dependencies (`sudo apt-get autoremove --purge -y`)
- Prunes Python UV cache (`uv cache clean`)
- Prunes PNPM store and Bun cache (`pnpm store prune`, `rm -rf ~/.bun/install/cache`)
- Cleans temporary files (`/tmp/*`, `~/.cache/*`)
- Displays before and after disk space delta (`df -h /`)

## Flags & Arguments
- `--dry-run`: Estimates reclaimable disk space without deleting files
- `--all`: Includes aggressive build cache eviction

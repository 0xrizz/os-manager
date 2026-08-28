---
name: clean-system
description: Use when ext4 disk space is low, package caches are bloated, or after intensive development builds requiring APT, UV, PNPM, Bun, and /tmp cache eviction
---

# Safe System Cleanup Skill

Reclaims disk space on the native ext4 WSL root volume by safely removing package caches, unreferenced dependencies, runtime cache stores, and temporary files.

## Trigger Scenarios
- Root volume (`/`) storage exceeding warning thresholds (>80% utilization)
- Bloated APT archive caches following system updates
- Accumulated Python UV package caches or orphaned virtual environments
- Stale PNPM store items, Bun install caches, or lingering `/tmp` artifacts

## Invocation
```bash
${PROJECT_DIR:-.}/scripts/clean_system.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Standard safe cleanup (APT cache/autoremove, UV cache, PNPM/Bun cache, `/tmp` files) |
| `--dry-run` | Inspects and estimates reclaimable disk space without deleting files |
| `--all` | Includes aggressive compiler and build cache eviction |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Authorized cleanup script preserving configuration files and active repositories.

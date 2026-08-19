---
name: wsl-snapshot
description: Use when creating point-in-time backups of the Debian WSL2 environment, exporting disk snapshots to external Windows storage, or verifying backup archive integrity
---

# WSL Snapshot Skill

Generates point-in-time compressed backups, verification hashes, and disaster recovery snapshot procedures for the Debian WSL2 environment.

## Trigger Scenarios
- Pre-maintenance point-in-time snapshot before risky system updates or refactoring
- Exporting full WSL instance state to external Windows host storage (`/mnt/d/wsl_backup`)
- Verifying SHA256 integrity checksums on existing snapshot tarballs
- Retention pruning of older backup archives to reclaim host storage

## Invocation
```bash
${CLAUDE_PROJECT_DIR}/scripts/wsl_snapshot.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Prepares backup directory and outputs Windows PowerShell export/import instructions with timestamped paths |
| `--verify` | Performs SHA256 checksum verification against existing snapshot archives |
| `--prune` | Prunes older snapshots, retaining the last 3 archives |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Authorized disaster recovery helper safely interacting with `/mnt/d/wsl_backup`.

# /snapshot: WSL Disaster Recovery Snapshot Command

Generates point-in-time compressed backups and snapshot verification for the Debian WSL2 environment.

## Invocation
```bash
${PROJECT_DIR:-.}/scripts/wsl_snapshot.sh "$@"
```

## Description
Executes disaster recovery snapshots for state protection:
- Creates timestamped tarball archives of critical user state and configurations
- Stores snapshots in Windows host target (`/mnt/d/wsl_backup` or local backup volume)
- Generates SHA256 integrity checksums for created archives
- Supports snapshot verification and retention management

## Flags & Arguments
- `--verify`: Performs SHA256 checksum verification against existing snapshot archives
- `--prune`: Prunes older snapshots, retaining the last 3 archives

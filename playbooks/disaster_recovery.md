# Playbook: WSL2 Disaster Recovery and Snapshot Restoration

Operational runbook for creating, verifying, and restoring full Debian WSL2 point-in-time snapshots.

## Storage Architecture

- **Snapshot Target**: `/mnt/d/wsl_backup/` (Dedicated NTFS host storage)
- **Archive Format**: Compressed `.tar.gz` with accompanying `.sha256` checksums

---

## Standard Recovery Procedures

### 1. Creating Disaster Recovery Snapshots
Generate a fresh point-in-time archive before major upgrades:

```bash
/home/rizz/dev/os-manager/scripts/wsl_snapshot.sh
```

### 2. Verifying Snapshot Integrity
Verify SHA256 checksums of stored archives:

```bash
/home/rizz/dev/os-manager/scripts/wsl_snapshot.sh --verify
```

### 3. Pruning Outdated Snapshots
Retain only the three most recent archives:

```bash
/home/rizz/dev/os-manager/scripts/wsl_snapshot.sh --prune
```

### 4. Full Distro Restoration Procedure
To restore a snapshot to a new or clean WSL instance from Windows PowerShell:

1. Locate the latest archive in `D:\wsl_backup\`:
   ```powershell
   Get-ChildItem D:\wsl_backup\*.tar.gz | Sort-Object LastWriteTime -Descending | Select-Object -First 1
   ```
2. Import the tarball into a new WSL instance:
   ```powershell
   wsl --import Debian-Restored D:\WSL\Debian-Restored D:\wsl_backup\<snapshot_name>.tar.gz
   ```
3. Set the default user in `/etc/wsl.conf`:
   ```ini
   [user]
   default=rizz
   ```
4. Launch the restored instance:
   ```powershell
   wsl -d Debian-Restored
   ```

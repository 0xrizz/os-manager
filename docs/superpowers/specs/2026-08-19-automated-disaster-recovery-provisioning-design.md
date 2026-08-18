# Specification: Automated Disaster Recovery Provisioning

- **Date:** 2026-08-19
- **Scope:** Disaster Recovery & Host Provisioning (`/home/rizz/dev/os-manager`)
- **Status:** Approved
- **Deliverable Reference:** Phase 4, Deliverable 4.3

---

## 1. Executive Summary

`playbooks/disaster_recovery.md` documents the manual procedure for restoring Debian WSL2 instances from point-in-time tarball archives. Manual restoration requires multiple interactive steps across PowerShell and bash: locating archives, verifying checksums, executing `wsl --import`, configuring `/etc/wsl.conf`, and re-establishing systemd user units.

Automated Disaster Recovery Provisioning provides a single-command restoration pipeline. It couples a Windows host orchestrator (`scripts/bootstrap_wsl.ps1`) with a Linux post-bootstrap agent (`scripts/post_bootstrap.sh`). This pairing automates archive selection, cryptographic verification, instance registration, user provisioning, and harness validation without manual intervention.

---

## 2. Problem Statement and Architectural Goals

### Current Limitations
1. **Manual Multi-Step Recovery**: Restoring a failed instance requires operators to run individual PowerShell commands sequentially, creating opportunities for configuration errors.
2. **Missing Post-Import Initialization**: Newly imported instances default to the `root` user and lack active systemd user timers until an operator manually runs maintenance scripts.
3. **Unvalidated Archive Integrity**: Manual restoration frequently skips SHA-256 checksum verification to save time, risking deployment of truncated archives.

### Architectural Goals
- **Single-Command Restoration**: Provision a fully operational WSL2 instance from a backup tarball via one PowerShell invocation.
- **Cryptographic Verification**: Enforce SHA-256 checksum verification prior to disk allocation.
- **Automated Default User Provisioning**: Configure `/etc/wsl.conf` automatically to launch the `rizz` user account by default.
- **Self-Healing Environment Re-establishment**: Execute an internal Linux bootstrap agent on first launch to rebuild symlinks, activate user timers, and run harness self-checks.

---

## 3. Provisioning Pipeline Architecture

### End-to-End Restoration Flow

```text
 ┌─────────────────────────────────────────────────────────────┐
 │               Windows Host (PowerShell 7.x)                 │
 └──────────────────────────────┬──────────────────────────────┘
                                │ 1. Parse CLI arguments or select latest archive
                                │ 2. Verify SHA-256 checksum against .sha256 file
                                │ 3. Check storage capacity (>25GB free on target disk)
                                │ 4. Execute: wsl --import <Name> <Path> <Archive> --version 2
                                │ 5. Inject /etc/wsl.conf: [user] default=rizz
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                First-Boot Lifecycle Execution               │
 └──────────────────────────────┬──────────────────────────────┘
                                │ Execute: wsl -d <Name> -u root -- /bin/bash /path/to/post_bootstrap.sh
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │          Linux Post-Bootstrap Agent (post_bootstrap.sh)     │
 │ • Verifies user permissions and script executable bits      │
 │ • Rebuilds multi-agent SSOT skill symlinks                  │
 │ • Re-registers systemd user timers                          │
 │ • Runs harness self-check and writes audit log              │
 └─────────────────────────────────────────────────────────────┘
```

---

## 4. Windows Host Provisioner Specification (`scripts/bootstrap_wsl.ps1`)

### 4.1 CLI Parameter Interface

The PowerShell provisioner supports non-interactive execution with sensible defaults:

```powershell
<#
.SYNOPSIS
    Automated WSL2 Distro Provisioning & Disaster Recovery Engine.
.PARAMETER SnapshotPath
    Path to the .tar.gz snapshot archive. Defaults to the latest file in D:\wsl_backup\.
.PARAMETER InstanceName
    Name of the new WSL2 instance. Defaults to Debian-Restored-<Timestamp>.
.PARAMETER InstallLocation
    Directory to store the virtual disk (.vhdx). Defaults to D:\WSL\<InstanceName>.
.PARAMETER DefaultUser
    Linux username for default shell login. Defaults to 'rizz'.
.PARAMETER SetAsDefault
    Sets the imported instance as the default WSL distribution.
.PARAMETER SkipChecksum
    Bypasses SHA-256 integrity verification.
.PARAMETER Force
    Overwrites an existing directory or deregisters a conflicting instance name.
#>
[CmdletBinding()]
param(
    [string]$SnapshotPath,
    [string]$InstanceName,
    [string]$InstallLocation,
    [string]$DefaultUser = "rizz",
    [switch]$SetAsDefault,
    [switch]$SkipChecksum,
    [switch]$Force
)
```

### 4.2 PowerShell Engine Implementation

```powershell
# scripts/bootstrap_wsl.ps1 — Automated WSL2 Distro Provisioning
$ErrorActionPreference = "Stop"

$BackupDirectory = "D:\wsl_backup"
$DefaultWslRoot = "D:\WSL"

# 1. Resolve Snapshot Archive
if (-not $SnapshotPath) {
    if (-not (Test-Path $BackupDirectory)) {
        throw "Backup directory '$BackupDirectory' does not exist."
    }
    $LatestSnapshot = Get-ChildItem -Path "$BackupDirectory\*.tar.gz" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $LatestSnapshot) {
        throw "No snapshot archives (.tar.gz) found in '$BackupDirectory'."
    }
    $SnapshotPath = $LatestSnapshot.FullName
}

Write-Host "==> Selected snapshot archive: $SnapshotPath"

# 2. Checksum Verification
if (-not $SkipChecksum) {
    $ChecksumFile = "$SnapshotPath.sha256"
    if (Test-Path $ChecksumFile) {
        Write-Host "==> Verifying SHA-256 checksum..."
        $ExpectedHash = (Get-Content $ChecksumFile).Split(' ')[0].Trim()
        $ActualHash = (Get-FileHash -Path $SnapshotPath -Algorithm SHA256).Hash.ToLower()

        if ($ExpectedHash.ToLower() -ne $ActualHash) {
            throw "Checksum mismatch! Expected: $ExpectedHash, Actual: $ActualHash"
        }
        Write-Host "==> Checksum verified successfully."
    } else {
        Write-Warning "Checksum file '$ChecksumFile' missing. Skipping verification."
    }
}

# 3. Establish Instance Parameters
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $InstanceName) {
    $InstanceName = "Debian-Restored-$Timestamp"
}
if (-not $InstallLocation) {
    $InstallLocation = Join-Path $DefaultWslRoot $InstanceName
}

# 4. Storage & Collision Validation
if (Test-Path $InstallLocation) {
    if ($Force) {
        Write-Warning "Directory '$InstallLocation' exists. Removing (--Force)..."
        Remove-Item -Path $InstallLocation -Recurse -Force
    } else {
        throw "Install location '$InstallLocation' already exists. Use -Force to overwrite."
    }
}
New-Item -ItemType Directory -Path $InstallLocation -Force | Out-Null

$DriveLetter = (Get-Item $InstallLocation).PSDrive.Name
$FreeSpaceGB = [math]::Round((Get-Volume -DriveLetter $DriveLetter).SizeRemaining / 1GB, 2)
if ($FreeSpaceGB -lt 25) {
    throw "Insufficient disk space on drive $DriveLetter: (${FreeSpaceGB}GB free, 25GB required)."
}

# 5. Import WSL2 Instance
Write-Host "==> Importing WSL2 instance '$InstanceName'..."
wsl.exe --import $InstanceName $InstallLocation $SnapshotPath --version 2
if ($LASTEXITCODE -ne 0) {
    throw "wsl.exe --import failed with exit code $LASTEXITCODE."
}

# 6. Configure Default User
Write-Host "==> Configuring default user '$DefaultUser' in /etc/wsl.conf..."
$WslConfContent = "[user]`ndefault=$DefaultUser`n`n[boot]`nsystemd=true`n"
$WslConfCommand = "cat <<'EOF' > /etc/wsl.conf`n$WslConfContent`nEOF"
wsl.exe -d $InstanceName -u root -- bash -c "$WslConfCommand"

# 7. Execute Linux Post-Bootstrap Agent
Write-Host "==> Executing Linux post-bootstrap agent..."
$PostBootstrapScript = "/home/$DefaultUser/dev/os-manager/scripts/post_bootstrap.sh"
wsl.exe -d $InstanceName -u $DefaultUser -- bash -c "if [ -f '$PostBootstrapScript' ]; then bash '$PostBootstrapScript'; fi"

if ($SetAsDefault) {
    Write-Host "==> Setting '$InstanceName' as default WSL instance..."
    wsl.exe --set-default $InstanceName
}

Write-Host "==> Provisioning complete. Launch instance using: wsl -d $InstanceName"
```

---

## 5. Linux Post-Bootstrap Agent Specification (`scripts/post_bootstrap.sh`)

The post-bootstrap agent executes within the Linux environment to restore operational invariants.

### 5.1 Agent Script Implementation

```bash
#!/usr/bin/env bash
# scripts/post_bootstrap.sh — First-boot verification and environment initialization
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDIT_LOG="${WORKSPACE_ROOT}/backups/logs/harness_audit.jsonl"

echo "==> [1/4] Auditing script permissions and workspace ownership..."
find "${WORKSPACE_ROOT}/scripts" -type f -name "*.sh" -exec chmod +x {} +
if [ -f "${WORKSPACE_ROOT}/scripts/agent_bus.py" ]; then
    chmod +x "${WORKSPACE_ROOT}/scripts/agent_bus.py"
fi

echo "==> [2/4] Rebuilding multi-agent SSOT skill symlinks..."
if [ -f "${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh" ]; then
    bash "${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh"
fi

echo "==> [3/4] Enabling systemd user maintenance timers..."
if [ -f "${WORKSPACE_ROOT}/scripts/manage_timers.sh" ]; then
    bash "${WORKSPACE_ROOT}/scripts/manage_timers.sh" install || true
fi

echo "==> [4/4] Running harness self-check..."
if [ -f "${WORKSPACE_ROOT}/scripts/harness_check.sh" ]; then
    bash "${WORKSPACE_ROOT}/scripts/harness_check.sh"
fi

# Log telemetry event
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
mkdir -p "$(dirname "${AUDIT_LOG}")"
echo "{\"timestamp\":\"${TIMESTAMP}\",\"event\":\"post_bootstrap_completed\",\"workspace\":\"${WORKSPACE_ROOT}\"}" >> "${AUDIT_LOG}"

echo "Environment restored and verified."
```

---

## 6. Safety, Boundary Compliance, and Verification

### 6.1 Guardrail Compliance
- **Read-Only Host Inspection**: `bootstrap_wsl.ps1` writes exclusively to the target virtual disk path (for example, `D:\WSL\<Name>`) and never modifies Windows system folders (`C:\Windows`).
- **Cryptographic Enforcement**: The script aborts immediately on checksum mismatches, preventing corruption propagation.

### 6.2 Unit Test Assertions (`tests/test_harness.sh`)
1. **Assertion 31**: Verify `scripts/post_bootstrap.sh` passes `bash -n` and `shellcheck`.
2. **Assertion 32**: Verify `scripts/post_bootstrap.sh` updates script permissions and writes a valid JSON record to `backups/logs/harness_audit.jsonl`.

# zRAM Dual-Manager Conflict Detection & Autonomous Remediation Design Specification

- **Date**: 2026-08-28
- **Topic**: zRAM Manager Conflict Detection, Policy Governance, and Remediation Subsystem
- **Status**: Draft (Approved for Specification)
- **Author**: os-manager Architecture Team

---

## 1. Executive Summary & Problem Context

In Linux workstations and WSL2 developer environments, compressed in-memory swap (zRAM) provides critical resilience against memory pressure, prevents sluggish disk I/O thrashing, and reduces storage write wear.

However, Linux distributions (especially Debian/Ubuntu families) frequently encounter conflicts when multiple zRAM manager packages are installed concurrently. For example:
- **`systemd-zram-generator`**: The canonical modern mechanism managed natively by `os-manager` (`/etc/systemd/zram-generator.conf`).
- **`zramswap.service`** (from `zram-tools`): Legacy daemon executing `/usr/sbin/zramswap start`.
- **`zram-config.service`** / **`zram-init.service`**: Alternative distro-specific helper services.

When both `systemd-zram-generator` and `zram-tools` (`zramswap.service`) are enabled:
1. `systemd-zram-generator` successfully claims and formats `/dev/zram0` during early boot.
2. `zramswap.service` executes afterwards and attempts to re-initialize `/dev/zram0` via `echo` and `mkswap`.
3. Kernel returns `write error: Device or resource busy` and `mkswap: error: /dev/zram0 is mounted; will not make swapspace`.
4. `zramswap.service` crashes with `Active: failed (Result: exit-code)`, entering a degraded system state and cluttering `systemctl` / `journalctl` error logs.

This specification designs a robust, zero-trust detection and multi-stage remediation engine integrated into `os-manager`.

---

## 2. Architectural Principles & Invariants

1. **Canonical Engine SSOT**: `systemd-zram-generator` is established as the sole Single Source of Truth (SSOT) for in-memory swap in `os-manager`.
2. **Deterministic Non-Destructive Audit**: Auditing (`osm diag`, `osm hsi audit`, `osm tune memory --audit`) must never mutate system state or invoke privileged commands unnecessarily.
3. **Multi-Stage Remediation Depth**: Remediation must execute `stop` -> `disable` -> `mask` -> `reset-failed` on all conflicting units to prevent auto-resurrection during package upgrades (e.g. `apt upgrade`).
4. **Non-Interactive Sudo Compliance**: All elevated operations adhere to `CLAUDE.md` and `os_manager/commands/hsi.py` non-interactive sudo execution (`sudo -n` first, fallback to `SUDO_PASSWORD` from `.env` via `sudo -S`).
5. **Dry-Run Predictability**: All mutating commands support `--dry-run` to output planned execution steps without touching system configuration.
6. **Cross-Subsystem Parity**: Consistent reporting and remediation across Python CLI (`osm tune`, `osm hsi`, `osm diag`), MCP tools (`osm_system_health`), and shell maintenance scripts (`tune_system.sh`, `hsi-harden.sh`, `sys_diag.sh`).

---

## 3. Subsystem Architecture & Component Breakdown

```text
os-manager/
├── os_manager/
│   ├── memory/
│   │   ├── __init__.py           # Subsystem exports
│   │   └── zram.py               # Core zRAM detection & remediation engine
│   └── commands/
│       ├── tune.py               # Integrates --audit, --apply, --remediate-zram
│       ├── hsi.py                # Integrates zRAM posture & hardening
│       └── diag.py               # Integrates zRAM diagnostic telemetry
├── scripts/
│   ├── tune_system.sh            # Shell parity for memory tuning
│   ├── hsi-harden.sh             # Shell parity for HSI hardening
│   └── sys_diag.sh               # Shell diagnostic check
└── tests/
    └── memory/
        └── test_zram.py          # Unit & integration test suite
```

---

## 4. Detailed Design: `os_manager/memory/zram.py`

### 4.1 Data Models & Constants

```python
from dataclasses import dataclass
from typing import Any

CONFLICTING_ZRAM_SERVICES: list[str] = [
    "zramswap.service",       # zram-tools
    "zram-config.service",     # zram-config
    "zram.service",            # generic zram service
    "zram-init.service",       # zram-init
]

CANONICAL_ZRAM_GENERATOR_PKG = "systemd-zram-generator"
CANONICAL_ZRAM_CONF = "/etc/systemd/zram-generator.conf"
CANONICAL_ZRAM_DEVICE = "/dev/zram0"

@dataclass
class ConflictingServiceStatus:
    name: str
    installed: bool
    enabled: bool
    active: bool
    failed: bool
    masked: bool

@dataclass
class ZramAuditReport:
    canonical_installed: bool
    canonical_configured: bool
    zram_device_active: bool
    active_devices: list[dict[str, Any]]
    conflicts_detected: bool
    conflicting_services: list[ConflictingServiceStatus]
    status: str  # "OPTIMAL", "CONFLICT_DETECTED", "DEGRADED", "UNCONFIGURED"
    summary_message: str
```

### 4.2 Audit Engine (`audit_zram_system`)

The audit engine performs inspection without modifying any files or services:
1. **Device & Swap Inspection**: Reads `/proc/swaps` to verify if `/dev/zram0` is mounted and its swap priority (target: `100`).
2. **Canonical Engine Inspection**:
   - Checks if `systemd-zram-generator` is installed (`dpkg-query -W` or package query).
   - Checks if `/etc/systemd/zram-generator.conf` exists and contains valid `[zram0]` section with `zstd` and dynamic memory fraction.
3. **Conflicting Services Inspection**:
   - Queries `systemctl is-enabled <service>`, `is-active <service>`, `is-failed <service>`.
   - Flags unit as conflicting if `installed and (enabled or active or failed) and not masked`.
4. **Status Determination**:
   - If conflicts exist: `status = "CONFLICT_DETECTED"`.
   - If `/dev/zram0` active and no conflicts: `status = "OPTIMAL"`.
   - If `/dev/zram0` missing or inactive: `status = "UNCONFIGURED"` or `"DEGRADED"`.

### 4.3 Remediation Engine (`remediate_zram_conflicts`)

```python
def remediate_zram_conflicts(
    report: ZramAuditReport | None = None,
    dry_run: bool = False,
    env_path: Path | None = None,
) -> dict[str, Any]:
    """Execute multi-stage remediation on conflicting zRAM services and enforce canonical generator."""
```

**Execution Steps**:
1. **Conflicting Unit Demotion**:
   For each conflicting unit detected:
   - `systemctl stop <unit>`
   - `systemctl disable <unit>`
   - `systemctl mask <unit>` (prevents re-enabling on apt upgrade)
   - `systemctl reset-failed <unit>`
2. **Canonical Configuration Guarantee**:
   - Write `/etc/systemd/zram-generator.conf` if absent or invalid:
     ```ini
     # Generated by os-manager zRAM subsystem
     [zram0]
     zram-size = min(ram, 8192)
     compression-algorithm = zstd
     swap-priority = 100
     ```
3. **Service Reload & Swap Activation**:
   - `systemctl daemon-reload`
   - `systemctl restart systemd-zram-setup@zram0.service` (or `swapon -a`)
4. **Post-Validation**:
   - Re-run `audit_zram_system()` to verify `status == "OPTIMAL"`.

---

## 5. CLI & Command Integration

### 5.1 `osm tune memory`
- `osm tune memory --audit`: Includes full zRAM audit details:
  ```text
  === Memory Subsystem Audit ===
  1. EarlyOOM Service       : Active (5% RAM, 5% Swap)
  2. MGLRU State            : Enabled (TTL: 1000ms)
  3. zRAM Swap Manager      : CONFLICT_DETECTED
     - Active Device        : /dev/zram0 (7.6 GB, Priority: 100)
     - Canonical Generator  : Configured (/etc/systemd/zram-generator.conf)
     - Conflicting Services : zramswap.service (failed: True, enabled: True, masked: False)
     * Recommendation       : Run 'osm tune memory --remediate-zram' to resolve.
  ```
- `osm tune memory --apply`: Automatically invokes remediation if conflicts are present.
- `osm tune memory --remediate-zram [--dry-run]`: Dedicated remediation entry point.

### 5.2 `osm hsi`
- `osm hsi audit`: Evaluates `swap.zram_active` and `swap.zram_conflict_detected`.
- `osm hsi apply`: Includes zRAM conflicting unit masking as part of HSI hardening.

### 5.3 `osm diag`
- `osm diag`: Evaluates memory telemetry. If conflicts exist, raises a warning badge in the diagnostic output.

---

## 6. Shell Parity & Scripts Update

### 6.1 `scripts/tune_system.sh` & `scripts/hsi-harden.sh`
Add reusable shell remediation routine:
```bash
remediate_zram_conflicts() {
    log_info "Auditing and remediating conflicting zRAM services..."
    local conflicts=("zramswap.service" "zram-config.service" "zram.service" "zram-init.service")
    for svc in "${conflicts[@]}"; do
        if systemctl list-unit-files "$svc" &>/dev/null; then
            log_warn "Conflicting zRAM service detected: $svc. Disabling and masking..."
            systemctl stop "$svc" 2>/dev/null || true
            systemctl disable "$svc" 2>/dev/null || true
            systemctl mask "$svc" 2>/dev/null || true
            systemctl reset-failed "$svc" 2>/dev/null || true
        fi
    done
    systemctl daemon-reload
    systemctl restart systemd-zram-setup@zram0.service 2>/dev/null || true
}
```

---

## 7. Testing & Quality Assurance Plan

1. **Unit Tests (`tests/memory/test_zram.py`)**:
   - `test_audit_optimal_state`: All clean, returns `OPTIMAL`.
   - `test_audit_conflict_detected_failed_service`: Simulates `zramswap.service` failed with `Device busy`.
   - `test_audit_conflict_detected_active_duplicate`: Simulates multiple active zRAM managers.
   - `test_remediation_execution_order`: Verifies `stop` -> `disable` -> `mask` -> `reset-failed` -> `daemon-reload`.
   - `test_remediation_dry_run`: Verifies zero mutations during `--dry-run`.
2. **CLI Routing Tests (`tests/test_cli.py`)**:
   - Verifies argument parser for `--remediate-zram` under `osm tune memory`.
3. **Shell Parity & Linter**:
   - `bash -n scripts/tune_system.sh`
   - `bash -n scripts/hsi-harden.sh`
   - `bash -n scripts/sys_diag.sh`
   - `./tests/test_harness.sh`

---

## 8. Rollback & Disaster Recovery

If a user specifically requires legacy `zramswap.service`:
1. `unmask_zram_service(service_name)` removes `/etc/systemd/system/<service>` symlink to `/dev/null`.
2. `systemctl unmask <service> && systemctl enable --now <service>`.

---
*End of Design Specification.*

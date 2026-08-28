# zRAM Dual-Manager Conflict Detection & Autonomous Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-trust zRAM conflict detection and autonomous multi-stage remediation subsystem in `os-manager` to resolve race conditions and crashes caused by dual zRAM managers (e.g. `systemd-zram-generator` vs `zram-tools` / `zramswap.service`).

**Architecture:** Implement a dedicated, testable domain module `os_manager/memory/zram.py` as Single Source of Truth (SSOT). Integrate detection and multi-stage remediation (`stop` -> `disable` -> `mask` -> `reset-failed` -> `daemon-reload`) into CLI commands (`osm tune memory`, `osm hsi`, `osm diag`), MCP health tools, and shell parity scripts.

**Tech Stack:** Python 3.11+ (Standard Library `subprocess`, `dataclasses`, `pathlib`, `json`, `argparse`), Bash 5+, Pytest, systemd.

**Spec:** `docs/superpowers/specs/2026-08-28-zram-conflict-remediation-design.md`

## Global Constraints

- Python Standard Library only (`dataclasses`, `subprocess`, `pathlib`, `json`, `typing`) — no third-party runtime dependencies.
- Canonical zRAM Engine: `systemd-zram-generator` is the sole SSOT.
- Non-Interactive Sudo Execution: Adhere strictly to `CLAUDE.md` (`sudo -n` test, fallback to `SUDO_PASSWORD` from `.env` via `sudo -S`).
- Tier 3 Invariant Protection: Never touch `/dev/null` redirection with invalid path constructs; operations must be clean and safe.
- Shell Script Parity: Maintain exact behavioral alignment across Python CLI and shell maintenance scripts (`tune_system.sh`, `hsi-harden.sh`, `sys_diag.sh`).

---

## File Structure & Responsibilities

- **`os_manager/memory/__init__.py`**: Subsystem exports for memory optimization & zRAM management.
- **`os_manager/memory/zram.py`**: Core domain logic containing `CONFLICTING_ZRAM_SERVICES`, dataclasses (`ZramAuditReport`, `ConflictingServiceStatus`), `audit_zram_system()`, `remediate_zram_conflicts()`, and `unmask_zram_service()`.
- **`os_manager/commands/tune.py`**: Integrate zRAM conflict telemetry in `osm tune memory --audit`, auto-remediation in `osm tune memory --apply`, and new dedicated flag `osm tune memory --remediate-zram [--dry-run]`.
- **`os_manager/commands/hsi.py`**: Integrate zRAM conflict checks into `audit_hsi_posture()` and HSI hardening routines.
- **`os_manager/commands/diag.py`**: Display zRAM manager conflict warning badges when detected.
- **`scripts/tune_system.sh`**: Add shell parity remediation routine `remediate_zram_conflicts()`.
- **`scripts/hsi-harden.sh`**: Add multi-stage masking for conflicting zRAM services during HSI hardening.
- **`scripts/sys_diag.sh`**: Add shell diagnostics check for conflicting zRAM services.
- **`tests/memory/test_zram.py`**: Pytest test suite testing audit, conflict detection, remediation sequencing, dry-run, and unmasking.
- **`tests/test_cli.py`**: CLI routing and argument parsing test assertions for `--remediate-zram`.

---

### Task 1: Create `os_manager/memory/zram.py` Data Structures & Audit Engine

**Files:**
- Create: `os_manager/memory/__init__.py`
- Create: `os_manager/memory/zram.py`
- Test: `tests/memory/test_zram.py`

**Interfaces:**
- Produces:
  - `CONFLICTING_ZRAM_SERVICES: list[str]`
  - `ConflictingServiceStatus(name, installed, enabled, active, failed, masked)`
  - `ZramAuditReport(canonical_installed, canonical_configured, zram_device_active, active_devices, conflicts_detected, conflicting_services, status, summary_message)`
  - `audit_zram_system(proc_swaps_path="/proc/swaps", conf_path="/etc/systemd/zram-generator.conf") -> ZramAuditReport`

- [ ] **Step 1: Write failing unit test for `audit_zram_system`**

```python
# tests/memory/test_zram.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from os_manager.memory.zram import (
    audit_zram_system,
    ZramAuditReport,
    CONFLICTING_ZRAM_SERVICES,
)

def test_audit_zram_optimal(tmp_path):
    proc_swaps = tmp_path / "swaps"
    proc_swaps.write_text("Filename Type Size Used Priority\n/dev/zram0 partition 8388604 0 100\n")
    zram_conf = tmp_path / "zram-generator.conf"
    zram_conf.write_text("[zram0]\nzram-size = min(ram, 8192)\ncompression-algorithm = zstd\nswap-priority = 100\n")

    with patch("shutil.which", return_value="/usr/lib/systemd/system-generators/systemd-zram-generator"), \
         patch("subprocess.run") as mock_run:
        # Mock all conflicting services as non-installed or masked
        mock_run.return_value = MagicMock(returncode=1, stdout="masked\n", stderr="")
        report = audit_zram_system(proc_swaps_path=str(proc_swaps), conf_path=str(zram_conf))

        assert isinstance(report, ZramAuditReport)
        assert report.status == "OPTIMAL"
        assert report.zram_device_active is True
        assert report.conflicts_detected is False
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/memory/test_zram.py -v`
Expected: FAIL with ModuleNotFoundError or import error.

- [ ] **Step 3: Implement `os_manager/memory/__init__.py` and `os_manager/memory/zram.py`**

```python
# os_manager/memory/__init__.py
"""Memory management and zRAM optimization subsystem."""
from os_manager.memory.zram import (
    CONFLICTING_ZRAM_SERVICES,
    ConflictingServiceStatus,
    ZramAuditReport,
    audit_zram_system,
    remediate_zram_conflicts,
    unmask_zram_service,
)

__all__ = [
    "CONFLICTING_ZRAM_SERVICES",
    "ConflictingServiceStatus",
    "ZramAuditReport",
    "audit_zram_system",
    "remediate_zram_conflicts",
    "unmask_zram_service",
]
```

```python
# os_manager/memory/zram.py
"""Zero-trust zRAM manager conflict detection and autonomous remediation engine."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
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
    installed: bool = False
    enabled: bool = False
    active: bool = False
    failed: bool = False
    masked: bool = False


@dataclass
class ZramAuditReport:
    canonical_installed: bool = False
    canonical_configured: bool = False
    zram_device_active: bool = False
    active_devices: list[dict[str, Any]] = field(default_factory=list)
    conflicts_detected: bool = False
    conflicting_services: list[ConflictingServiceStatus] = field(default_factory=list)
    status: str = "UNCONFIGURED"  # OPTIMAL, CONFLICT_DETECTED, DEGRADED, UNCONFIGURED
    summary_message: str = ""


def _query_service_status(service_name: str) -> ConflictingServiceStatus:
    """Query systemd state for a single service."""
    status = ConflictingServiceStatus(name=service_name)
    try:
        res_file = subprocess.run(
            ["systemctl", "list-unit-files", service_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if res_file.returncode == 0 and service_name in res_file.stdout:
            status.installed = True
            if "masked" in res_file.stdout:
                status.masked = True
            elif "enabled" in res_file.stdout:
                status.enabled = True

        res_active = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        out_active = res_active.stdout.strip()
        status.active = out_active == "active"
        if out_active == "failed":
            status.failed = True

        res_failed = subprocess.run(
            ["systemctl", "is-failed", service_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if res_failed.stdout.strip() == "failed":
            status.failed = True

    except Exception:
        pass
    return status


def audit_zram_system(
    proc_swaps_path: str = "/proc/swaps",
    conf_path: str = CANONICAL_ZRAM_CONF,
) -> ZramAuditReport:
    """Inspect zRAM devices, canonical generator status, and conflicting services."""
    report = ZramAuditReport()

    # 1. Inspect active swap devices in /proc/swaps
    swaps_node = Path(proc_swaps_path)
    if swaps_node.is_file():
        try:
            lines = swaps_node.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[1:]:
                parts = line.split()
                if not parts:
                    continue
                dev = parts[0]
                dev_type = parts[1] if len(parts) > 1 else ""
                size_kb = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                used_kb = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
                prio = int(parts[4]) if len(parts) > 4 and (parts[4].isdigit() or parts[4].startswith("-")) else 0

                entry = {
                    "device": dev,
                    "type": dev_type,
                    "size_kb": size_kb,
                    "used_kb": used_kb,
                    "priority": prio,
                }
                report.active_devices.append(entry)
                if "zram" in dev:
                    report.zram_device_active = True
        except Exception:
            pass

    # 2. Check canonical generator configuration and package
    cfg_node = Path(conf_path)
    if cfg_node.is_file():
        try:
            content = cfg_node.read_text(encoding="utf-8")
            if "[zram0]" in content:
                report.canonical_configured = True
        except Exception:
            pass

    if (
        shutil.which("systemd-zram-generator")
        or Path("/usr/lib/systemd/system-generators/systemd-zram-generator").is_file()
    ):
        report.canonical_installed = True

    # 3. Check conflicting services
    conflicts: list[ConflictingServiceStatus] = []
    for svc in CONFLICTING_ZRAM_SERVICES:
        svc_status = _query_service_status(svc)
        if svc_status.installed and not svc_status.masked:
            if svc_status.enabled or svc_status.active or svc_status.failed:
                conflicts.append(svc_status)
        elif svc_status.active or svc_status.failed:
            conflicts.append(svc_status)

    report.conflicting_services = conflicts
    report.conflicts_detected = len(conflicts) > 0

    # 4. Synthesize overall status
    if report.conflicts_detected:
        report.status = "CONFLICT_DETECTED"
        svc_names = ", ".join(c.name for c in report.conflicting_services)
        report.summary_message = f"Conflicting zRAM services detected: {svc_names}"
    elif report.zram_device_active and report.canonical_configured:
        report.status = "OPTIMAL"
        report.summary_message = "zRAM configured with systemd-zram-generator and active without conflicts."
    elif report.zram_device_active:
        report.status = "DEGRADED"
        report.summary_message = "zRAM device active but canonical configuration missing."
    else:
        report.status = "UNCONFIGURED"
        report.summary_message = "No active zRAM devices or generator found."

    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/memory/test_zram.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/memory/ tests/memory/test_zram.py
git commit -m "feat(memory): implement zram audit and conflict detection engine"
```

---

### Task 2: Implement Multi-Stage Remediation & Unmask Engine

**Files:**
- Modify: `os_manager/memory/zram.py`
- Test: `tests/memory/test_zram.py`

**Interfaces:**
- Consumes: `ZramAuditReport`, `audit_zram_system()`
- Produces:
  - `remediate_zram_conflicts(report=None, dry_run=False, env_path=None) -> dict[str, Any]`
  - `unmask_zram_service(service_name: str, env_path=None) -> bool`

- [ ] **Step 1: Write failing unit tests for remediation and dry-run**

```python
# tests/memory/test_zram.py (append tests)
def test_remediate_zram_conflicts_dry_run():
    report = ZramAuditReport(
        conflicts_detected=True,
        conflicting_services=[
            ConflictingServiceStatus(name="zramswap.service", installed=True, failed=True)
        ],
    )
    res = remediate_zram_conflicts(report=report, dry_run=True)
    assert res["success"] is True
    assert res["dry_run"] is True
    assert len(res["actions"]) > 0
    assert any("mask zramswap.service" in a for a in res["actions"])

def test_remediate_zram_conflicts_execution():
    report = ZramAuditReport(
        conflicts_detected=True,
        conflicting_services=[
            ConflictingServiceStatus(name="zramswap.service", installed=True, failed=True)
        ],
    )
    with patch("os_manager.commands.hsi.run_privileged_command") as mock_priv, \
         patch("os_manager.memory.zram.audit_zram_system") as mock_audit:
        mock_priv.return_value = MagicMock(returncode=0)
        mock_audit.return_value = ZramAuditReport(status="OPTIMAL", zram_device_active=True)

        res = remediate_zram_conflicts(report=report, dry_run=False)
        assert res["success"] is True
        assert res["dry_run"] is False
        assert mock_priv.call_count >= 4  # stop, disable, mask, reset-failed, daemon-reload
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/memory/test_zram.py -k "test_remediate" -v`
Expected: FAIL (functions not implemented).

- [ ] **Step 3: Implement remediation and unmasking functions**

```python
# In os_manager/memory/zram.py (add implementation)
from os_manager.commands.hsi import run_privileged_command

def generate_canonical_zram_conf(ram_fraction: str = "ram", max_mb: int = 8192) -> str:
    """Generate optimal systemd-zram-generator configuration."""
    return (
        "# Generated by os-manager zRAM subsystem\n"
        "[zram0]\n"
        f"zram-size = min({ram_fraction}, {max_mb})\n"
        "compression-algorithm = zstd\n"
        "swap-priority = 100\n"
    )

def remediate_zram_conflicts(
    report: ZramAuditReport | None = None,
    dry_run: bool = False,
    env_path: Path | None = None,
) -> dict[str, Any]:
    """Execute multi-stage remediation on conflicting zRAM services and enforce canonical generator."""
    if report is None:
        report = audit_zram_system()

    actions: list[str] = []

    # 1. Plan/Execute actions for conflicting services
    for svc in report.conflicting_services:
        actions.append(f"systemctl stop {svc.name}")
        actions.append(f"systemctl disable {svc.name}")
        actions.append(f"systemctl mask {svc.name}")
        actions.append(f"systemctl reset-failed {svc.name}")

    # 2. Plan/Execute canonical config creation if missing
    if not report.canonical_configured:
        actions.append(f"write configuration to {CANONICAL_ZRAM_CONF}")

    actions.append("systemctl daemon-reload")
    actions.append("systemctl restart systemd-zram-setup@zram0.service")

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "actions": actions,
            "initial_status": report.status,
            "message": "Dry-run simulation completed.",
        }

    # Live Execution
    for svc in report.conflicting_services:
        run_privileged_command(["systemctl", "stop", svc.name], env_path=env_path, check=False)
        run_privileged_command(["systemctl", "disable", svc.name], env_path=env_path, check=False)
        run_privileged_command(["systemctl", "mask", svc.name], env_path=env_path, check=False)
        run_privileged_command(["systemctl", "reset-failed", svc.name], env_path=env_path, check=False)

    if not report.canonical_configured:
        conf_content = generate_canonical_zram_conf()
        if os.geteuid() == 0:
            p = Path(CANONICAL_ZRAM_CONF)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(conf_content, encoding="utf-8")
        else:
            run_privileged_command(
                ["tee", CANONICAL_ZRAM_CONF],
                env_path=env_path,
                input=conf_content,
                text=True,
                check=False,
            )

    run_privileged_command(["systemctl", "daemon-reload"], env_path=env_path, check=False)
    run_privileged_command(
        ["systemctl", "restart", "systemd-zram-setup@zram0.service"],
        env_path=env_path,
        check=False,
    )

    post_report = audit_zram_system()
    success = not post_report.conflicts_detected

    return {
        "success": success,
        "dry_run": False,
        "actions": actions,
        "initial_status": report.status,
        "post_status": post_report.status,
        "message": "Remediation executed successfully." if success else "Remediation completed with remaining issues.",
    }


def unmask_zram_service(service_name: str, env_path: Path | None = None) -> bool:
    """Unmask a service for rollback or troubleshooting."""
    res = run_privileged_command(["systemctl", "unmask", service_name], env_path=env_path, check=False)
    return res.returncode == 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/memory/test_zram.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/memory/zram.py tests/memory/test_zram.py
git commit -m "feat(memory): implement multi-stage remediation and unmasking engine"
```

---

### Task 3: Integrate with `osm tune memory` CLI Command

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `tests/test_cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `audit_zram_system()`, `remediate_zram_conflicts()`
- Produces: CLI options `--remediate-zram` and integrated telemetry output.

- [ ] **Step 1: Write failing CLI integration test**

```python
# In tests/test_cli.py (add new test cases)
def test_tune_memory_remediate_zram_dry_run_args():
    from os_manager.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["tune", "memory", "--remediate-zram", "--dry-run"])
    assert args.command == "tune"
    assert args.tune_action == "memory"
    assert args.remediate_zram is True
    assert args.dry_run is True
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_cli.py -k "test_tune_memory_remediate_zram" -v`
Expected: FAIL (unrecognized argument `--remediate-zram`).

- [ ] **Step 3: Update `os_manager/commands/tune.py` argument parser and handlers**

```python
# In os_manager/commands/tune.py
# 1. Import audit_zram_system, remediate_zram_conflicts
from os_manager.memory.zram import audit_zram_system, remediate_zram_conflicts

# 2. Add --remediate-zram to argument parser:
mem_group.add_argument("--remediate-zram", action="store_true", help="Detect and remediate conflicting zRAM managers")

# 3. Update memory handler logic:
# When --audit:
zram_audit = audit_zram_system()
# Print status and conflicts if detected

# When --remediate-zram:
res = remediate_zram_conflicts(dry_run=getattr(parsed, "dry_run", False))
# Output structured actions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_cli.py tests/memory/test_zram.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py tests/test_cli.py
git commit -m "feat(cli): wire zram conflict remediation into osm tune memory"
```

---

### Task 4: Integrate with `osm hsi` and `osm diag`

**Files:**
- Modify: `os_manager/commands/hsi.py`
- Modify: `os_manager/commands/diag.py`
- Test: `tests/platform/test_diag.py` or equivalent

**Interfaces:**
- Consumes: `audit_zram_system()`, `remediate_zram_conflicts()`
- Produces: Enhanced HSI posture report and diagnostic telemetry.

- [ ] **Step 1: Write unit tests for HSI and Diag zRAM conflict telemetry**

```python
# In tests/memory/test_zram.py (or tests/test_hsi.py)
def test_hsi_audit_includes_zram_conflict():
    from os_manager.commands.hsi import audit_hsi_posture
    with patch("os_manager.memory.zram.audit_zram_system") as mock_audit:
        mock_audit.return_value = ZramAuditReport(
            conflicts_detected=True,
            status="CONFLICT_DETECTED",
            zram_device_active=True,
        )
        posture = audit_hsi_posture()
        assert posture["swap"]["zram_conflict_detected"] is True
        assert posture["overall_status"] == "needs_hardening"
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/memory/test_zram.py -k "test_hsi_audit" -v`
Expected: FAIL

- [ ] **Step 3: Update `os_manager/commands/hsi.py` and `os_manager/commands/diag.py`**

In `hsi.py`:
- Use `audit_zram_system()` within `audit_hsi_posture()`.
- If `conflicts_detected` is True, consider `swap["hardened"] = False`.
- In `hsi apply`, invoke `remediate_zram_conflicts()`.

In `diag.py`:
- Add check for `audit_zram_system()` under memory diagnostics. If `status == "CONFLICT_DETECTED"`, format warning alert in stdout and JSON.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/hsi.py os_manager/commands/diag.py tests/
git commit -m "feat(hsi,diag): expose zram conflict telemetry and hardening integration"
```

---

### Task 5: Implement Shell Script Parity & Master Harness Verification

**Files:**
- Modify: `scripts/tune_system.sh`
- Modify: `scripts/hsi-harden.sh`
- Modify: `scripts/sys_diag.sh`
- Test: `./tests/test_harness.sh`

**Interfaces:**
- Parity bash functions: `remediate_zram_conflicts` in shell scripts.

- [ ] **Step 1: Update `scripts/tune_system.sh` and `scripts/hsi-harden.sh`**

Add shell remediation logic:
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

- [ ] **Step 2: Update `scripts/sys_diag.sh`**

Add detection check under swap diagnostic section to flag enabled/active/failed `zramswap.service` or legacy zRAM units.

- [ ] **Step 3: Run syntax validation on all modified shell scripts**

Run: `bash -n scripts/tune_system.sh && bash -n scripts/hsi-harden.sh && bash -n scripts/sys_diag.sh`
Expected: Exit 0 (clean syntax).

- [ ] **Step 4: Run full harness verification**

Run: `./tests/test_harness.sh` and `.venv/bin/pytest tests/`
Expected: 82+ assertions passing, all pytest tests green.

- [ ] **Step 5: Commit**

```bash
git add scripts/ tests/
git commit -m "feat(scripts): add shell parity for zram conflict remediation and verify harness"
```

---

*End of Implementation Plan.*

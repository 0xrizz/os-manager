# System Optimization & Resilience Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an automated, idempotent, resilient, and test-driven system optimization and memory resilience tuning suite for Debian 13 (Trixie), covering in-kernel `ntfs3` storage migration, `earlyoom` memory protection, Lenovo ACPI battery conservation, NVIDIA MX330 D3cold power gating, kernel sysctl tuning, and unified `osm tune` CLI control plane.

**Architecture:** A modular Python 3.13 + Bash subsystem engine (`os_manager/commands/tune.py`, `scripts/tune_system.sh`, `scripts/tune_hardware.sh`) divided into Storage, Memory, Hardware, and Sysctl domains with atomic rollback guardrails, systemd boot persistence (`osm-hardware-tune.service`), and full JSON telemetry.

**Tech Stack:** Python 3.13 (`unittest`, `subprocess`, `argparse`, `pathlib`), Linux Kernel 6.12 (`ntfs3`, `zram`, sysfs, sysctl), systemd (`earlyoom.service`, `fstrim.timer`, `osm-hardware-tune.service`), UFW, PipeWire.

**Spec:** [`docs/superpowers/specs/2026-08-22-system-optimization-tuning-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-22-system-optimization-tuning-design.md)

## Global Constraints

- **INV-01 (Zero Data Loss):** `/dev/nvme0n1p4` (`/mnt/data`) must NEVER be formatted or wiped; `/etc/fstab` changes must maintain automated timestamped backups (`/etc/fstab.bak.<timestamp>`) with auto-fallback to `ntfs-3g`.
- **INV-02 (Strict Idempotency):** All routines must be safe to execute multiple times consecutively without duplicating entries or causing mount drops.
- **INV-03 (Privilege Separation):** System writes (`/etc/fstab`, sysctl, systemd, apt) require root/sudo with automated privilege detection; non-root user dotfiles remain user-owned.
- **INV-04 (Hybrid GPU Decoupling):** Wayland display and VA-API decoding prioritize Intel Iris Plus iGPU; NVIDIA MX330 remains in Runtime D3 Cold (`suspended`) when idle.
- **INV-05 (EarlyOOM Immunity):** `earlyoom` must explicitly protect session-critical processes (`systemd`, `sshd`, `Xorg`, `wayland`, `gnome-shell`, `pipewire`, `wireplumber`, `agy`, `claude`).

---

### Task 1: Storage & I/O Subsystem Engine (`ntfs3` Migration & NVMe TRIM)

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `scripts/tune_system.sh`
- Modify: `tests/test_tune_system.py`

**Interfaces:**
- Produces:
  - `migrate_ntfs_driver(fstab_path: str = "/etc/fstab", mount_point: str = "/mnt/data") -> dict[str, Any]`
  - `audit_ntfs_mount_driver(mount_point: str = "/mnt/data") -> dict[str, Any]`
  - `generate_fstab_ntfs3_entry(current_fstab: str, mount_point: str = "/mnt/data") -> str`

- [ ] **Step 1: Write the failing tests for `ntfs3` fstab migration and audit**

```python
# In tests/test_tune_system.py
def test_generate_fstab_ntfs3_entry_success(self):
    """Verify replacing ntfs-3g with ntfs3 in fstab content."""
    sample_fstab = (
        "UUID=3E01-3117 /boot/efi vfat defaults,noatime 0 2\n"
        "UUID=6C7AB7E37AB7A7EA /mnt/data ntfs-3g defaults,uid=1000,gid=1000,umask=022,nofail 0 0\n"
    )
    updated = generate_fstab_ntfs3_entry(sample_fstab, mount_point="/mnt/data")
    self.assertIn("ntfs3", updated)
    self.assertNotIn("ntfs-3g", updated)
    self.assertIn("UUID=6C7AB7E37AB7A7EA /mnt/data ntfs3 defaults,uid=1000,gid=1000,umask=022,nofail,iocharset=utf8 0 0", updated)

def test_audit_ntfs_mount_driver(self):
    """Verify detection of in-kernel ntfs3 vs ntfs-3g FUSE mount."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ntfs3\n")
        res = audit_ntfs_mount_driver("/mnt/data")
        self.assertEqual(res["driver"], "ntfs3")
        self.assertTrue(res["is_inkernel"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tune_system.py -k "test_generate_fstab_ntfs3_entry_success or test_audit_ntfs_mount_driver" -v`  
Expected: FAIL with `NameError: name 'generate_fstab_ntfs3_entry' is not defined`

- [ ] **Step 3: Implement `generate_fstab_ntfs3_entry`, `audit_ntfs_mount_driver`, and `migrate_ntfs_driver` in `os_manager/commands/tune.py` and `scripts/tune_system.sh`**

```python
# In os_manager/commands/tune.py
def generate_fstab_ntfs3_entry(current_fstab: str, mount_point: str = "/mnt/data") -> str:
    """Replace ntfs-3g FUSE driver with in-kernel ntfs3 driver in fstab content."""
    lines = []
    for line in current_fstab.splitlines():
        if mount_point in line and "ntfs-3g" in line:
            parts = line.split()
            if len(parts) >= 4:
                opts = parts[3]
                if "iocharset=utf8" not in opts:
                    opts = f"{opts},iocharset=utf8"
                line = f"{parts[0]} {parts[1]} ntfs3 {opts} {' '.join(parts[4:])}".strip()
        lines.append(line)
    return "\n".join(lines) + "\n"

def audit_ntfs_mount_driver(mount_point: str = "/mnt/data") -> dict[str, Any]:
    """Audit current mount driver for a given mount point."""
    try:
        res = subprocess.run(
            ["findmnt", "-n", "-o", "FSTYPE", mount_point],
            capture_output=True,
            text=True,
            check=False,
        )
        fstype = res.stdout.strip() if res.returncode == 0 else "unknown"
        return {
            "mount_point": mount_point,
            "driver": fstype,
            "is_inkernel": fstype == "ntfs3",
        }
    except Exception:
        return {"mount_point": mount_point, "driver": "unknown", "is_inkernel": False}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tune_system.py -k "test_generate_fstab_ntfs3_entry_success or test_audit_ntfs_mount_driver" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py scripts/tune_system.sh tests/test_tune_system.py
git commit -m "feat(tune): implement ntfs3 storage migration and mount audit"
```

---

### Task 2: Memory & Resilience Engine (`earlyoom` Protection & Dual-Tier Swap Telemetry)

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `scripts/tune_system.sh`
- Modify: `tests/test_tune_system.py`

**Interfaces:**
- Produces:
  - `generate_earlyoom_config(ram_threshold: int = 5, swap_threshold: int = 5) -> str`
  - `audit_earlyoom_status() -> dict[str, Any]`
  - `audit_dual_tier_swap_status() -> dict[str, Any]`
  - `configure_earlyoom(ram_threshold: int = 5, swap_threshold: int = 5) -> bool`

- [ ] **Step 1: Write failing tests for EarlyOOM configuration and swap telemetry**

```python
# In tests/test_tune_system.py
def test_generate_earlyoom_config(self):
    """Verify EarlyOOM configuration string generation with session whitelist."""
    cfg = generate_earlyoom_config(ram_threshold=5, swap_threshold=5)
    self.assertIn("-m 5", cfg)
    self.assertIn("-s 5", cfg)
    self.assertIn("--avoid", cfg)
    self.assertIn("pipewire", cfg)
    self.assertIn("gnome-shell", cfg)

def test_audit_dual_tier_swap_status(self):
    """Verify detection of ZRAM and swapfile in /proc/swaps."""
    mock_swaps = (
        "Filename\tType\tSize\tUsed\tPriority\n"
        "/swapfile file\t8388604\t514964\t-2\n"
        "/dev/zram0 partition\t3841940\t1543188\t100\n"
    )
    with patch("pathlib.Path.read_text", return_value=mock_swaps):
        res = audit_dual_tier_swap_status(proc_swaps_path="/proc/swaps")
        self.assertTrue(res["has_zram"])
        self.assertTrue(res["has_swapfile"])
        self.assertEqual(res["zram_priority"], 100)
        self.assertEqual(res["swapfile_priority"], -2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tune_system.py -k "test_generate_earlyoom_config or test_audit_dual_tier_swap_status" -v`  
Expected: FAIL with `NameError: name 'generate_earlyoom_config' is not defined`

- [ ] **Step 3: Implement `generate_earlyoom_config`, `audit_earlyoom_status`, and `audit_dual_tier_swap_status`**

```python
# In os_manager/commands/tune.py
def generate_earlyoom_config(ram_threshold: int = 5, swap_threshold: int = 5) -> str:
    """Generate /etc/default/earlyoom configuration with protected processes."""
    avoid_pattern = r"(^|/)(init|systemd|sshd|Xorg|wayland|gnome-shell|pipewire|wireplumber|agy|claude)$"
    return (
        "# /etc/default/earlyoom - Managed by os-manager\n"
        f'EARLYOOM_ARGS="-m {ram_threshold} -s {swap_threshold} -r 60 --avoid \'{avoid_pattern}\'"\n'
    )

def audit_dual_tier_swap_status(proc_swaps_path: str = "/proc/swaps") -> dict[str, Any]:
    """Parse /proc/swaps to verify dual-tier ZRAM + swapfile hierarchy."""
    node = Path(proc_swaps_path)
    if not node.is_file():
        return {"has_zram": False, "has_swapfile": False, "zram_priority": 0, "swapfile_priority": 0}
    content = node.read_text()
    has_zram = False
    has_swapfile = False
    zram_prio = 0
    swap_prio = 0
    for line in content.splitlines():
        if "zram" in line:
            has_zram = True
            parts = line.split()
            if len(parts) >= 5:
                zram_prio = int(parts[4])
        elif "swapfile" in line:
            has_swapfile = True
            parts = line.split()
            if len(parts) >= 5:
                swap_prio = int(parts[4])
    return {
        "has_zram": has_zram,
        "has_swapfile": has_swapfile,
        "zram_priority": zram_prio,
        "swapfile_priority": swap_prio,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tune_system.py -k "test_generate_earlyoom_config or test_audit_dual_tier_swap_status" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py scripts/tune_system.sh tests/test_tune_system.py
git commit -m "feat(tune): implement EarlyOOM configuration and dual-tier swap audit"
```

---

### Task 3: Power, Thermals & Boot Persistence Engine

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `scripts/tune_hardware.sh`
- Modify: `tests/test_tune_hardware.py`

**Interfaces:**
- Produces:
  - `generate_hardware_persistence_service() -> str`
  - `generate_hardware_persistence_config(conservation: bool = True, fn_lock: bool = True, gpu_power: str = "auto") -> str`
  - `configure_hardware_persistence(enable: bool = True) -> bool`

- [ ] **Step 1: Write failing tests for hardware persistence config generation**

```python
# In tests/test_tune_hardware.py
def test_generate_hardware_persistence_config(self):
    """Verify hardware persistence configuration file format."""
    cfg = generate_hardware_persistence_config(conservation=True, fn_lock=True, gpu_power="auto")
    self.assertIn("CONSERVATION_MODE=1", cfg)
    self.assertIn("FN_LOCK=1", cfg)
    self.assertIn("GPU_POWER_SAVE=auto", cfg)

def test_generate_hardware_persistence_service(self):
    """Verify systemd service unit definition for hardware persistence."""
    unit = generate_hardware_persistence_service()
    self.assertIn("[Unit]", unit)
    self.assertIn("osm-hardware-tune", unit)
    self.assertIn("ExecStart=", unit)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tune_hardware.py -k "test_generate_hardware_persistence_config or test_generate_hardware_persistence_service" -v`  
Expected: FAIL with `NameError: name 'generate_hardware_persistence_config' is not defined`

- [ ] **Step 3: Implement persistence generators and helpers in `os_manager/commands/tune.py` and `scripts/tune_hardware.sh`**

```python
# In os_manager/commands/tune.py
def generate_hardware_persistence_config(conservation: bool = True, fn_lock: bool = True, gpu_power: str = "auto") -> str:
    """Generate /etc/osm/hardware-tune.conf state configuration."""
    cm_val = "1" if conservation else "0"
    fn_val = "1" if fn_lock else "0"
    return (
        f"CONSERVATION_MODE={cm_val}\n"
        f"FN_LOCK={fn_val}\n"
        f"GPU_POWER_SAVE={gpu_power}\n"
    )

def generate_hardware_persistence_service() -> str:
    """Generate systemd service unit for restoring ACPI & GPU tuning at boot."""
    return (
        "[Unit]\n"
        "Description=os-manager Lenovo Hardware Power & ACPI Tuning Persistence\n"
        "After=multi-user.target\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        "ExecStart=/usr/local/bin/osm tune hardware --apply\n"
        "RemainAfterExit=yes\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tune_hardware.py -k "test_generate_hardware_persistence_config or test_generate_hardware_persistence_service" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py scripts/tune_hardware.sh tests/test_tune_hardware.py
git commit -m "feat(tune): implement hardware persistence configuration and systemd service"
```

---

### Task 4: Unified CLI Routing & Master Telemetry (`osm tune`)

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `os_manager/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `osm tune storage [--apply | --audit]`
  - `osm tune memory [--apply | --audit]`
  - `osm tune hardware [--apply | --audit]`
  - `osm tune system [--apply | --audit]`
  - `osm tune persist [--enable | --disable | --status]`
  - `osm tune all [--apply | --audit | --json]`

- [ ] **Step 1: Write failing tests for new CLI subcommands and JSON telemetry**

```python
# In tests/test_cli.py
def test_cli_tune_storage_audit(self):
    """Verify osm tune storage --audit CLI invocation."""
    res = subprocess.run(["osm", "tune", "storage", "--audit"], capture_output=True, text=True)
    self.assertEqual(res.returncode, 0)
    self.assertIn("Storage", res.stdout)

def test_cli_tune_all_json(self):
    """Verify osm tune all --json output returns valid telemetry payload."""
    res = subprocess.run(["osm", "tune", "all", "--json"], capture_output=True, text=True)
    self.assertEqual(res.returncode, 0)
    import json
    data = json.loads(res.stdout)
    self.assertIn("subsystems", data)
    self.assertIn("storage", data["subsystems"])
    self.assertIn("memory", data["subsystems"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -k "test_cli_tune_storage_audit or test_cli_tune_all_json" -v`  
Expected: FAIL

- [ ] **Step 3: Implement argument routing and JSON payload formatting in `os_manager/commands/tune.py`**

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -k "test_cli_tune_storage_audit or test_cli_tune_all_json" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py os_manager/cli.py tests/test_cli.py
git commit -m "feat(cli): add storage, memory, persist subcommands and json telemetry"
```

---

### Task 5: Live Bare-Metal Execution & Quality Gate Verification

**Files:**
- Execute: `scripts/tune_system.sh`
- Execute: `scripts/tune_hardware.sh`
- Execute: `osm tune all --audit`
- Test: `pytest -v`

- [ ] **Step 1: Run complete test suite**

Run: `pytest tests/test_tune_system.py tests/test_tune_hardware.py tests/test_cli.py -v`  
Expected: All tests PASS with 100% success rate.

- [ ] **Step 2: Apply optimizations to live Debian 13 environment**

Run:
```bash
sudo osm tune system --apply
sudo osm tune memory --apply
sudo osm tune hardware --apply
sudo osm tune persist --enable
```
Expected:
- `/mnt/data` mounted with `ntfs3`
- `earlyoom` active
- Lenovo conservation mode active
- NVIDIA GPU D3cold suspended
- `osm-hardware-tune.service` enabled

- [ ] **Step 3: Run master audit and telemetry check**

Run: `osm tune all --audit`  
Expected: All 5 subsystem audit checks report `[PASS]`.

- [ ] **Step 4: Commit and finalize development state**

```bash
git add -A
git commit -m "chore: complete system optimization and resilience tuning rollout"
```

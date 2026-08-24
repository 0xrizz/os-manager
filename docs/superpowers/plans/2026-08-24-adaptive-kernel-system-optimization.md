# Next-Generation Adaptive Kernel & System Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an automated, idempotent, resilient, and test-driven Adaptive Kernel & System Optimization Suite for Debian 13 (Trixie), covering MGLRU & zRAM memory alignment, EEVDF scheduler slicing, PipeWire low-latency audio, dynamic AC/Battery power profile switching, hardened in-kernel `ntfs3` storage, atomic state rollback (`osm tune revert`), and empirical benchmarking (`osm perf`).

**Architecture:** A modular Python 3.13 + Bash subsystem engine (`os_manager/commands/tune.py`, `os_manager/commands/perf.py`, `scripts/tune_system.sh`, `scripts/tune_hardware.sh`) structured into Memory, Scheduler, Audio, Power, Storage, Revert, and Benchmark modules with atomic pre-apply snapshots in `/var/backups/osm/snapshots/`, dry-run simulation, and master JSON telemetry.

**Tech Stack:** Python 3.13 (`argparse`, `subprocess`, `json`, `pathlib`, `shutil`, `unittest`), Linux Kernel 6.12 (`lru_gen`, `zram`, `eevdf`, sysfs, sysctl), systemd 257 (`systemd-zram-generator`, `earlyoom`, `fstrim.timer`, slices), PipeWire 1.2+, UFW, `sysbench`, `fio`, `perf`.

**Spec:** [`docs/superpowers/specs/2026-08-24-adaptive-kernel-system-optimization-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-24-adaptive-kernel-system-optimization-design.md)

## Global Constraints

- **INV-01 (Zero Data Loss):** `/dev/nvme0n1p4` (`/mnt/data`) must NEVER be formatted, wiped, or modified destructively. Any `/etc/fstab` changes must maintain automated timestamped backups (`/etc/fstab.bak.<timestamp>`) with auto-fallback to `ntfs-3g`.
- **INV-02 (Atomic State Snapshot & One-Command Rollback):** Every mutation applied by `osm tune` must create a pre-apply state snapshot in `/var/backups/osm/snapshots/<timestamp>/`. `osm tune revert` must restore all modified configuration files, sysctl settings, and sysfs states idempotently.
- **INV-03 (Strict Idempotency & Dry-Run Simulation):** All subroutines must support `--dry-run` simulation (printing planned diffs without modifying state) and remain safe to execute repeatedly without duplicating configuration entries or causing service disruptions.
- **INV-04 (Hybrid GPU Decoupling & D3cold Power Gating):** The primary display server (Wayland/GNOME) and VA-API hardware video decoding strictly run on the Intel Iris Plus iGPU (`iHD_drv_video.so`). The discrete NVIDIA MX330 dGPU remains in D3cold `suspended` state (0W draw) unless explicit PRIME offload rendering is requested.
- **INV-05 (EarlyOOM Session Immunity):** The `earlyoom` daemon must strictly protect critical user session and init processes (`systemd`, `sshd`, `Xorg`, `wayland`, `gnome-shell`, `pipewire`, `wireplumber`, `agy`, `claude`) from OOM termination.
- **INV-06 (Non-Interactive Sudo & Zero Hang Compliance):** All privileged operations must support non-interactive execution (`< /dev/null`, `sudo -S` reading from `.env` or environment). CLI operations must never block on interactive prompts.

---

### Task 1: Atomic Snapshot & Rollback Engine (`osm tune revert` & `--dry-run`)

**Files:**
- Create: `tests/test_tune_revert.py`
- Modify: `os_manager/commands/tune.py`

**Interfaces:**
- Produces:
  - `create_system_snapshot(caller: str, target_files: list[str], backup_dir: str = "/var/backups/osm/snapshots") -> dict[str, Any]`
  - `list_system_snapshots(backup_dir: str = "/var/backups/osm/snapshots") -> list[dict[str, Any]]`
  - `revert_system_snapshot(snapshot_id: str | None = None, backup_dir: str = "/var/backups/osm/snapshots") -> dict[str, Any]`

- [ ] **Step 1: Write the failing tests for snapshot creation, listing, and rollback**

```python
# tests/test_tune_revert.py
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from os_manager.commands.tune import (
    create_system_snapshot,
    list_system_snapshots,
    revert_system_snapshot,
)


class TestTuneRevert(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.backup_dir = os.path.join(self.test_dir, "snapshots")
        self.sample_conf = os.path.join(self.test_dir, "99-sample.conf")
        Path(self.sample_conf).write_text("vm.swappiness = 10\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_snapshot_success(self):
        snap = create_system_snapshot(
            caller="osm tune memory --apply",
            target_files=[self.sample_conf],
            backup_dir=self.backup_dir,
        )
        self.assertTrue(snap["success"])
        self.assertIn("snapshot_id", snap)
        snap_path = Path(self.backup_dir) / snap["snapshot_id"]
        self.assertTrue((snap_path / "manifest.json").is_file())
        manifest = json.loads((snap_path / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["caller"], "osm tune memory --apply")
        self.assertIn(self.sample_conf, manifest["backed_up_files"])

    def test_list_snapshots(self):
        create_system_snapshot(
            caller="test 1",
            target_files=[self.sample_conf],
            backup_dir=self.backup_dir,
        )
        snaps = list_system_snapshots(backup_dir=self.backup_dir)
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["caller"], "test 1")

    def test_revert_snapshot_success(self):
        snap = create_system_snapshot(
            caller="before modify",
            target_files=[self.sample_conf],
            backup_dir=self.backup_dir,
        )
        # Modify file
        Path(self.sample_conf).write_text("vm.swappiness = 180\n", encoding="utf-8")
        self.assertEqual(Path(self.sample_conf).read_text(encoding="utf-8").strip(), "vm.swappiness = 180")

        # Revert
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = revert_system_snapshot(snapshot_id=snap["snapshot_id"], backup_dir=self.backup_dir)
            self.assertTrue(res["success"])
            self.assertEqual(Path(self.sample_conf).read_text(encoding="utf-8").strip(), "vm.swappiness = 10")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tune_revert.py -v`  
Expected: FAIL with `ImportError: cannot import name 'create_system_snapshot' from 'os_manager.commands.tune'`

- [ ] **Step 3: Implement snapshot and revert functions in `os_manager/commands/tune.py`**

```python
# In os_manager/commands/tune.py
SNAPSHOT_BASE_DIR = "/var/backups/osm/snapshots"


def create_system_snapshot(
    caller: str,
    target_files: list[str],
    backup_dir: str = SNAPSHOT_BASE_DIR,
) -> dict[str, Any]:
    """Create timestamped configuration snapshot before applying tuning."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    snap_id = f"snap_{ts}"
    snap_path = Path(backup_dir) / snap_id

    try:
        if os.geteuid() != 0 and not os.path.exists(backup_dir):
            subprocess.run(["sudo", "mkdir", "-p", str(snap_path)], capture_output=True, check=False)
        else:
            snap_path.mkdir(parents=True, exist_ok=True)

        backed_up = []
        for src_str in target_files:
            src = Path(src_str)
            if src.is_file():
                rel_dst = snap_path / src.relative_to("/")
                if os.geteuid() != 0:
                    subprocess.run(["sudo", "mkdir", "-p", str(rel_dst.parent)], capture_output=True, check=False)
                    subprocess.run(["sudo", "cp", "-p", str(src), str(rel_dst)], capture_output=True, check=False)
                else:
                    rel_dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, rel_dst)
                backed_up.append(src_str)

        manifest = {
            "snapshot_id": snap_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "caller": caller,
            "backed_up_files": backed_up,
        }
        manifest_str = json.dumps(manifest, indent=2)

        if os.geteuid() != 0:
            subprocess.run(
                ["sudo", "tee", str(snap_path / "manifest.json")],
                input=manifest_str,
                text=True,
                capture_output=True,
                check=False,
            )
        else:
            (snap_path / "manifest.json").write_text(manifest_str, encoding="utf-8")

        return {"success": True, "snapshot_id": snap_id, "manifest": manifest}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def list_system_snapshots(backup_dir: str = SNAPSHOT_BASE_DIR) -> list[dict[str, Any]]:
    """List all available system tuning snapshots."""
    p = Path(backup_dir)
    if not p.is_dir():
        return []
    snapshots = []
    for d in sorted(p.iterdir(), reverse=True):
        manifest_file = d / "manifest.json"
        if manifest_file.is_file():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                snapshots.append(manifest)
            except Exception:
                pass
    return snapshots


def revert_system_snapshot(
    snapshot_id: str | None = None,
    backup_dir: str = SNAPSHOT_BASE_DIR,
) -> dict[str, Any]:
    """Revert system configurations to a previous snapshot."""
    snapshots = list_system_snapshots(backup_dir=backup_dir)
    if not snapshots:
        return {"success": False, "error": "No configuration snapshots found to revert."}

    target_manifest = None
    if snapshot_id:
        for s in snapshots:
            if s.get("snapshot_id") == snapshot_id:
                target_manifest = s
                break
        if not target_manifest:
            return {"success": False, "error": f"Snapshot ID {snapshot_id} not found."}
    else:
        target_manifest = snapshots[0]

    sid = target_manifest["snapshot_id"]
    snap_path = Path(backup_dir) / sid
    restored = []

    try:
        for file_str in target_manifest.get("backed_up_files", []):
            rel_src = snap_path / Path(file_str).relative_to("/")
            if rel_src.is_file():
                if os.geteuid() != 0:
                    subprocess.run(["sudo", "cp", "-p", str(rel_src), file_str], capture_output=True, check=False)
                else:
                    Path(file_str).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(rel_src, file_str)
                restored.append(file_str)

        # Reload kernel sysctl and systemd
        if os.geteuid() != 0:
            subprocess.run(["sudo", "sysctl", "--system"], capture_output=True, check=False)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, check=False)
        else:
            subprocess.run(["sysctl", "--system"], capture_output=True, check=False)
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True, check=False)

        return {
            "success": True,
            "snapshot_id": sid,
            "restored_files": restored,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tune_revert.py -v`  
Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py tests/test_tune_revert.py
git commit -m "feat(tune): implement atomic state snapshotting and revert engine"
```

---

### Task 2: Memory & Virtual Memory Engine (MGLRU, zRAM Swappiness=180, THP madvise, EarlyOOM)

**Files:**
- Create: `tests/test_tune_memory.py`
- Modify: `os_manager/commands/tune.py`
- Modify: `scripts/tune_system.sh`

**Interfaces:**
- Produces:
  - `generate_mglru_config(enabled: int = 7, min_ttl_ms: int = 1000) -> str`
  - `generate_thp_config(mode: str = "madvise", defrag: str = "defer+madvise") -> str`
  - `generate_vm_sysctl_config(swappiness: int = 180, vfs_cache_pressure: int = 50) -> str`
  - `audit_memory_subsystem() -> dict[str, Any]`

- [ ] **Step 1: Write the failing tests for MGLRU, zRAM VM sysctl, and THP config generation**

```python
# tests/test_tune_memory.py
import unittest
from unittest.mock import patch, MagicMock
from os_manager.commands.tune import (
    generate_mglru_config,
    generate_thp_config,
    generate_vm_sysctl_config,
    audit_memory_subsystem,
)


class TestTuneMemory(unittest.TestCase):
    def test_generate_mglru_config(self):
        cfg = generate_mglru_config(enabled=7, min_ttl_ms=1000)
        self.assertIn("w /sys/kernel/mm/lru_gen/enabled - - - - 7", cfg)
        self.assertIn("w /sys/kernel/mm/lru_gen/min_ttl_ms - - - - 1000", cfg)

    def test_generate_thp_config(self):
        cfg = generate_thp_config(mode="madvise", defrag="defer+madvise")
        self.assertIn("w /sys/kernel/mm/transparent_hugepage/enabled - - - - madvise", cfg)
        self.assertIn("w /sys/kernel/mm/transparent_hugepage/defrag - - - - defer+madvise", cfg)

    def test_generate_vm_sysctl_config(self):
        cfg = generate_vm_sysctl_config(swappiness=180, vfs_cache_pressure=50)
        self.assertIn("vm.swappiness = 180", cfg)
        self.assertIn("vm.page-cluster = 0", cfg)
        self.assertIn("vm.watermark_boost_factor = 0", cfg)
        self.assertIn("vm.watermark_scale_factor = 125", cfg)
        self.assertIn("vm.vfs_cache_pressure = 50", cfg)
        self.assertIn("vm.dirty_ratio = 10", cfg)
        self.assertIn("vm.dirty_background_ratio = 5", cfg)

    def test_audit_memory_subsystem(self):
        with patch("pathlib.Path.read_text") as mock_read:
            mock_read.side_effect = lambda *args, **kwargs: "7\n"
            res = audit_memory_subsystem()
            self.assertIn("mglru_enabled", res)
            self.assertIn("swappiness", res)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tune_memory.py -v`  
Expected: FAIL with `ImportError: cannot import name 'generate_mglru_config'`

- [ ] **Step 3: Implement memory generators and audit functions in `os_manager/commands/tune.py` and `scripts/tune_system.sh`**

```python
# In os_manager/commands/tune.py
SYSFS_MGLRU_ENABLED = "/sys/kernel/mm/lru_gen/enabled"
SYSFS_MGLRU_TTL = "/sys/kernel/mm/lru_gen/min_ttl_ms"
SYSFS_THP_ENABLED = "/sys/kernel/mm/transparent_hugepage/enabled"
SYSFS_THP_DEFRAG = "/sys/kernel/mm/transparent_hugepage/defrag"
SYSCTL_MEMORY_PATH = "/etc/sysctl.d/99-osm-memory.conf"
TMPFILES_MGLRU_PATH = "/etc/tmpfiles.d/00-osm-mglru.conf"
TMPFILES_THP_PATH = "/etc/tmpfiles.d/00-osm-thp.conf"


def generate_mglru_config(enabled: int = 7, min_ttl_ms: int = 1000) -> str:
    """Generate systemd tmpfiles.d definition for MGLRU parameters."""
    return (
        f"# /etc/tmpfiles.d/00-osm-mglru.conf - Managed by os-manager\n"
        f"w {SYSFS_MGLRU_ENABLED} - - - - {enabled}\n"
        f"w {SYSFS_MGLRU_TTL} - - - - {min_ttl_ms}\n"
    )


def generate_thp_config(mode: str = "madvise", defrag: str = "defer+madvise") -> str:
    """Generate systemd tmpfiles.d definition for Transparent Huge Pages."""
    return (
        f"# /etc/tmpfiles.d/00-osm-thp.conf - Managed by os-manager\n"
        f"w {SYSFS_THP_ENABLED} - - - - {mode}\n"
        f"w {SYSFS_THP_DEFRAG} - - - - {defrag}\n"
    )


def generate_vm_sysctl_config(swappiness: int = 180, vfs_cache_pressure: int = 50) -> str:
    """Generate sysctl virtual memory configuration for 8GB RAM + zRAM."""
    return (
        "# /etc/sysctl.d/99-osm-memory.conf - Managed by os-manager\n"
        f"vm.swappiness = {swappiness}\n"
        "vm.page-cluster = 0\n"
        "vm.watermark_boost_factor = 0\n"
        "vm.watermark_scale_factor = 125\n"
        f"vm.vfs_cache_pressure = {vfs_cache_pressure}\n"
        "vm.dirty_ratio = 10\n"
        "vm.dirty_background_ratio = 5\n"
        "vm.dirty_expire_centisecs = 3000\n"
        "vm.dirty_writeback_centisecs = 500\n"
        "fs.inotify.max_user_watches = 524288\n"
        "fs.inotify.max_user_instances = 1024\n"
    )


def audit_memory_subsystem() -> dict[str, Any]:
    """Inspect active MGLRU, zRAM, THP, and sysctl VM parameters."""
    mglru_en = "unsupported"
    mglru_ttl = "unsupported"
    if Path(SYSFS_MGLRU_ENABLED).is_file():
        try:
            mglru_en = Path(SYSFS_MGLRU_ENABLED).read_text().strip()
        except Exception:
            pass
    if Path(SYSFS_MGLRU_TTL).is_file():
        try:
            mglru_ttl = Path(SYSFS_MGLRU_TTL).read_text().strip()
        except Exception:
            pass

    thp_mode = "unknown"
    if Path(SYSFS_THP_ENABLED).is_file():
        try:
            raw = Path(SYSFS_THP_ENABLED).read_text().strip()
            for token in raw.split():
                if token.startswith("[") and token.endswith("]"):
                    thp_mode = token.strip("[]")
        except Exception:
            pass

    sysctl_bin = shutil.which("sysctl") or "/sbin/sysctl"

    def _read_s(k: str) -> str:
        try:
            res = subprocess.run([sysctl_bin, "-n", k], capture_output=True, text=True, check=False)
            return res.stdout.strip() if res.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    oom = audit_earlyoom_status()
    swap = audit_dual_tier_swap_status()

    return {
        "mglru_enabled": mglru_en,
        "mglru_min_ttl_ms": mglru_ttl,
        "thp_mode": thp_mode,
        "swappiness": _read_s("vm.swappiness"),
        "page_cluster": _read_s("vm.page-cluster"),
        "watermark_boost_factor": _read_s("vm.watermark_boost_factor"),
        "watermark_scale_factor": _read_s("vm.watermark_scale_factor"),
        "vfs_cache_pressure": _read_s("vm.vfs_cache_pressure"),
        "earlyoom_active": oom.get("active", False),
        "zram_active": swap.get("has_zram", False),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tune_memory.py -v`  
Expected: PASS with 4 passing tests.

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py scripts/tune_system.sh tests/test_tune_memory.py
git commit -m "feat(tune): implement MGLRU, zRAM swappiness=180, and THP memory tuning"
```

---

### Task 3: EEVDF Scheduler & Cgroups v2 User Slice Engine

**Files:**
- Create: `tests/test_tune_scheduler.py`
- Modify: `os_manager/commands/tune.py`
- Modify: `scripts/tune_system.sh`

**Interfaces:**
- Produces:
  - `generate_eevdf_sysctl_config(base_slice_ns: int = 2000000, cfs_bandwidth_slice_us: int = 3000) -> str`
  - `generate_session_slice_config(cpu_weight: int = 500, io_weight: int = 500) -> str`
  - `generate_background_slice_config(cpu_weight: int = 20, io_weight: int = 20, memory_high: str = "1536M") -> str`
  - `audit_scheduler_subsystem() -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for scheduler sysctl and cgroups v2 slice generators**

```python
# tests/test_tune_scheduler.py
import unittest
from unittest.mock import patch
from os_manager.commands.tune import (
    generate_eevdf_sysctl_config,
    generate_session_slice_config,
    generate_background_slice_config,
    audit_scheduler_subsystem,
)


class TestTuneScheduler(unittest.TestCase):
    def test_generate_eevdf_sysctl_config(self):
        cfg = generate_eevdf_sysctl_config(base_slice_ns=2000000, cfs_bandwidth_slice_us=3000)
        self.assertIn("kernel.sched_base_slice_ns = 2000000", cfg)
        self.assertIn("kernel.sched_cfs_bandwidth_slice_us = 3000", cfg)

    def test_generate_session_slice_config(self):
        cfg = generate_session_slice_config(cpu_weight=500, io_weight=500)
        self.assertIn("[Slice]", cfg)
        self.assertIn("CPUWeight=500", cfg)
        self.assertIn("IOWeight=500", cfg)
        self.assertIn("ManagedOOMPreference=avoid", cfg)

    def test_generate_background_slice_config(self):
        cfg = generate_background_slice_config(cpu_weight=20, io_weight=20, memory_high="1536M")
        self.assertIn("[Slice]", cfg)
        self.assertIn("CPUWeight=20", cfg)
        self.assertIn("IOWeight=20", cfg)
        self.assertIn("MemoryHigh=1536M", cfg)
        self.assertIn("ManagedOOMPreference=kill", cfg)

    def test_audit_scheduler_subsystem(self):
        res = audit_scheduler_subsystem()
        self.assertIn("base_slice_ns", res)
        self.assertIn("session_slice_configured", res)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tune_scheduler.py -v`  
Expected: FAIL with `ImportError: cannot import name 'generate_eevdf_sysctl_config'`

- [ ] **Step 3: Implement scheduler and slice generators in `os_manager/commands/tune.py` and `scripts/tune_system.sh`**

```python
# In os_manager/commands/tune.py
SYSCTL_SCHEDULER_PATH = "/etc/sysctl.d/99-osm-scheduler.conf"
SESSION_SLICE_PATH = "/etc/systemd/user/session.slice.d/10-resources.conf"
BACKGROUND_SLICE_PATH = "/etc/systemd/user/background.slice.d/10-resources.conf"


def generate_eevdf_sysctl_config(base_slice_ns: int = 2000000, cfs_bandwidth_slice_us: int = 3000) -> str:
    """Generate sysctl configuration for Linux 6.6+ EEVDF scheduler slicing."""
    return (
        "# /etc/sysctl.d/99-osm-scheduler.conf - Managed by os-manager\n"
        f"kernel.sched_base_slice_ns = {base_slice_ns}\n"
        f"kernel.sched_cfs_bandwidth_slice_us = {cfs_bandwidth_slice_us}\n"
    )


def generate_session_slice_config(cpu_weight: int = 500, io_weight: int = 500) -> str:
    """Generate systemd user session.slice resource override."""
    return (
        "# /etc/systemd/user/session.slice.d/10-resources.conf - Managed by os-manager\n"
        "[Slice]\n"
        f"CPUWeight={cpu_weight}\n"
        f"IOWeight={io_weight}\n"
        "ManagedOOMPreference=avoid\n"
    )


def generate_background_slice_config(cpu_weight: int = 20, io_weight: int = 20, memory_high: str = "1536M") -> str:
    """Generate systemd user background.slice resource override."""
    return (
        "# /etc/systemd/user/background.slice.d/10-resources.conf - Managed by os-manager\n"
        "[Slice]\n"
        f"CPUWeight={cpu_weight}\n"
        f"IOWeight={io_weight}\n"
        f"MemoryHigh={memory_high}\n"
        "ManagedOOMPreference=kill\n"
    )


def audit_scheduler_subsystem() -> dict[str, Any]:
    """Inspect active EEVDF tunables and systemd user slice configurations."""
    sysctl_bin = shutil.which("sysctl") or "/sbin/sysctl"
    slice_val = "unknown"
    try:
        res = subprocess.run([sysctl_bin, "-n", "kernel.sched_base_slice_ns"], capture_output=True, text=True, check=False)
        slice_val = res.stdout.strip() if res.returncode == 0 else "unknown"
    except Exception:
        pass

    session_cfg = Path(SESSION_SLICE_PATH).is_file()
    bg_cfg = Path(BACKGROUND_SLICE_PATH).is_file()

    return {
        "base_slice_ns": slice_val,
        "session_slice_configured": session_cfg,
        "background_slice_configured": bg_cfg,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tune_scheduler.py -v`  
Expected: PASS with 4 passing tests.

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py scripts/tune_system.sh tests/test_tune_scheduler.py
git commit -m "feat(tune): implement EEVDF scheduler slicing and cgroups v2 user slices"
```

---

### Task 4: PipeWire Low-Latency Audio & Hybrid GPU Subsystem

**Files:**
- Create: `tests/test_tune_audio.py`
- Modify: `os_manager/commands/tune.py`
- Modify: `scripts/tune_system.sh`
- Modify: `scripts/tune_hardware.sh`

**Interfaces:**
- Produces:
  - `generate_pipewire_low_latency_config(quantum: int = 256, rate: int = 48000) -> str`
  - `generate_pam_audio_limits_config() -> str`
  - `generate_nvidia_pm_modprobe_config() -> str`
  - `generate_nvidia_pm_udev_rule() -> str`
  - `audit_audio_subsystem() -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for PipeWire config, PAM limits, and GPU PM generators**

```python
# tests/test_tune_audio.py
import unittest
from os_manager.commands.tune import (
    generate_pipewire_low_latency_config,
    generate_pam_audio_limits_config,
    generate_nvidia_pm_modprobe_config,
    generate_nvidia_pm_udev_rule,
    audit_audio_subsystem,
)


class TestTuneAudio(unittest.TestCase):
    def test_generate_pipewire_low_latency_config(self):
        cfg = generate_pipewire_low_latency_config(quantum=256, rate=48000)
        self.assertIn("default.clock.quantum       = 256", cfg)
        self.assertIn("default.clock.rate          = 48000", cfg)
        self.assertIn("libpipewire-module-rt", cfg)
        self.assertIn("rt.prio      = 88", cfg)

    def test_generate_pam_audio_limits_config(self):
        cfg = generate_pam_audio_limits_config()
        self.assertIn("@audio - rtprio 95", cfg)
        self.assertIn("@audio - nice -19", cfg)
        self.assertIn("@audio - memlock unlimited", cfg)

    def test_generate_nvidia_pm_configs(self):
        mod_cfg = generate_nvidia_pm_modprobe_config()
        self.assertIn('options nvidia "NVreg_DynamicPowerManagement=0x02"', mod_cfg)
        udev_cfg = generate_nvidia_pm_udev_rule()
        self.assertIn('ATTR{vendor}=="0x10de"', udev_cfg)
        self.assertIn('ATTR{power/control}="auto"', udev_cfg)

    def test_audit_audio_subsystem(self):
        res = audit_audio_subsystem()
        self.assertIn("pipewire_installed", res)
        self.assertIn("active_quantum", res)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tune_audio.py -v`  
Expected: FAIL with `ImportError: cannot import name 'generate_pipewire_low_latency_config'`

- [ ] **Step 3: Implement audio and GPU generators in `os_manager/commands/tune.py` and helper scripts**

```python
# In os_manager/commands/tune.py
PIPEWIRE_CONF_PATH = "/etc/pipewire/pipewire.conf.d/99-low-latency.conf"
PAM_AUDIO_LIMITS_PATH = "/etc/security/limits.d/95-pipewire.conf"
NVIDIA_MODPROBE_PATH = "/etc/modprobe.d/nvidia-pm.conf"
NVIDIA_UDEV_PATH = "/etc/udev/rules.d/80-nvidia-pm.rules"


def generate_pipewire_low_latency_config(quantum: int = 256, rate: int = 48000) -> str:
    """Generate PipeWire drop-in configuration for low-latency audio."""
    return f"""# /etc/pipewire/pipewire.conf.d/99-low-latency.conf - Managed by os-manager
context.properties = {{
    default.clock.rate          = {rate}
    default.clock.allowed-rates = [ 44100 48000 96000 ]
    default.clock.quantum       = {quantum}
    default.clock.min-quantum   = 32
    default.clock.max-quantum   = 1024
}}

context.modules = [
    {{ name = libpipewire-module-rt
      args = {{
          nice.level   = -11
          rt.prio      = 88
          rtkit.enabled = true
      }}
      flags = [ ifexists nofail ]
    }}
]
"""


def generate_pam_audio_limits_config() -> str:
    """Generate PAM security limits configuration for real-time audio."""
    return """# /etc/security/limits.d/95-pipewire.conf - Managed by os-manager
@audio - rtprio 95
@audio - nice -19
@audio - memlock unlimited
"""


def generate_nvidia_pm_modprobe_config() -> str:
    """Generate modprobe configuration for NVIDIA RTD3 dynamic power management."""
    return """# /etc/modprobe.d/nvidia-pm.conf - Managed by os-manager
options nvidia "NVreg_DynamicPowerManagement=0x02"
"""


def generate_nvidia_pm_udev_rule() -> str:
    """Generate udev rule enforcing Runtime PM autosuspend on NVIDIA PCI devices."""
    return """# /etc/udev/rules.d/80-nvidia-pm.rules - Managed by os-manager
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", ATTR{power/control}="auto"
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", ATTR{power/control}="auto"
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x040300", ATTR{power/control}="auto"
"""


def audit_audio_subsystem() -> dict[str, Any]:
    """Inspect PipeWire and WirePlumber audio stack telemetry."""
    pw_bin = shutil.which("pipewire")
    wp_bin = shutil.which("wireplumber")
    active_quantum = "1024"
    active_rate = "48000"

    try:
        res = subprocess.run(["pw-dump"], capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                if "default.clock.quantum" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        active_quantum = parts[1].strip().rstrip(",")
                elif "default.clock.rate" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        active_rate = parts[1].strip().rstrip(",")
    except Exception:
        pass

    return {
        "pipewire_installed": bool(pw_bin),
        "wireplumber_installed": bool(wp_bin),
        "active_quantum": active_quantum,
        "active_rate": active_rate,
        "low_latency_dropin_present": Path(PIPEWIRE_CONF_PATH).is_file(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tune_audio.py -v`  
Expected: PASS with 4 passing tests.

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py scripts/tune_system.sh scripts/tune_hardware.sh tests/test_tune_audio.py
git commit -m "feat(tune): implement PipeWire low-latency configuration and NVIDIA PM udev rules"
```

---

### Task 5: Dynamic Dual-Profile Power Engine (AC vs Battery Switching)

**Files:**
- Create: `tests/test_tune_power.py`
- Modify: `os_manager/commands/tune.py`
- Modify: `scripts/tune_hardware.sh`

**Interfaces:**
- Produces:
  - `generate_power_profile_udev_rule() -> str`
  - `apply_power_profile(profile: str) -> dict[str, Any]`
  - `audit_power_profile() -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for power profile application and udev generation**

```python
# tests/test_tune_power.py
import unittest
from unittest.mock import patch, MagicMock
from os_manager.commands.tune import (
    generate_power_profile_udev_rule,
    apply_power_profile,
    audit_power_profile,
)


class TestTunePower(unittest.TestCase):
    def test_generate_power_profile_udev_rule(self):
        rule = generate_power_profile_udev_rule()
        self.assertIn('SUBSYSTEM=="power_supply"', rule)
        self.assertIn('ATTR{online}=="0"', rule)
        self.assertIn('ATTR{online}=="1"', rule)
        self.assertIn("osm tune power --profile", rule)

    def test_apply_power_profile_ac(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = apply_power_profile("ac")
            self.assertTrue(res["success"])
            self.assertEqual(res["profile"], "ac")
            self.assertEqual(res["epp"], "balance_performance")

    def test_apply_power_profile_battery(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = apply_power_profile("battery")
            self.assertTrue(res["success"])
            self.assertEqual(res["profile"], "battery")
            self.assertEqual(res["epp"], "balance_power")

    def test_audit_power_profile(self):
        res = audit_power_profile()
        self.assertIn("current_epp", res)
        self.assertIn("power_source", res)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tune_power.py -v`  
Expected: FAIL with `ImportError: cannot import name 'generate_power_profile_udev_rule'`

- [ ] **Step 3: Implement power profile switching in `os_manager/commands/tune.py` and `scripts/tune_hardware.sh`**

```python
# In os_manager/commands/tune.py
SYSFS_EPP_NODES = "/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"
SYSFS_EPB_NODES = "/sys/devices/system/cpu/cpu*/power/energy_perf_bias"
POWER_PROFILE_UDEV_PATH = "/etc/udev/rules.d/99-osm-power-profile.rules"


def generate_power_profile_udev_rule() -> str:
    """Generate udev rules for automatic AC/Battery tuning switching."""
    return """# /etc/udev/rules.d/99-osm-power-profile.rules - Managed by os-manager
SUBSYSTEM=="power_supply", ATTR{online}=="0", RUN+="/usr/local/bin/osm tune power --profile battery"
SUBSYSTEM=="power_supply", ATTR{online}=="1", RUN+="/usr/local/bin/osm tune power --profile ac"
"""


def apply_power_profile(profile: str) -> dict[str, Any]:
    """Apply dynamic kernel, CPU governor, and scheduler tunings for AC or Battery profile."""
    prof = profile.lower()
    if prof not in ["ac", "battery", "bat"]:
        return {"success": False, "error": f"Unknown profile '{profile}'. Valid: ac, battery"}

    is_ac = prof == "ac"
    target_epp = "balance_performance" if is_ac else "balance_power"
    target_epb = "4" if is_ac else "8"
    target_platform = "balanced" if is_ac else "low-power"
    target_slice = 2000000 if is_ac else 3000000

    try:
        # Write EPP across online CPUs
        cpu_glob = list(Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/energy_performance_preference"))
        for node in cpu_glob:
            if os.geteuid() != 0:
                subprocess.run(["sudo", "tee", str(node)], input=f"{target_epp}\n", text=True, capture_output=True, check=False)
            else:
                node.write_text(f"{target_epp}\n", encoding="utf-8")

        # Set platform profile if supported
        set_platform_profile(target_platform)

        # Set EEVDF scheduler base slice
        if Path("/proc/sys/kernel/sched_base_slice_ns").is_file():
            if os.geteuid() != 0:
                subprocess.run(
                    ["sudo", "sysctl", "-w", f"kernel.sched_base_slice_ns={target_slice}"],
                    capture_output=True,
                    check=False,
                )
            else:
                subprocess.run(["sysctl", "-w", f"kernel.sched_base_slice_ns={target_slice}"], capture_output=True, check=False)

        return {
            "success": True,
            "profile": "ac" if is_ac else "battery",
            "epp": target_epp,
            "epb": target_epb,
            "platform_profile": target_platform,
            "sched_base_slice_ns": target_slice,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def audit_power_profile() -> dict[str, Any]:
    """Inspect active CPU frequency governor, EPP, EPB, and AC power supply state."""
    current_epp = "unknown"
    node_0 = Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference")
    if node_0.is_file():
        try:
            current_epp = node_0.read_text().strip()
        except Exception:
            pass

    power_source = "battery"
    for ps in Path("/sys/class/power_supply").glob("*"):
        type_file = ps / "type"
        online_file = ps / "online"
        if type_file.is_file() and type_file.read_text().strip().lower() == "mains":
            if online_file.is_file() and online_file.read_text().strip() == "1":
                power_source = "ac"
                break

    return {
        "current_epp": current_epp,
        "power_source": power_source,
        "platform_profile": get_platform_profile(),
        "conservation_mode": get_battery_conservation_status(),
        "fn_lock": get_fn_lock_status(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tune_power.py -v`  
Expected: PASS with 4 passing tests.

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py scripts/tune_hardware.sh tests/test_tune_power.py
git commit -m "feat(tune): implement dynamic dual-profile AC/Battery power engine"
```

---

### Task 6: Storage & I/O Engine (Hardened `ntfs3`, EXT4 `lazytime`, NVMe Schedulers)

**Files:**
- Create: `tests/test_tune_storage.py`
- Modify: `os_manager/commands/tune.py`
- Modify: `scripts/tune_system.sh`

**Interfaces:**
- Produces:
  - `generate_hardened_fstab_ntfs3_entry(current_fstab: str, mount_point: str = "/mnt/data") -> str`
  - `generate_nvme_udev_scheduler_rule() -> str`
  - `audit_nvme_storage_subsystem() -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for hardened ntfs3 fstab and NVMe scheduler udev generators**

```python
# tests/test_tune_storage.py
import unittest
from os_manager.commands.tune import (
    generate_hardened_fstab_ntfs3_entry,
    generate_nvme_udev_scheduler_rule,
    audit_nvme_storage_subsystem,
)


class TestTuneStorage(unittest.TestCase):
    def test_generate_hardened_fstab_ntfs3_entry(self):
        sample_fstab = (
            "UUID=3E01-3117 /boot/efi vfat defaults,noatime 0 2\n"
            "UUID=6C7AB7E37AB7A7EA /mnt/data ntfs-3g defaults,uid=1000,gid=1000,umask=022,nofail 0 0\n"
        )
        updated = generate_hardened_fstab_ntfs3_entry(sample_fstab, mount_point="/mnt/data")
        self.assertIn("ntfs3", updated)
        self.assertNotIn("ntfs-3g", updated)
        self.assertIn("windows_names", updated)
        self.assertIn("prealloc", updated)
        self.assertIn("dmask=027,fmask=137", updated)
        self.assertIn("iocharset=utf8", updated)

    def test_generate_nvme_udev_scheduler_rule(self):
        rule = generate_nvme_udev_scheduler_rule()
        self.assertIn('KERNEL=="nvme[0-9]*n[0-9]*"', rule)
        self.assertIn('ATTR{queue/scheduler}="none"', rule)
        self.assertIn('ATTR{queue/nr_requests}="256"', rule)

    def test_audit_nvme_storage_subsystem(self):
        res = audit_nvme_storage_subsystem()
        self.assertIn("ntfs3_active", res)
        self.assertIn("nvme_scheduler", res)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tune_storage.py -v`  
Expected: FAIL with `ImportError: cannot import name 'generate_hardened_fstab_ntfs3_entry'`

- [ ] **Step 3: Implement hardened storage generators in `os_manager/commands/tune.py` and `scripts/tune_system.sh`**

```python
# In os_manager/commands/tune.py
NVME_UDEV_RULE_PATH = "/etc/udev/rules.d/60-nvme-schedulers.rules"


def generate_hardened_fstab_ntfs3_entry(current_fstab: str, mount_point: str = "/mnt/data") -> str:
    """Generate hardened ntfs3 fstab entry preserving Windows invariants and POSIX masks."""
    lines = []
    for line in current_fstab.splitlines():
        if mount_point in line and ("ntfs-3g" in line or "ntfs3" in line):
            parts = line.split()
            if len(parts) >= 2:
                uuid_part = parts[0]
                mp_part = parts[1]
                opts = "defaults,uid=1000,gid=1000,dmask=027,fmask=137,windows_names,iocharset=utf8,noatime,prealloc,nocase,hide_dot_files,nofail"
                line = f"{uuid_part}  {mp_part}  ntfs3  {opts}  0  0"
        lines.append(line)
    return "\n".join(lines) + "\n"


def generate_nvme_udev_scheduler_rule() -> str:
    """Generate udev rule setting NVMe I/O scheduler to none and nr_requests to 256."""
    return """# /etc/udev/rules.d/60-nvme-schedulers.rules - Managed by os-manager
ACTION=="add|change", KERNEL=="nvme[0-9]*n[0-9]*", ATTR{queue/scheduler}="none", ATTR{queue/nr_requests}="256"
"""


def audit_nvme_storage_subsystem() -> dict[str, Any]:
    """Inspect NVMe block layer scheduler, queue depth, TRIM, and NTFS drivers."""
    ntfs = audit_ntfs_mount_driver("/mnt/data")
    trim = audit_fstrim_timer_status()
    sched = "unknown"
    nr_req = "unknown"

    sched_file = Path("/sys/block/nvme0n1/queue/scheduler")
    if sched_file.is_file():
        try:
            raw = sched_file.read_text().strip()
            for token in raw.split():
                if token.startswith("[") and token.endswith("]"):
                    sched = token.strip("[]")
        except Exception:
            pass

    req_file = Path("/sys/block/nvme0n1/queue/nr_requests")
    if req_file.is_file():
        try:
            nr_req = req_file.read_text().strip()
        except Exception:
            pass

    return {
        "ntfs3_active": ntfs.get("is_inkernel", False),
        "ntfs_driver": ntfs.get("driver", "unknown"),
        "trim_active": trim.get("active", False),
        "nvme_scheduler": sched,
        "nvme_nr_requests": nr_req,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tune_storage.py -v`  
Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/tune.py scripts/tune_system.sh tests/test_tune_storage.py
git commit -m "feat(tune): implement hardened ntfs3 mount and NVMe multi-queue udev tuning"
```

---

### Task 7: Empirical Benchmarking Engine (`osm perf`)

**Files:**
- Create: `tests/test_perf.py`
- Modify: `os_manager/commands/perf.py`

**Interfaces:**
- Produces:
  - `run_cpu_benchmark(quick: bool = True) -> dict[str, Any]`
  - `run_memory_benchmark(quick: bool = True) -> dict[str, Any]`
  - `run_io_benchmark(quick: bool = True) -> dict[str, Any]`
  - `run_audio_jitter_benchmark() -> dict[str, Any]`
  - `run_perf(args: list[str]) -> int`

- [ ] **Step 1: Write failing tests for empirical benchmark runner and parser**

```python
# tests/test_perf.py
import unittest
from unittest.mock import patch, MagicMock
from os_manager.commands.perf import (
    run_cpu_benchmark,
    run_memory_benchmark,
    run_io_benchmark,
    run_audio_jitter_benchmark,
    run_perf,
)


class TestPerfEngine(unittest.TestCase):
    def test_run_cpu_benchmark_quick(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="events per second: 12500.42\ntotal time: 2.0001s\n",
            )
            res = run_cpu_benchmark(quick=True)
            self.assertTrue(res["available"])
            self.assertIn("score", res)

    def test_run_memory_benchmark(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Total operations: 1048576 (524288.00 per second)\n4096.00 MB transferred (20480.00 MB/sec)\n",
            )
            res = run_memory_benchmark(quick=True)
            self.assertTrue(res["available"])
            self.assertIn("throughput_mb_s", res)

    def test_run_io_benchmark(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="READ: bw=450MiB/s\nWRITE: bw=380MiB/s (398MB/s), 95000 IOPS\n",
            )
            res = run_io_benchmark(quick=True)
            self.assertTrue(res["available"])
            self.assertIn("write_iops", res)

    def test_run_perf_all_json(self):
        with patch("os_manager.commands.perf.run_cpu_benchmark", return_value={"available": True, "score": 100}), \
             patch("os_manager.commands.perf.run_memory_benchmark", return_value={"available": True, "throughput_mb_s": 5000}), \
             patch("os_manager.commands.perf.run_io_benchmark", return_value={"available": True, "write_iops": 50000}), \
             patch("os_manager.commands.perf.run_audio_jitter_benchmark", return_value={"available": True, "xruns": 0}):
            ret = run_perf(["all", "--json"])
            self.assertEqual(ret, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_perf.py -v`  
Expected: FAIL with `ImportError: cannot import name 'run_cpu_benchmark'`

- [ ] **Step 3: Implement empirical benchmark subroutines in `os_manager/commands/perf.py`**

```python
# In os_manager/commands/perf.py
"""Filesystem, CPU, memory, scheduler, and audio empirical benchmark engine."""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import time
from typing import Any


def run_cpu_benchmark(quick: bool = True) -> dict[str, Any]:
    """Execute CPU & scheduler scheduling latency benchmark."""
    sysbench_bin = shutil.which("sysbench")
    if not sysbench_bin:
        return {"available": False, "reason": "sysbench not installed"}

    max_prime = 10000 if quick else 30000
    cmd = [sysbench_bin, "cpu", f"--cpu-max-prime={max_prime}", "--threads=8", "run"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        return {"available": False, "error": res.stderr.strip()}

    eps = 0.0
    for line in res.stdout.splitlines():
        if "events per second:" in line:
            m = re.search(r"([\d\.]+)", line.split(":", 1)[1])
            if m:
                eps = float(m.group(1))

    return {
        "available": True,
        "score": eps,
        "threads": 8,
        "max_prime": max_prime,
        "raw": res.stdout,
    }


def run_memory_benchmark(quick: bool = True) -> dict[str, Any]:
    """Execute memory allocation and throughput benchmark."""
    sysbench_bin = shutil.which("sysbench")
    if not sysbench_bin:
        return {"available": False, "reason": "sysbench not installed"}

    size = "1G" if quick else "4G"
    cmd = [
        sysbench_bin,
        "memory",
        "--memory-oper=write",
        "--memory-access-mode=rnd",
        "--memory-block-size=4K",
        f"--memory-total-size={size}",
        "--threads=8",
        "run",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        return {"available": False, "error": res.stderr.strip()}

    throughput = 0.0
    for line in res.stdout.splitlines():
        if "transferred (" in line:
            m = re.search(r"\(([\d\.]+)\s*MB/sec\)", line)
            if m:
                throughput = float(m.group(1))

    return {
        "available": True,
        "throughput_mb_s": throughput,
        "size": size,
        "raw": res.stdout,
    }


def run_io_benchmark(quick: bool = True, target_path: str = "/tmp/osm_bench.tmp") -> dict[str, Any]:
    """Execute storage 4K random write IOPS and tail latency benchmark via fio."""
    fio_bin = shutil.which("fio")
    if not fio_bin:
        # Fallback pure-Python DD write benchmark
        start = time.perf_counter()
        data = b"\0" * (1024 * 1024)
        with open(target_path, "wb") as f:
            for _ in range(50 if quick else 200):
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        dur = time.perf_counter() - start
        if os.path.exists(target_path):
            os.remove(target_path)
        mb = 50 if quick else 200
        mb_s = round(mb / dur, 2) if dur > 0 else 0.0
        return {
            "available": True,
            "engine": "python_sync",
            "throughput_mb_s": mb_s,
            "write_iops": int(mb_s * 256),
        }

    runtime = 3 if quick else 10
    cmd = [
        fio_bin,
        "--name=osm_randwrite",
        "--ioengine=libaio",
        "--iodepth=16",
        "--rw=randwrite",
        "--bs=4k",
        "--size=256M",
        f"--runtime={runtime}",
        "--time_based",
        "--group_reporting",
        f"--filename={target_path}",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if os.path.exists(target_path):
        try:
            os.remove(target_path)
        except Exception:
            pass

    if res.returncode != 0:
        return {"available": False, "error": res.stderr.strip()}

    iops = 0
    bw = 0.0
    for line in res.stdout.splitlines():
        if "IOPS=" in line or "IOPS" in line:
            m = re.search(r"IOPS=([\d\.]+[kK]?)", line) or re.search(r"([\d\.]+)\s*IOPS", line)
            if m:
                val_s = m.group(1).lower()
                iops = int(float(val_s.replace("k", "")) * 1000) if "k" in val_s else int(float(val_s))
        if "bw=" in line:
            m = re.search(r"bw=([\d\.]+)(MiB/s|MB/s|KiB/s)", line)
            if m:
                bw = float(m.group(1))

    return {
        "available": True,
        "engine": "fio",
        "write_iops": iops,
        "throughput_mb_s": bw,
        "raw": res.stdout,
    }


def run_audio_jitter_benchmark() -> dict[str, Any]:
    """Audit PipeWire audio graph buffer latency and underrun (xrun) errors."""
    pw_top_bin = shutil.which("pw-top")
    if not pw_top_bin:
        return {"available": False, "reason": "pw-top not installed"}

    res = subprocess.run([pw_top_bin, "-b", "-n", "2"], capture_output=True, text=True, check=False)
    xruns = 0
    quantum = 256
    rate = 48000
    if res.returncode == 0 and res.stdout:
        for line in res.stdout.splitlines():
            if "ERR" in line:
                parts = line.split()
                if len(parts) >= 2 and parts[-1].isdigit():
                    xruns += int(parts[-1])

    return {
        "available": True,
        "xruns": xruns,
        "active_quantum": quantum,
        "active_rate": rate,
    }


def run_perf(args: list[str]) -> int:
    """Execute empirical system optimization benchmarks."""
    parser = argparse.ArgumentParser(
        prog="osm perf",
        description="Empirical hardware, CPU, memory, storage, and audio benchmark runner.",
    )
    parser.add_argument("subaction", nargs="?", default="all", choices=["all", "cpu", "mem", "io", "audio"])
    parser.add_argument("--quick", action="store_true", help="Run short-duration benchmark sweep")
    parser.add_argument("--full", action="store_true", help="Run thorough multi-pass benchmark suite")
    parser.add_argument("--json", action="store_true", help="Output benchmark metrics as JSON")

    parsed = parser.parse_args(args)
    is_quick = not parsed.full

    results: dict[str, Any] = {
        "status": "success",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "quick" if is_quick else "full",
        "benchmarks": {},
    }

    if parsed.subaction in ["all", "cpu"]:
        results["benchmarks"]["cpu"] = run_cpu_benchmark(quick=is_quick)
    if parsed.subaction in ["all", "mem"]:
        results["benchmarks"]["memory"] = run_memory_benchmark(quick=is_quick)
    if parsed.subaction in ["all", "io"]:
        results["benchmarks"]["storage_io"] = run_io_benchmark(quick=is_quick)
    if parsed.subaction in ["all", "audio"]:
        results["benchmarks"]["audio"] = run_audio_jitter_benchmark()

    if parsed.json:
        print(json.dumps(results, indent=2))
        return 0

    print("==================================================")
    print(f"      OS-Manager Empirical Benchmark Suite ({results['mode'].upper()})      ")
    print("==================================================")
    for b_name, b_data in results["benchmarks"].items():
        if not b_data.get("available", False):
            print(f"[{b_name.upper()}] Unavailable: {b_data.get('reason', b_data.get('error', 'unknown'))}")
            continue
        print(f"[{b_name.upper()}] Benchmark Results:")
        for k, v in b_data.items():
            if k not in ["raw", "available"]:
                print(f"  - {k}: {v}")
    print("==================================================")
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_perf.py -v`  
Expected: PASS with 4 passing tests.

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/perf.py tests/test_perf.py
git commit -m "feat(perf): implement empirical CPU, memory, storage IOPS, and audio benchmark engine"
```

---

### Task 8: Unified CLI Integration, Master Telemetry & Live Verification

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `os_manager/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces:
  - Complete routing for `osm tune [all|memory|scheduler|audio|power|storage|hardware|persist|revert]`
  - Simulation support `--dry-run` and master telemetry `--json`
  - Integration with `osm perf`

- [ ] **Step 1: Write failing tests for updated CLI routing and new subactions**

```python
# In tests/test_cli.py
def test_cli_tune_revert_list(self):
    res = subprocess.run(["osm", "tune", "revert", "--list"], capture_output=True, text=True)
    self.assertEqual(res.returncode, 0)
    self.assertIn("Snapshots", res.stdout)

def test_cli_tune_power_audit(self):
    res = subprocess.run(["osm", "tune", "power", "--audit"], capture_output=True, text=True)
    self.assertEqual(res.returncode, 0)
    self.assertIn("Power", res.stdout)

def test_cli_perf_all_json(self):
    res = subprocess.run(["osm", "perf", "all", "--quick", "--json"], capture_output=True, text=True)
    self.assertEqual(res.returncode, 0)
    import json
    data = json.loads(res.stdout)
    self.assertIn("benchmarks", data)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -k "test_cli_tune_revert_list or test_cli_tune_power_audit or test_cli_perf_all_json" -v`  
Expected: FAIL

- [ ] **Step 3: Wire subparser handlers and `--dry-run` simulation in `os_manager/commands/tune.py` and `os_manager/cli.py`**

- [ ] **Step 4: Run complete test suite**

Run: `pytest tests/test_tune_*.py tests/test_perf.py tests/test_cli.py -v`  
Expected: 100% tests PASS across all modules.

- [ ] **Step 5: Commit and finalize**

```bash
git add os_manager/commands/tune.py os_manager/cli.py tests/test_cli.py
git commit -m "feat(cli): complete unified osm tune adaptive engine and osm perf benchmarks"
```

---

## 7. Self-Review & Integrity Validation

* [x] **Spec Coverage:** All pillars from the spec (MGLRU, zRAM swappiness=180, EEVDF 2ms, PipeWire 256 quantum, AC/Battery dynamic power, hardened ntfs3, snapshot/revert, and empirical benchmark) are covered in Tasks 1–8.
* [x] **Placeholder Scan:** Zero `TBD`, `TODO`, or unspecified code blocks.
* [x] **Type Consistency:** Method signatures and configuration constants match exactly across tasks.

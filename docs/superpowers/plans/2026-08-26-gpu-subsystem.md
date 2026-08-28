# Intelligent Dual-GPU Subsystem & Workload Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous dual-GPU management subsystem (`osm gpu`) and HAL abstraction that audits GPU hardware, automates Debian 13 driver provisioning (with Pascal architecture DKMS enforcement), automatically routes desktop application workloads using Freedesktop standards, and provides persistent power profile switching.

**Architecture:** Extend HAL data models in `base.py` with multi-vendor GPU telemetry and sysfs scanning in `generic_linux.py`. Implement heuristic application classification in `gpu_classifier.py` to tag `.desktop` entries for Intel iGPU vs NVIDIA dGPU. Provide a standalone CLI controller in `os_manager/commands/gpu.py` with `status`, `install`, `run`, `sync-profiles`, and `profile` subcommands, integrated into `cli.py` and `diag.py`.

**Tech Stack:** Python 3.11+ (Standard Library `dataclasses`, `subprocess`, `argparse`, `pathlib`, `json`, `shutil`), Freedesktop Desktop Entry Specification, Pytest.

**Spec:** `docs/superpowers/specs/2026-08-26-intelligent-gpu-subsystem-design.md`

## Global Constraints

- Platform: Debian 13 (Trixie) Linux Native / Lenovo IdeaPad (Product `81WD`), Linux kernel 6.12+ x86_64.
- Hardware Target: Intel Iris Plus G1 (`8086:8a56`) iGPU + NVIDIA GeForce MX330 (`10de:1d16`) Pascal GP108M dGPU.
- Driver Rule: Strictly enforce `nvidia-kernel-dkms` (proprietary) for Pascal GP108M; forbid `nvidia-open-kernel-dkms`.
- Non-Interactive Sudo: Privilege operations must resolve `SUDO_PASSWORD` from `${CLAUDE_PROJECT_DIR}/.env` and stream via `sudo -S`.
- Guardrail: Never modify `/dev/null` directly or trigger Tier 3 harness violations.

---

### Task 1: Extend HAL Models and Implement GPU Scanner

**Files:**
- Modify: `os_manager/platform/hal/base.py`
- Modify: `os_manager/platform/hal/generic_linux.py`
- Test: `tests/gpu/test_gpu_hal.py`

**Interfaces:**
- Produces: `GpuDeviceInfo`, `GpuSubsystemInfo`, `AbstractHardwareDriver.audit_gpu_subsystem() -> GpuSubsystemInfo`

- [ ] **Step 1: Write the failing test for GPU HAL data models and sysfs scanner**

```python
# tests/gpu/test_gpu_hal.py
import pytest
from pathlib import Path
from os_manager.platform.hal.base import GpuDeviceInfo, GpuSubsystemInfo
from os_manager.platform.hal.generic_linux import GenericLinuxDriver


def test_gpu_device_info_dataclass():
    dev = GpuDeviceInfo(
        vendor="NVIDIA",
        device_name="GeForce MX330",
        pci_slot="0000:01:00.0",
        driver_in_use="nvidia",
        is_discrete=True,
        power_state="suspended",
        vaapi_supported=False,
        cuda_supported=True,
    )
    assert dev.vendor == "NVIDIA"
    assert dev.is_discrete is True
    assert dev.cuda_supported is True


def test_audit_gpu_subsystem_mock_sysfs(tmp_path: Path):
    # Setup mock sysfs
    pci_dir = tmp_path / "sys/bus/pci/devices"
    pci_dir.mkdir(parents=True)

    # Mock Intel iGPU (0000:00:02.0)
    igpu_dir = pci_dir / "0000:00:02.0"
    igpu_dir.mkdir()
    (igpu_dir / "vendor").write_text("0x8086\n", encoding="utf-8")
    (igpu_dir / "device").write_text("0x8a56\n", encoding="utf-8")
    (igpu_dir / "class").write_text("0x030000\n", encoding="utf-8")
    (igpu_dir / "power").mkdir()
    (igpu_dir / "power/runtime_status").write_text("active\n", encoding="utf-8")

    # Mock NVIDIA dGPU (0000:01:00.0)
    dgpu_dir = pci_dir / "0000:01:00.0"
    dgpu_dir.mkdir()
    (dgpu_dir / "vendor").write_text("0x10de\n", encoding="utf-8")
    (dgpu_dir / "device").write_text("0x1d16\n", encoding="utf-8")
    (dgpu_dir / "class").write_text("0x030200\n", encoding="utf-8")
    (dgpu_dir / "power").mkdir()
    (dgpu_dir / "power/runtime_status").write_text("suspended\n", encoding="utf-8")

    driver = GenericLinuxDriver(sysfs_root=tmp_path)
    subsystem = driver.audit_gpu_subsystem()

    assert subsystem.primary_display_gpu is not None
    assert subsystem.primary_display_gpu.vendor == "Intel"
    assert subsystem.primary_display_gpu.is_discrete is False
    assert subsystem.discrete_gpu is not None
    assert subsystem.discrete_gpu.vendor == "NVIDIA"
    assert subsystem.discrete_gpu.is_discrete is True
    assert subsystem.discrete_gpu.power_state == "suspended"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/gpu/test_gpu_hal.py -v`
Expected: FAIL with missing classes/attributes.

- [ ] **Step 3: Implement data models in `base.py` and `audit_gpu_subsystem` in `generic_linux.py`**

In `os_manager/platform/hal/base.py`:
```python
@dataclass
class GpuDeviceInfo:
    vendor: str = "Unknown"
    device_name: str = "Unknown"
    pci_slot: str = ""
    driver_in_use: str = "none"
    is_discrete: bool = False
    power_state: str = "unsupported"
    vaapi_supported: bool = False
    cuda_supported: bool = False


@dataclass
class GpuSubsystemInfo:
    primary_display_gpu: Optional[GpuDeviceInfo] = None
    discrete_gpu: Optional[GpuDeviceInfo] = None
    active_profile: str = "hybrid"
    driver_flavor: str = "missing"
```

In `os_manager/platform/hal/generic_linux.py`:
Implement `audit_gpu_subsystem(self) -> GpuSubsystemInfo` scanning `sys/bus/pci/devices/`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/gpu/test_gpu_hal.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/platform/hal/base.py os_manager/platform/hal/generic_linux.py tests/gpu/test_gpu_hal.py
git commit -m "feat(hal): implement multi-vendor GPU subsystem scanner and telemetry models"
```

---

### Task 2: Implement Heuristic Application Classifier & Sync Engine

**Files:**
- Create: `os_manager/platform/hal/gpu_classifier.py`
- Test: `tests/gpu/test_gpu_classifier.py`

**Interfaces:**
- Consumes: Freedesktop Desktop Entry specifications
- Produces: `classify_application(desktop_content: str) -> str`, `sync_desktop_profiles(source_dirs: list[Path], target_dir: Path, dry_run: bool = False) -> list[dict]`

- [ ] **Step 1: Write failing tests for application classifier and sync engine**

```python
# tests/gpu/test_gpu_classifier.py
import pytest
from pathlib import Path
from os_manager.platform.hal.gpu_classifier import (
    classify_application,
    sync_desktop_profiles,
)


def test_classify_media_app_to_intel():
    content = """[Desktop Entry]
Name=Spotube
Exec=spotube %U
Categories=AudioVideo;Audio;Player;
"""
    assert classify_application(content) == "intel"


def test_classify_3d_game_to_nvidia():
    content = """[Desktop Entry]
Name=Blender
Exec=blender %f
Categories=Graphics;3DGraphics;
"""
    assert classify_application(content) == "nvidia"


def test_sync_desktop_profiles_creates_overrides(tmp_path: Path):
    system_dir = tmp_path / "usr_share"
    system_dir.mkdir(parents=True)
    user_dir = tmp_path / "user_share"
    user_dir.mkdir(parents=True)

    # Media app (Intel - should not override with discrete)
    (system_dir / "spotube.desktop").write_text(
        "[Desktop Entry]\nName=Spotube\nExec=spotube\nCategories=Audio;Player;\n",
        encoding="utf-8",
    )

    # 3D app (NVIDIA - should create override with PrefersNonDefaultGPU)
    (system_dir / "blender.desktop").write_text(
        "[Desktop Entry]\nName=Blender\nExec=blender\nCategories=Graphics;3DGraphics;\n",
        encoding="utf-8",
    )

    synced = sync_desktop_profiles(source_dirs=[system_dir], target_dir=user_dir)
    assert len(synced) == 1
    assert synced[0]["app"] == "blender"

    override_file = user_dir / "blender.desktop"
    assert override_file.exists()
    content = override_file.read_text(encoding="utf-8")
    assert "PrefersNonDefaultGPU=true" in content
    assert "X-KDE-RunOnDiscreteGpu=true" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/gpu/test_gpu_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'os_manager.platform.hal.gpu_classifier'`.

- [ ] **Step 3: Implement `os_manager/platform/hal/gpu_classifier.py`**

Implement classification heuristics:
- If Categories match `Game`, `3DGraphics`, `Engineering`, or Name/Exec matches `blender`, `godot`, `steam`, `unreal`, `ollama`, `pytorch`: return `"nvidia"`.
- Else return `"intel"`.
Implement `sync_desktop_profiles` to inject `PrefersNonDefaultGPU=true` and `X-KDE-RunOnDiscreteGpu=true` into `target_dir / file.name`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/gpu/test_gpu_classifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/platform/hal/gpu_classifier.py tests/gpu/test_gpu_classifier.py
git commit -m "feat(gpu): implement intelligent application heuristic classifier and profile sync"
```

---

### Task 3: Implement `osm gpu` Command Controller

**Files:**
- Create: `os_manager/commands/gpu.py`
- Modify: `os_manager/cli.py`
- Test: `tests/commands/test_gpu_command.py`

**Interfaces:**
- Consumes: `GenericLinuxDriver.audit_gpu_subsystem`, `sync_desktop_profiles`
- Produces: `run_gpu(argv: list[str]) -> int`, subcommands: `status`, `install`, `run`, `sync-profiles`, `profile`

- [ ] **Step 1: Write failing tests for `osm gpu` command**

```python
# tests/commands/test_gpu_command.py
import pytest
from unittest.mock import patch, MagicMock
from os_manager.commands.gpu import run_gpu


def test_gpu_command_status_json(capsys):
    with patch("os_manager.commands.gpu.get_active_hardware_driver") as mock_drv:
        mock_instance = MagicMock()
        mock_subsystem = MagicMock()
        mock_subsystem.active_profile = "hybrid"
        mock_subsystem.driver_flavor = "nouveau"
        mock_subsystem.primary_display_gpu = MagicMock(vendor="Intel", device_name="Iris Plus G1", power_state="active")
        mock_subsystem.discrete_gpu = MagicMock(vendor="NVIDIA", device_name="GeForce MX330", power_state="suspended")
        mock_instance.audit_gpu_subsystem.return_value = mock_subsystem
        mock_drv.return_value = mock_instance

        code = run_gpu(["status", "--json"])
        assert code == 0
        captured = capsys.readouterr()
        assert '"vendor": "Intel"' in captured.out or '"vendor": "NVIDIA"' in captured.out


def test_gpu_command_run_wrapper():
    with patch("os_manager.commands.gpu.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        code = run_gpu(["run", "glxgears"])
        assert code == 0
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        env = kwargs.get("env", {})
        assert env.get("__NV_PRIME_RENDER_OFFLOAD") == "1"
        assert env.get("__GLX_VENDOR_LIBRARY_NAME") == "nvidia"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/commands/test_gpu_command.py -v`
Expected: FAIL with missing module `os_manager.commands.gpu`.

- [ ] **Step 3: Implement `os_manager/commands/gpu.py` and register in `cli.py`**

Implement subcommands:
- `status`: format JSON or human TTY report.
- `install`: verify Pascal GPU, reject open dkms, stream `apt-get install -y nvidia-kernel-dkms nvidia-driver firmware-misc-nonfree intel-media-va-driver-non-free`.
- `run`: execute subprocess with PRIME env variables.
- `sync-profiles`: invoke `sync_desktop_profiles`.
- `profile`: write modprobe options (`NVreg_DynamicPowerManagement=0x02` or `0x00`).
Register `gpu` subcommand in `os_manager/cli.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/commands/test_gpu_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/gpu.py os_manager/cli.py tests/commands/test_gpu_command.py
git commit -m "feat(cli): introduce osm gpu command controller for lifecycle and offloading"
```

---

### Task 4: Integrate GPU Subsystem Telemetry into `osm diag` and Verify Full Suite

**Files:**
- Modify: `os_manager/commands/diag.py`
- Test: `tests/commands/test_diag_gpu.py`

**Interfaces:**
- Consumes: `AbstractHardwareDriver.audit_gpu_subsystem`
- Produces: Enhanced `osm diag` JSON & TTY schema with `"gpu"` block

- [ ] **Step 1: Write failing test for `osm diag` GPU block**

```python
# tests/commands/test_diag_gpu.py
import json
import pytest
from unittest.mock import patch, MagicMock
from os_manager.commands.diag import run_diag


def test_diag_includes_gpu_telemetry(capsys):
    with patch("os_manager.commands.diag.get_active_hardware_driver") as mock_drv:
        mock_inst = MagicMock()
        mock_subsystem = MagicMock()
        mock_subsystem.active_profile = "hybrid"
        mock_subsystem.driver_flavor = "nouveau"
        mock_subsystem.primary_display_gpu = MagicMock(vendor="Intel", device_name="Iris Plus G1", power_state="active")
        mock_subsystem.discrete_gpu = MagicMock(vendor="NVIDIA", device_name="GeForce MX330", power_state="suspended")
        mock_inst.audit_gpu_subsystem.return_value = mock_subsystem
        mock_inst.get_dmi_info.return_value = MagicMock(vendor="LENOVO", product_name="81WD")
        mock_drv.return_value = mock_inst

        code = run_diag(["--json"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "gpu" in data
        assert data["gpu"]["active_profile"] == "hybrid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/commands/test_diag_gpu.py -v`
Expected: FAIL with `"gpu"` key missing in `data`.

- [ ] **Step 3: Update `os_manager/commands/diag.py` to include GPU telemetry**

In `run_diag`:
Call `driver.audit_gpu_subsystem()` and embed the GPU summary into the output dictionary and TTY output.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/commands/test_diag_gpu.py -v`
Expected: PASS

- [ ] **Step 5: Run full project test suite and harness check**

Run: `.venv/bin/pytest tests/` and `./tests/test_harness.sh`
Expected: All 300+ assertions PASS.

- [ ] **Step 6: Commit**

```bash
git add os_manager/commands/diag.py tests/commands/test_diag_gpu.py
git commit -m "feat(diag): expose dual-GPU subsystem telemetry in system diagnostics"
```

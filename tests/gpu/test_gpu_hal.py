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

"""Hardware Abstraction Layer (HAL) for os-manager."""

from .asus import AsusDriver
from .base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
    GpuDeviceInfo,
    GpuSubsystemInfo,
    PlatformProfileInfo,
)
from .dell import DellDriver
from .generic_linux import GenericLinuxDriver
from .lenovo import LenovoDriver
from .macos import DarwinDriver
from .registry import HardwareRegistry, get_active_hardware_driver
from .storage import StorageSubsystemInfo, audit_storage_subsystem
from .thinkpad import ThinkPadDriver

__all__ = [
    "AbstractHardwareDriver",
    "GenericLinuxDriver",
    "PlatformProfileInfo",
    "BatteryHealthInfo",
    "DmiInfo",
    "GpuDeviceInfo",
    "GpuSubsystemInfo",
    "LenovoDriver",
    "ThinkPadDriver",
    "AsusDriver",
    "DellDriver",
    "DarwinDriver",
    "HardwareRegistry",
    "get_active_hardware_driver",
    "StorageSubsystemInfo",
    "audit_storage_subsystem",
]

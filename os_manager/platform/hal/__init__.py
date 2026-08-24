"""Hardware Abstraction Layer (HAL) for os-manager."""

from .asus import AsusDriver
from .base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
    PlatformProfileInfo,
)
from .dell import DellDriver
from .generic_linux import GenericLinuxDriver
from .lenovo import LenovoDriver
from .macos import DarwinDriver
from .thinkpad import ThinkPadDriver

__all__ = [
    "AbstractHardwareDriver",
    "GenericLinuxDriver",
    "PlatformProfileInfo",
    "BatteryHealthInfo",
    "DmiInfo",
    "LenovoDriver",
    "ThinkPadDriver",
    "AsusDriver",
    "DellDriver",
    "DarwinDriver",
]


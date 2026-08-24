"""Hardware Abstraction Layer (HAL) for os-manager."""

from .base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
    PlatformProfileInfo,
)

__all__ = [
    "AbstractHardwareDriver",
    "PlatformProfileInfo",
    "BatteryHealthInfo",
    "DmiInfo",
]

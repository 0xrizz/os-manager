"""Abstract Base Classes and Data Models for Hardware Abstraction Layer."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PlatformProfileInfo:
    supported: bool = False
    current: str = "unsupported"
    choices: List[str] = field(default_factory=list)


@dataclass
class BatteryHealthInfo:
    supported: bool = False
    conservation_mode: bool = False
    threshold: Optional[int] = None
    health_percent: Optional[float] = None


@dataclass
class DmiInfo:
    vendor: str = "Unknown"
    product_name: str = "Unknown"
    family: str = "Unknown"
    bios_version: str = "Unknown"


class AbstractHardwareDriver(ABC):
    """Base interface for vendor and platform hardware drivers."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        self.sysfs_root = sysfs_root or Path("/")

    @abstractmethod
    def probe(self) -> bool:
        """Return True if running hardware is supported by this driver."""
        pass

    @abstractmethod
    def get_dmi_info(self) -> DmiInfo:
        """Query DMI/SMBIOS hardware vendor and product information."""
        pass

    @abstractmethod
    def get_platform_profile(self) -> PlatformProfileInfo:
        """Query ACPI thermal/power platform profile state."""
        pass

    @abstractmethod
    def set_platform_profile(self, profile: str) -> bool:
        """Set ACPI platform profile."""
        pass

    @abstractmethod
    def get_battery_conservation(self) -> BatteryHealthInfo:
        """Query battery threshold status."""
        pass

    @abstractmethod
    def set_battery_conservation(self, enabled: bool) -> bool:
        """Apply battery charge limit threshold."""
        pass

    @abstractmethod
    def get_gpu_power_status(self) -> Dict[str, Any]:
        """Query discrete GPU power and runtime status."""
        pass

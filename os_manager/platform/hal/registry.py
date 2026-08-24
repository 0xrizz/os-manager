"""Hardware Registry and Active Driver Discovery Engine."""

from pathlib import Path
from typing import List, Optional

from os_manager.config.schema import HardwareConfig

from .asus import AsusDriver
from .base import AbstractHardwareDriver
from .dell import DellDriver
from .generic_linux import GenericLinuxDriver
from .lenovo import LenovoDriver
from .macos import DarwinDriver
from .thinkpad import ThinkPadDriver


class HardwareRegistry:
    """Maintains active hardware drivers and resolves target platform driver."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        self.sysfs_root = sysfs_root
        self._drivers: List[AbstractHardwareDriver] = [
            DarwinDriver(sysfs_root=sysfs_root),
            LenovoDriver(sysfs_root=sysfs_root),
            ThinkPadDriver(sysfs_root=sysfs_root),
            AsusDriver(sysfs_root=sysfs_root),
            DellDriver(sysfs_root=sysfs_root),
            GenericLinuxDriver(sysfs_root=sysfs_root),
        ]

    def resolve(self, config: Optional[HardwareConfig] = None) -> AbstractHardwareDriver:
        """Resolve active hardware driver respecting config overrides and runtime probes."""
        cfg = config or HardwareConfig()

        if cfg.force_override and cfg.driver != "auto":
            driver_map = {
                "lenovo": LenovoDriver,
                "thinkpad": ThinkPadDriver,
                "asus": AsusDriver,
                "dell": DellDriver,
                "macos": DarwinDriver,
                "generic": GenericLinuxDriver,
            }
            target_cls = driver_map.get(cfg.driver.lower(), GenericLinuxDriver)
            return target_cls(sysfs_root=self.sysfs_root)

        for driver in self._drivers:
            if driver.probe():
                return driver

        return GenericLinuxDriver(sysfs_root=self.sysfs_root)


def get_active_hardware_driver(
    config: Optional[HardwareConfig] = None, sysfs_root: Optional[Path] = None
) -> AbstractHardwareDriver:
    """Convenience function returning resolved active hardware driver instance."""
    registry = HardwareRegistry(sysfs_root=sysfs_root)
    return registry.resolve(config)

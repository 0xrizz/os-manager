"""ASUS Laptop Hardware Driver (asus-nb-wmi / asus_wmi)."""

from pathlib import Path
from typing import Optional

from .generic_linux import GenericLinuxDriver


class AsusDriver(GenericLinuxDriver):
    """Driver for ASUS consumer and ROG laptops utilizing asus_wmi."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        super().__init__(sysfs_root=sysfs_root)
        self.asus_wmi_dir = (
            self.sysfs_root / "sys" / "devices" / "platform" / "asus-nb-wmi"
        )
        self.throttle_profile = self.asus_wmi_dir / "throttle_thermal_policy"

    def probe(self) -> bool:
        return self.asus_wmi_dir.is_dir()

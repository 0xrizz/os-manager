"""Dell Laptop Hardware Driver (dell_laptop / dell_smbios)."""

from pathlib import Path
from typing import Optional

from .generic_linux import GenericLinuxDriver


class DellDriver(GenericLinuxDriver):
    """Driver for Dell XPS/Latitude laptops utilizing dell_smbios."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        super().__init__(sysfs_root=sysfs_root)
        self.dell_dir = (
            self.sysfs_root / "sys" / "devices" / "platform" / "dell-laptop"
        )

    def probe(self) -> bool:
        return self.dell_dir.is_dir()

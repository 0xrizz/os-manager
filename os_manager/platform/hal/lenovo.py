"""Lenovo IdeaPad and Yoga Hardware Driver (ideapad_acpi)."""

from pathlib import Path
from typing import Optional

from .base import BatteryHealthInfo
from .generic_linux import GenericLinuxDriver


class LenovoDriver(GenericLinuxDriver):
    """Driver for Lenovo IdeaPad/Yoga laptops utilizing ideapad_acpi."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        super().__init__(sysfs_root=sysfs_root)
        self.ideapad_dir = (
            self.sysfs_root
            / "sys"
            / "bus"
            / "platform"
            / "drivers"
            / "ideapad_acpi"
            / "VPC2004:00"
        )
        self.conservation_file = self.ideapad_dir / "conservation_mode"
        self.fn_lock_file = self.ideapad_dir / "fn_lock"

    def probe(self) -> bool:
        return self.conservation_file.exists() or self.ideapad_dir.is_dir()

    def get_battery_conservation(self) -> BatteryHealthInfo:
        if self.conservation_file.exists():
            val = self._read_sysfs(self.conservation_file, "0")
            is_enabled = val == "1"
            return BatteryHealthInfo(
                supported=True,
                conservation_mode=is_enabled,
                threshold=60 if is_enabled else 100,
            )
        return super().get_battery_conservation()

    def set_battery_conservation(self, enabled: bool) -> bool:
        if self.conservation_file.exists():
            try:
                self.conservation_file.write_text("1\n" if enabled else "0\n", encoding="utf-8")
                return True
            except Exception:
                return False
        return super().set_battery_conservation(enabled)

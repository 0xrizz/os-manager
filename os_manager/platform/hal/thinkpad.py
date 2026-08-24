"""Lenovo ThinkPad Hardware Driver (thinkpad_acpi)."""

from pathlib import Path
from typing import Optional

from .base import BatteryHealthInfo
from .generic_linux import GenericLinuxDriver


class ThinkPadDriver(GenericLinuxDriver):
    """Driver for Lenovo ThinkPad laptops utilizing thinkpad_acpi."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        super().__init__(sysfs_root=sysfs_root)
        self.thinkpad_dir = (
            self.sysfs_root / "sys" / "devices" / "platform" / "thinkpad_acpi"
        )

    def probe(self) -> bool:
        return self.thinkpad_dir.is_dir()

    def get_battery_conservation(self) -> BatteryHealthInfo:
        if not self.power_supply_dir.is_dir():
            return super().get_battery_conservation()

        for bat in self.power_supply_dir.glob("BAT*"):
            stop_file = bat / "charge_stop_threshold"
            if stop_file.exists():
                val = int(self._read_sysfs(stop_file, "100"))
                return BatteryHealthInfo(
                    supported=True,
                    conservation_mode=(val < 100),
                    threshold=val,
                )
        return super().get_battery_conservation()

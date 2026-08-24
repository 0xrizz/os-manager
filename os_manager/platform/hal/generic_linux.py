"""Generic Linux ACPI and Sysfs Hardware Driver."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
    PlatformProfileInfo,
)


class GenericLinuxDriver(AbstractHardwareDriver):
    """Fallback driver utilizing standard ACPI sysfs and power supply classes."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        super().__init__(sysfs_root=sysfs_root)
        self.acpi_profile_path = self.sysfs_root / "sys" / "firmware" / "acpi" / "platform_profile"
        self.acpi_choices_path = self.sysfs_root / "sys" / "firmware" / "acpi" / "platform_profile_choices"
        self.dmi_dir = self.sysfs_root / "sys" / "class" / "dmi" / "id"
        self.power_supply_dir = self.sysfs_root / "sys" / "class" / "power_supply"

    def probe(self) -> bool:
        """Generic driver probes True if standard ACPI profile or DMI nodes exist."""
        return self.acpi_profile_path.exists() or self.dmi_dir.exists()

    def get_dmi_info(self) -> DmiInfo:
        vendor = self._read_sysfs(self.dmi_dir / "sys_vendor", "Unknown")
        product = self._read_sysfs(self.dmi_dir / "product_name", "Unknown")
        family = self._read_sysfs(self.dmi_dir / "product_family", "Unknown")
        bios = self._read_sysfs(self.dmi_dir / "bios_version", "Unknown")
        return DmiInfo(vendor=vendor, product_name=product, family=family, bios_version=bios)

    def get_platform_profile(self) -> PlatformProfileInfo:
        if not self.acpi_profile_path.exists():
            return PlatformProfileInfo(supported=False)

        current = self._read_sysfs(self.acpi_profile_path, "unsupported")
        choices_raw = self._read_sysfs(self.acpi_choices_path, "")
        choices = choices_raw.split() if choices_raw else []

        return PlatformProfileInfo(supported=True, current=current, choices=choices)

    def set_platform_profile(self, profile: str) -> bool:
        info = self.get_platform_profile()
        if not info.supported:
            return False

        if info.choices and profile not in info.choices:
            raise ValueError(f"Profile '{profile}' not in available choices: {info.choices}")

        try:
            self.acpi_profile_path.write_text(profile.strip() + "\n", encoding="utf-8")
            return True
        except Exception:
            return False

    def get_battery_conservation(self) -> BatteryHealthInfo:
        if not self.power_supply_dir.is_dir():
            return BatteryHealthInfo(supported=False)

        for bat in self.power_supply_dir.glob("BAT*"):
            threshold_file = bat / "charge_control_end_threshold"
            if threshold_file.exists():
                val = int(self._read_sysfs(threshold_file, "100"))
                return BatteryHealthInfo(
                    supported=True,
                    conservation_mode=(val < 100),
                    threshold=val,
                )
        return BatteryHealthInfo(supported=False)

    def set_battery_conservation(self, enabled: bool) -> bool:
        target_val = "80\n" if enabled else "100\n"
        applied = False

        if not self.power_supply_dir.is_dir():
            return False

        for bat in self.power_supply_dir.glob("BAT*"):
            threshold_file = bat / "charge_control_end_threshold"
            if threshold_file.exists():
                try:
                    threshold_file.write_text(target_val, encoding="utf-8")
                    applied = True
                except Exception:
                    pass
        return applied

    def get_gpu_power_status(self) -> Dict[str, Any]:
        pci_dir = self.sysfs_root / "sys" / "bus" / "pci" / "devices"
        if not pci_dir.is_dir():
            return {"supported": False, "status": "unknown"}

        for dev in pci_dir.iterdir():
            ctrl = dev / "power" / "control"
            runtime = dev / "power" / "runtime_status"
            if ctrl.exists() and runtime.exists():
                return {
                    "supported": True,
                    "device": dev.name,
                    "control": self._read_sysfs(ctrl, "unknown"),
                    "runtime_status": self._read_sysfs(runtime, "unknown"),
                }
        return {"supported": False, "status": "unknown"}

    def _read_sysfs(self, path: Path, default: str) -> str:
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8").strip()
        except Exception:
            pass
        return default

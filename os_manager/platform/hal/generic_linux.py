"""Generic Linux ACPI and Sysfs Hardware Driver."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
    GpuDeviceInfo,
    GpuSubsystemInfo,
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

    def audit_gpu_subsystem(self) -> GpuSubsystemInfo:
        """Scan sysfs PCI bus for Display/3D controller devices and classify iGPU vs dGPU."""
        pci_dir = self.sysfs_root / "sys" / "bus" / "pci" / "devices"
        if not pci_dir.is_dir():
            return GpuSubsystemInfo(driver_flavor="none")

        vendor_map = {
            "0x8086": "Intel",
            "0x10de": "NVIDIA",
            "0x1002": "AMD",
        }

        primary_gpu: Optional[GpuDeviceInfo] = None
        discrete_gpu: Optional[GpuDeviceInfo] = None

        # Sort device directories to ensure deterministic ordering
        for dev_path in sorted(pci_dir.iterdir()):
            if not dev_path.is_dir():
                continue

            class_file = dev_path / "class"
            if not class_file.is_file():
                continue

            class_code = self._read_sysfs(class_file, "").lower()
            # 0x030000 = VGA compatible controller
            # 0x030200 = 3D controller
            # 0x038000 = Display controller
            if not (
                class_code.startswith("0x0300")
                or class_code.startswith("0x0302")
                or class_code.startswith("0x0380")
            ):
                continue

            vendor_code = self._read_sysfs(dev_path / "vendor", "").lower()
            vendor_name = vendor_map.get(vendor_code, "Unknown")
            device_code = self._read_sysfs(dev_path / "device", "")

            # Check driver in use via symlink
            driver_link = dev_path / "driver"
            driver_in_use = driver_link.resolve().name if driver_link.exists() else "none"

            # Power state
            runtime_status = self._read_sysfs(dev_path / "power" / "runtime_status", "unsupported")

            # Determine if discrete:
            # 3D controller (0x0302xx) is typically dGPU (e.g. NVIDIA Optimus)
            # Non-primary PCI bus (e.g. bus != 00) or NVIDIA/AMD secondary
            is_discrete = (
                class_code.startswith("0x0302")
                or vendor_name == "NVIDIA"
                or not dev_path.name.startswith("0000:00:")
            )

            gpu_info = GpuDeviceInfo(
                vendor=vendor_name,
                device_name=f"{vendor_name} ({device_code})" if device_code else vendor_name,
                pci_slot=dev_path.name,
                driver_in_use=driver_in_use,
                is_discrete=is_discrete,
                power_state=runtime_status,
                vaapi_supported=(vendor_name == "Intel" or vendor_name == "AMD"),
                cuda_supported=(vendor_name == "NVIDIA"),
            )

            if is_discrete:
                if discrete_gpu is None:
                    discrete_gpu = gpu_info
            else:
                if primary_gpu is None:
                    primary_gpu = gpu_info

        # If only discrete was found and no primary, assign primary
        if primary_gpu is None and discrete_gpu is not None:
            # Check if only one GPU in system
            pass

        active_profile = "hybrid" if (primary_gpu and discrete_gpu) else ("discrete" if discrete_gpu else "integrated")
        driver_flavor = "nvidia" if (discrete_gpu and discrete_gpu.vendor == "NVIDIA") else "mesa"

        return GpuSubsystemInfo(
            primary_display_gpu=primary_gpu,
            discrete_gpu=discrete_gpu,
            active_profile=active_profile,
            driver_flavor=driver_flavor,
        )

    def _read_sysfs(self, path: Path, default: str) -> str:
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8").strip()
        except Exception:
            pass
        return default

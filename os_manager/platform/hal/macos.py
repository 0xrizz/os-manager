"""macOS Darwin Hardware and Power Management Driver."""

from pathlib import Path
import platform
import subprocess
from typing import Any, Dict, Optional

from .base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
    GpuDeviceInfo,
    GpuSubsystemInfo,
    PlatformProfileInfo,
)


class DarwinDriver(AbstractHardwareDriver):
    """Driver for macOS operating systems using pmset and sysctl."""

    def probe(self) -> bool:
        return platform.system() == "Darwin"

    def get_dmi_info(self) -> DmiInfo:
        model = "Apple Mac"
        try:
            res = subprocess.run(["sysctl", "-n", "hw.model"], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                model = res.stdout.strip()
        except Exception:
            pass
        return DmiInfo(vendor="Apple Inc.", product_name=model, family="Macintosh")

    def get_platform_profile(self) -> PlatformProfileInfo:
        return PlatformProfileInfo(supported=True, current="default", choices=["default", "lowpower"])

    def set_platform_profile(self, profile: str) -> bool:
        return True

    def get_battery_conservation(self) -> BatteryHealthInfo:
        return BatteryHealthInfo(supported=False)

    def set_battery_conservation(self, enabled: bool) -> bool:
        return False

    def get_gpu_power_status(self) -> Dict[str, Any]:
        return {"supported": False, "status": "integrated"}

    def audit_gpu_subsystem(self) -> GpuSubsystemInfo:
        return GpuSubsystemInfo(
            primary_display_gpu=GpuDeviceInfo(
                vendor="Apple",
                device_name="Apple Silicon Integrated GPU",
                is_discrete=False,
                power_state="active",
            ),
            active_profile="integrated",
            driver_flavor="native",
        )

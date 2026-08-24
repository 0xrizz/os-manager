"""Unit tests for AbstractHardwareDriver interface and data models."""

from dataclasses import asdict
from pathlib import Path
import unittest

from os_manager.platform.hal.base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
    PlatformProfileInfo,
)


class MockDriver(AbstractHardwareDriver):
    """Mock concrete implementation for testing interface contract."""

    def __init__(self, sysfs_root: Path | None = None) -> None:
        super().__init__(sysfs_root=sysfs_root)

    def probe(self) -> bool:
        return True

    def get_dmi_info(self) -> DmiInfo:
        return DmiInfo(vendor="MockVendor", product_name="MockModel", family="MockFamily", bios_version="v1.0")

    def get_platform_profile(self) -> PlatformProfileInfo:
        return PlatformProfileInfo(supported=True, current="balanced", choices=["performance", "balanced", "low-power"])

    def set_platform_profile(self, profile: str) -> bool:
        return profile in ["performance", "balanced", "low-power"]

    def get_battery_conservation(self) -> BatteryHealthInfo:
        return BatteryHealthInfo(supported=True, conservation_mode=True, threshold=80, health_percent=95.0)

    def set_battery_conservation(self, enabled: bool) -> bool:
        return True

    def get_gpu_power_status(self) -> dict:
        return {"status": "suspended"}


class TestHalBase(unittest.TestCase):
    """Verify HAL base interface contract enforcement."""

    def test_mock_driver_instantiation(self) -> None:
        driver = MockDriver()
        self.assertTrue(driver.probe())
        dmi = driver.get_dmi_info()
        self.assertEqual(dmi.vendor, "MockVendor")

        prof = driver.get_platform_profile()
        self.assertTrue(prof.supported)
        self.assertEqual(prof.current, "balanced")
        self.assertIn("performance", prof.choices)

        bat = driver.get_battery_conservation()
        self.assertTrue(bat.conservation_mode)
        self.assertEqual(bat.threshold, 80)

    def test_cannot_instantiate_abstract_base(self) -> None:
        with self.assertRaises(TypeError):
            AbstractHardwareDriver()  # type: ignore


if __name__ == "__main__":
    unittest.main()

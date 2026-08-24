"""Unit tests for specialized vendor hardware drivers (Lenovo, Asus, Dell, Darwin)."""

from pathlib import Path
import tempfile
import unittest

from os_manager.platform.hal.asus import AsusDriver
from os_manager.platform.hal.dell import DellDriver
from os_manager.platform.hal.lenovo import LenovoDriver
from os_manager.platform.hal.macos import DarwinDriver
from os_manager.platform.hal.thinkpad import ThinkPadDriver


class TestVendorDrivers(unittest.TestCase):
    """Verify vendor driver probe logic and specialized sysfs handling."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.test_dir.name)

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_lenovo_ideapad_driver_probe_and_conservation(self) -> None:
        ideapad_dir = self.root / "sys" / "bus" / "platform" / "drivers" / "ideapad_acpi" / "VPC2004:00"
        ideapad_dir.mkdir(parents=True, exist_ok=True)
        (ideapad_dir / "conservation_mode").write_text("1\n", encoding="utf-8")

        driver = LenovoDriver(sysfs_root=self.root)
        self.assertTrue(driver.probe())

        bat = driver.get_battery_conservation()
        self.assertTrue(bat.supported)
        self.assertTrue(bat.conservation_mode)
        self.assertEqual(bat.threshold, 60)

        driver.set_battery_conservation(False)
        self.assertEqual((ideapad_dir / "conservation_mode").read_text().strip(), "0")

    def test_thinkpad_driver_probe_and_thresholds(self) -> None:
        tp_dir = self.root / "sys" / "devices" / "platform" / "thinkpad_acpi"
        tp_dir.mkdir(parents=True, exist_ok=True)
        bat_dir = self.root / "sys" / "class" / "power_supply" / "BAT0"
        bat_dir.mkdir(parents=True, exist_ok=True)
        (bat_dir / "charge_stop_threshold").write_text("80\n", encoding="utf-8")

        driver = ThinkPadDriver(sysfs_root=self.root)
        self.assertTrue(driver.probe())
        bat = driver.get_battery_conservation()
        self.assertTrue(bat.supported)
        self.assertEqual(bat.threshold, 80)

    def test_asus_driver_probe(self) -> None:
        asus_dir = self.root / "sys" / "devices" / "platform" / "asus-nb-wmi"
        asus_dir.mkdir(parents=True, exist_ok=True)

        driver = AsusDriver(sysfs_root=self.root)
        self.assertTrue(driver.probe())

    def test_dell_driver_probe(self) -> None:
        dell_dir = self.root / "sys" / "devices" / "platform" / "dell-laptop"
        dell_dir.mkdir(parents=True, exist_ok=True)

        driver = DellDriver(sysfs_root=self.root)
        self.assertTrue(driver.probe())

    def test_darwin_driver_methods(self) -> None:
        driver = DarwinDriver(sysfs_root=self.root)
        self.assertIsInstance(driver.probe(), bool)
        dmi = driver.get_dmi_info()
        self.assertEqual(dmi.vendor, "Apple Inc.")
        self.assertEqual(dmi.family, "Macintosh")
        profile = driver.get_platform_profile()
        self.assertTrue(profile.supported)
        self.assertEqual(profile.current, "default")
        self.assertTrue(driver.set_platform_profile("default"))
        bat = driver.get_battery_conservation()
        self.assertFalse(bat.supported)
        self.assertFalse(driver.set_battery_conservation(True))
        gpu = driver.get_gpu_power_status()
        self.assertFalse(gpu["supported"])


if __name__ == "__main__":
    unittest.main()

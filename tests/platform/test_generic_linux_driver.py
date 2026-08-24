"""Unit tests for Generic Linux ACPI HAL driver with mock sysfs fixtures."""

from pathlib import Path
import tempfile
import unittest

from os_manager.platform.hal.generic_linux import GenericLinuxDriver


class TestGenericLinuxDriver(unittest.TestCase):
    """Test GenericLinuxDriver against mock sysfs trees."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.test_dir.name)

        # Build mock sysfs structure
        self.dmi_dir = self.root / "sys" / "class" / "dmi" / "id"
        self.dmi_dir.mkdir(parents=True, exist_ok=True)
        (self.dmi_dir / "sys_vendor").write_text("GenericCorp\n", encoding="utf-8")
        (self.dmi_dir / "product_name").write_text("GenericLaptop 2026\n", encoding="utf-8")

        self.acpi_dir = self.root / "sys" / "firmware" / "acpi"
        self.acpi_dir.mkdir(parents=True, exist_ok=True)
        (self.acpi_dir / "platform_profile").write_text("balanced\n", encoding="utf-8")
        (self.acpi_dir / "platform_profile_choices").write_text("performance balanced low-power\n", encoding="utf-8")

        self.bat_dir = self.root / "sys" / "class" / "power_supply" / "BAT0"
        self.bat_dir.mkdir(parents=True, exist_ok=True)
        (self.bat_dir / "charge_control_end_threshold").write_text("100\n", encoding="utf-8")

        self.driver = GenericLinuxDriver(sysfs_root=self.root)

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_probe_success_with_acpi_profile(self) -> None:
        self.assertTrue(self.driver.probe())

    def test_dmi_info_resolution(self) -> None:
        dmi = self.driver.get_dmi_info()
        self.assertEqual(dmi.vendor, "GenericCorp")
        self.assertEqual(dmi.product_name, "GenericLaptop 2026")

    def test_platform_profile_get_and_set(self) -> None:
        prof = self.driver.get_platform_profile()
        self.assertTrue(prof.supported)
        self.assertEqual(prof.current, "balanced")
        self.assertEqual(prof.choices, ["performance", "balanced", "low-power"])

        success = self.driver.set_platform_profile("performance")
        self.assertTrue(success)
        new_prof = self.driver.get_platform_profile()
        self.assertEqual(new_prof.current, "performance")

    def test_battery_conservation_control(self) -> None:
        bat = self.driver.get_battery_conservation()
        self.assertTrue(bat.supported)
        self.assertEqual(bat.threshold, 100)

        self.driver.set_battery_conservation(True)
        updated_bat = self.driver.get_battery_conservation()
        self.assertEqual(updated_bat.threshold, 80)


if __name__ == "__main__":
    unittest.main()

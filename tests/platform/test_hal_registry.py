"""Unit tests for HardwareRegistry driver resolution and Storage Profiler."""

from pathlib import Path
import tempfile
import unittest

from os_manager.config.schema import HardwareConfig
from os_manager.platform.hal.generic_linux import GenericLinuxDriver
from os_manager.platform.hal.lenovo import LenovoDriver
from os_manager.platform.hal.registry import (
    HardwareRegistry,
    get_active_hardware_driver,
)
from os_manager.platform.hal.storage import audit_storage_subsystem


class TestHalRegistryAndStorage(unittest.TestCase):
    """Verify dynamic driver resolution and non-destructive storage auditing."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.test_dir.name)

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_registry_resolves_lenovo_when_sysfs_present(self) -> None:
        ideapad_dir = self.root / "sys" / "bus" / "platform" / "drivers" / "ideapad_acpi" / "VPC2004:00"
        ideapad_dir.mkdir(parents=True, exist_ok=True)
        (ideapad_dir / "conservation_mode").write_text("1\n", encoding="utf-8")

        driver = get_active_hardware_driver(sysfs_root=self.root)
        self.assertIsInstance(driver, LenovoDriver)

    def test_registry_fallback_to_generic_linux(self) -> None:
        # Create minimal generic DMI node
        dmi = self.root / "sys" / "class" / "dmi" / "id"
        dmi.mkdir(parents=True, exist_ok=True)
        (dmi / "sys_vendor").write_text("GenericOEM\n", encoding="utf-8")

        driver = get_active_hardware_driver(sysfs_root=self.root)
        self.assertIsInstance(driver, GenericLinuxDriver)

    def test_forced_driver_override_in_config(self) -> None:
        cfg = HardwareConfig(driver="generic", force_override=True)
        driver = get_active_hardware_driver(config=cfg, sysfs_root=self.root)
        self.assertIsInstance(driver, GenericLinuxDriver)

    def test_storage_subsystem_audit(self) -> None:
        info = audit_storage_subsystem("/")
        self.assertIsNotNone(info.target_device)
        self.assertIsInstance(info.is_nvme, bool)


if __name__ == "__main__":
    unittest.main()

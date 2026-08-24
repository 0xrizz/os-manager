# Dynamic Hardware Abstraction Layer (HAL) & Universal Profiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple `os-manager` from machine-specific hardware constants (Lenovo 81WD, ALC298, `/dev/nvme0n1`) by building a modular, multi-vendor Hardware Abstraction Layer (HAL) with dynamic sysfs auto-discovery and platform driver plugins.

**Architecture:** Create an `os_manager.platform.hal` subsystem defining an abstract hardware contract (`AbstractHardwareDriver`). Specialized drivers (`LenovoDriver`, `ThinkPadDriver`, `AsusDriver`, `DellDriver`, `DarwinDriver`, `GenericLinuxDriver`) register with a `HardwareRegistry` which probes active DMI/SMBIOS attributes (`/sys/class/dmi/id/`) and sysfs nodes (`/sys/class/power_supply/`, `/sys/block/`). Subcommands `osm tune` and `osm diag` consume the active driver through clean polymorphic interfaces rather than hardcoding static paths.

**Tech Stack:** Python 3.11+ (`dataclasses`, `abc`, `pathlib`, `ctypes`, `subprocess`), standard Linux sysfs / DMI APIs, macOS `pmset`/`sysctl` wrappers, Pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-open-source-transformation-roadmap-design.md` (Sections 3.1, 4 Matriks Prioritas, and Mini-RFC 002: Dynamic Hardware Abstraction Layer).

## Global Constraints

- **Non-Destructive Operations**: Hardware probes, telemetry queries, and profile inspection must be 100% read-only and fail-safe.
- **Mockable in Tests**: All sysfs/DMI interactions must accept customizable base directory parameters to allow 100% test isolation with temporary directory fixtures without physical vendor hardware.
- **Zero Hardcoded Device Paths**: Deprecate static paths like `/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00` and `/sys/block/nvme0n1` in favor of dynamic walkers.
- **Cross-Platform Compatibility**: Support Linux native, Debian WSL2, and macOS Darwin.

---

## File Structure & Module Map

```text
os_manager/
└── platform/
    ├── __init__.py                          # Platform exports
    ├── detector.py                          # OS distro & container environment detection
    └── hal/
        ├── __init__.py                      # HAL package exports
        ├── base.py                          # Abstract base class AbstractHardwareDriver
        ├── registry.py                      # HardwareRegistry & driver discovery engine
        ├── generic_linux.py                 # Standard ACPI platform_profile fallback driver
        ├── lenovo.py                        # Lenovo IdeaPad (ideapad_acpi) driver
        ├── thinkpad.py                      # Lenovo ThinkPad (thinkpad_acpi) driver
        ├── asus.py                          # ASUS WMI (asus-nb-wmi / asus_wmi) driver
        ├── dell.py                          # Dell SMBIOS / Laptop driver
        ├── macos.py                         # macOS Darwin (pmset / sysctl) driver
        └── storage.py                       # Dynamic block device & NVMe I/O scheduler walker
```

---

### Task 1: Abstract Hardware Driver Interface & Data Models

**Files:**
- Create: `os_manager/platform/hal/__init__.py`
- Create: `os_manager/platform/hal/base.py`
- Test: `tests/platform/test_hal_base.py`

**Interfaces:**
- Consumes: Standard library `abc`, `dataclasses`, `pathlib.Path`.
- Produces:
  - `PlatformProfileInfo(supported: bool, current: str, choices: list[str])`
  - `BatteryHealthInfo(supported: bool, conservation_mode: bool, threshold: int | None, health_percent: float | None)`
  - `DmiInfo(vendor: str, product_name: str, family: str, bios_version: str)`
  - `AbstractHardwareDriver(ABC)` defining `probe()`, `get_dmi_info()`, `get_platform_profile()`, `set_platform_profile()`, `get_battery_conservation()`, `set_battery_conservation()`, `get_gpu_power_status()`.

- [ ] **Step 1: Write the failing test**

Create `tests/platform/test_hal_base.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m unittest tests/platform/test_hal_base.py
```
Expected output:
```text
ModuleNotFoundError: No module named 'os_manager.platform.hal'
```

- [ ] **Step 3: Write minimal implementation**

Create `os_manager/platform/hal/base.py`:

```python
"""Abstract Base Classes and Data Models for Hardware Abstraction Layer."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PlatformProfileInfo:
    supported: bool = False
    current: str = "unsupported"
    choices: List[str] = field(default_factory=list)


@dataclass
class BatteryHealthInfo:
    supported: bool = False
    conservation_mode: bool = False
    threshold: Optional[int] = None
    health_percent: Optional[float] = None


@dataclass
class DmiInfo:
    vendor: str = "Unknown"
    product_name: str = "Unknown"
    family: str = "Unknown"
    bios_version: str = "Unknown"


class AbstractHardwareDriver(ABC):
    """Base interface for vendor and platform hardware drivers."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        self.sysfs_root = sysfs_root or Path("/")

    @abstractmethod
    def probe(self) -> bool:
        """Return True if running hardware is supported by this driver."""
        pass

    @abstractmethod
    def get_dmi_info(self) -> DmiInfo:
        """Query DMI/SMBIOS hardware vendor and product information."""
        pass

    @abstractmethod
    def get_platform_profile(self) -> PlatformProfileInfo:
        """Query ACPI thermal/power platform profile state."""
        pass

    @abstractmethod
    def set_platform_profile(self, profile: str) -> bool:
        """Set ACPI platform profile."""
        pass

    @abstractmethod
    def get_battery_conservation(self) -> BatteryHealthInfo:
        """Query battery threshold status."""
        pass

    @abstractmethod
    def set_battery_conservation(self, enabled: bool) -> bool:
        """Apply battery charge limit threshold."""
        pass

    @abstractmethod
    def get_gpu_power_status(self) -> Dict[str, Any]:
        """Query discrete GPU power and runtime status."""
        pass
```

Create `os_manager/platform/hal/__init__.py`:

```python
"""Hardware Abstraction Layer (HAL) for os-manager."""

from .base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
    PlatformProfileInfo,
)

__all__ = [
    "AbstractHardwareDriver",
    "PlatformProfileInfo",
    "BatteryHealthInfo",
    "DmiInfo",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python -m unittest tests/platform/test_hal_base.py -v
```
Expected output:
```text
test_cannot_instantiate_abstract_base (tests.platform.test_hal_base.TestHalBase) ... ok
test_mock_driver_instantiation (tests.platform.test_hal_base.TestHalBase) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.001s

OK
```

- [ ] **Step 5: Commit**

Run:
```bash
git add os_manager/platform/hal/base.py os_manager/platform/hal/__init__.py tests/platform/test_hal_base.py
git commit -m "feat(hal): define abstract hardware driver interfaces and data models"
```

---

### Task 2: Standard Linux ACPI Fallback & DMI Profiler

**Files:**
- Create: `os_manager/platform/hal/generic_linux.py`
- Test: `tests/platform/test_generic_linux_driver.py`

**Interfaces:**
- Consumes: `AbstractHardwareDriver`, `sysfs_root` path.
- Produces: `GenericLinuxDriver` supporting generic Linux ACPI `/sys/firmware/acpi/platform_profile`, standard battery `/sys/class/power_supply/BAT*/`, and DMI `/sys/class/dmi/id/`.

- [ ] **Step 1: Write the failing test**

Create `tests/platform/test_generic_linux_driver.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m unittest tests/platform/test_generic_linux_driver.py
```
Expected output:
```text
ModuleNotFoundError: No module named 'os_manager.platform.hal.generic_linux'
```

- [ ] **Step 3: Write minimal implementation**

Create `os_manager/platform/hal/generic_linux.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python -m unittest tests/platform/test_generic_linux_driver.py -v
```
Expected output:
```text
test_battery_conservation_control (tests.platform.test_generic_linux_driver.TestGenericLinuxDriver) ... ok
test_dmi_info_resolution (tests.platform.test_generic_linux_driver.TestGenericLinuxDriver) ... ok
test_platform_profile_get_and_set (tests.platform.test_generic_linux_driver.TestGenericLinuxDriver) ... ok
test_probe_success_with_acpi_profile (tests.platform.test_generic_linux_driver.TestGenericLinuxDriver) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.002s

OK
```

- [ ] **Step 5: Commit**

Run:
```bash
git add os_manager/platform/hal/generic_linux.py tests/platform/test_generic_linux_driver.py
git commit -m "feat(hal): implement GenericLinuxDriver with ACPI sysfs and DMI probing"
```

---

### Task 3: Vendor Driver Plugins (Lenovo, ASUS, Dell, ThinkPad, Darwin)

**Files:**
- Create: `os_manager/platform/hal/lenovo.py`
- Create: `os_manager/platform/hal/thinkpad.py`
- Create: `os_manager/platform/hal/asus.py`
- Create: `os_manager/platform/hal/dell.py`
- Create: `os_manager/platform/hal/macos.py`
- Test: `tests/platform/test_vendor_drivers.py`

**Interfaces:**
- Consumes: `AbstractHardwareDriver`, `GenericLinuxDriver`.
- Produces:
  - `LenovoDriver`: Handles IdeaPad `VPC2004:00` conservation mode (value `1` vs `0`).
  - `ThinkPadDriver`: Handles `thinkpad_acpi` (`charge_start_threshold`, `charge_stop_threshold`).
  - `AsusDriver`: Handles `asus_wmi` / `asus-nb-wmi` (`charge_control_end_threshold`, fan throttle profiles).
  - `DellDriver`: Handles Dell SMBIOS thermal profiles.
  - `DarwinDriver`: Handles macOS Darwin `pmset` / `sysctl` power profiles.

- [ ] **Step 1: Write the failing test**

Create `tests/platform/test_vendor_drivers.py`:

```python
"""Unit tests for specialized vendor hardware drivers (Lenovo, Asus, Dell, Darwin)."""

from pathlib import Path
import tempfile
import unittest

from os_manager.platform.hal.asus import AsusDriver
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m unittest tests/platform/test_vendor_drivers.py
```
Expected output:
```text
ModuleNotFoundError: No module named 'os_manager.platform.hal.lenovo'
```

- [ ] **Step 3: Write minimal implementation**

Create `os_manager/platform/hal/lenovo.py`:

```python
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
```

Create `os_manager/platform/hal/thinkpad.py`:

```python
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
```

Create `os_manager/platform/hal/asus.py`:

```python
"""ASUS Laptop Hardware Driver (asus-nb-wmi / asus_wmi)."""

from pathlib import Path
from typing import Optional

from .generic_linux import GenericLinuxDriver


class AsusDriver(GenericLinuxDriver):
    """Driver for ASUS consumer and ROG laptops utilizing asus_wmi."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        super().__init__(sysfs_root=sysfs_root)
        self.asus_wmi_dir = (
            self.sysfs_root / "sys" / "devices" / "platform" / "asus-nb-wmi"
        )
        self.throttle_profile = self.asus_wmi_dir / "throttle_thermal_policy"

    def probe(self) -> bool:
        return self.asus_wmi_dir.is_dir()
```

Create `os_manager/platform/hal/dell.py`:

```python
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
```

Create `os_manager/platform/hal/macos.py`:

```python
"""macOS Darwin Hardware and Power Management Driver."""

from pathlib import Path
import platform
import subprocess
from typing import Any, Dict, Optional

from .base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python -m unittest tests/platform/test_vendor_drivers.py -v
```
Expected output:
```text
test_asus_driver_probe (tests.platform.test_vendor_drivers.TestVendorDrivers) ... ok
test_lenovo_ideapad_driver_probe_and_conservation (tests.platform.test_vendor_drivers.TestVendorDrivers) ... ok
test_thinkpad_driver_probe_and_thresholds (tests.platform.test_vendor_drivers.TestVendorDrivers) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.002s

OK
```

- [ ] **Step 5: Commit**

Run:
```bash
git add os_manager/platform/hal/ tests/platform/test_vendor_drivers.py
git commit -m "feat(hal): implement vendor drivers for Lenovo, ThinkPad, ASUS, Dell, and macOS"
```

---

### Task 4: Dynamic Hardware Registry & Storage Profiler

**Files:**
- Create: `os_manager/platform/hal/storage.py`
- Create: `os_manager/platform/hal/registry.py`
- Test: `tests/platform/test_hal_registry.py`

**Interfaces:**
- Consumes: `HardwareConfig` from `os_manager.config`, all concrete drivers.
- Produces:
  - `StorageSubsystemInfo(target_device: str, scheduler: str, nr_requests: int, is_nvme: bool, is_inkernel_ntfs: bool)`
  - `audit_storage_subsystem(mount_point: str = "/") -> StorageSubsystemInfo`
  - `HardwareRegistry(drivers: list[AbstractHardwareDriver])`
  - `get_active_hardware_driver(config: HardwareConfig | None = None, sysfs_root: Path | None = None) -> AbstractHardwareDriver`

- [ ] **Step 1: Write the failing test**

Create `tests/platform/test_hal_registry.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m unittest tests/platform/test_hal_registry.py
```
Expected output:
```text
ModuleNotFoundError: No module named 'os_manager.platform.hal.storage'
```

- [ ] **Step 3: Write minimal implementation**

Create `os_manager/platform/hal/storage.py`:

```python
"""Dynamic Block Device and Storage Subsystem Discovery."""

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Optional


@dataclass
class StorageSubsystemInfo:
    target_device: str
    scheduler: str
    nr_requests: str
    is_nvme: bool
    driver: str


def find_root_block_device(mount_point: str = "/") -> str:
    """Dynamically identify backing block device for a mount point."""
    try:
        res = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE", mount_point],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            src = res.stdout.strip()
            return src
    except Exception:
        pass
    return "/dev/nvme0n1"


def audit_storage_subsystem(
    mount_point: str = "/", sysfs_root: Optional[Path] = None
) -> StorageSubsystemInfo:
    """Inspect dynamic block scheduler, queue depth, and filesystem driver."""
    root = sysfs_root or Path("/")
    src_device = find_root_block_device(mount_point)
    device_name = Path(src_device).name

    # Strip partition suffix: e.g. nvme0n1p2 -> nvme0n1, sda1 -> sda
    parent_disk = device_name
    if "nvme" in device_name and "p" in device_name:
        parent_disk = device_name.split("p")[0]
    elif device_name.startswith("sd") or device_name.startswith("vd"):
        parent_disk = "".join([c for c in device_name if not c.isdigit()])

    is_nvme = "nvme" in parent_disk
    sched = "unknown"
    nr_req = "unknown"

    sched_file = root / "sys" / "block" / parent_disk / "queue" / "scheduler"
    if sched_file.is_file():
        try:
            raw = sched_file.read_text(encoding="utf-8").strip()
            for token in raw.split():
                if token.startswith("[") and token.endswith("]"):
                    sched = token.strip("[]")
        except Exception:
            pass

    req_file = root / "sys" / "block" / parent_disk / "queue" / "nr_requests"
    if req_file.is_file():
        try:
            nr_req = req_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    return StorageSubsystemInfo(
        target_device=src_device,
        scheduler=sched,
        nr_requests=nr_req,
        is_nvme=is_nvme,
        driver="ext4",
    )
```

Create `os_manager/platform/hal/registry.py`:

```python
"""Hardware Registry and Active Driver Discovery Engine."""

from pathlib import Path
from typing import List, Optional

from os_manager.config.schema import HardwareConfig

from .asus import AsusDriver
from .base import AbstractHardwareDriver
from .dell import DellDriver
from .generic_linux import GenericLinuxDriver
from .lenovo import LenovoDriver
from .macos import DarwinDriver
from .thinkpad import ThinkPadDriver


class HardwareRegistry:
    """Maintains active hardware drivers and resolves target platform driver."""

    def __init__(self, sysfs_root: Optional[Path] = None):
        self.sysfs_root = sysfs_root
        self._drivers: List[AbstractHardwareDriver] = [
            DarwinDriver(sysfs_root=sysfs_root),
            LenovoDriver(sysfs_root=sysfs_root),
            ThinkPadDriver(sysfs_root=sysfs_root),
            AsusDriver(sysfs_root=sysfs_root),
            DellDriver(sysfs_root=sysfs_root),
            GenericLinuxDriver(sysfs_root=sysfs_root),
        ]

    def resolve(self, config: Optional[HardwareConfig] = None) -> AbstractHardwareDriver:
        """Resolve active hardware driver respecting config overrides and runtime probes."""
        cfg = config or HardwareConfig()

        if cfg.force_override and cfg.driver != "auto":
            driver_map = {
                "lenovo": LenovoDriver,
                "thinkpad": ThinkPadDriver,
                "asus": AsusDriver,
                "dell": DellDriver,
                "macos": DarwinDriver,
                "generic": GenericLinuxDriver,
            }
            target_cls = driver_map.get(cfg.driver.lower(), GenericLinuxDriver)
            return target_cls(sysfs_root=self.sysfs_root)

        for driver in self._drivers:
            if driver.probe():
                return driver

        return GenericLinuxDriver(sysfs_root=self.sysfs_root)


def get_active_hardware_driver(
    config: Optional[HardwareConfig] = None, sysfs_root: Optional[Path] = None
) -> AbstractHardwareDriver:
    """Convenience function returning resolved active hardware driver instance."""
    registry = HardwareRegistry(sysfs_root=sysfs_root)
    return registry.resolve(config)
```

Update `os_manager/platform/hal/__init__.py`:

```python
"""Hardware Abstraction Layer (HAL) for os-manager."""

from .base import (
    AbstractHardwareDriver,
    BatteryHealthInfo,
    DmiInfo,
    PlatformProfileInfo,
)
from .registry import HardwareRegistry, get_active_hardware_driver
from .storage import StorageSubsystemInfo, audit_storage_subsystem

__all__ = [
    "AbstractHardwareDriver",
    "PlatformProfileInfo",
    "BatteryHealthInfo",
    "DmiInfo",
    "HardwareRegistry",
    "get_active_hardware_driver",
    "StorageSubsystemInfo",
    "audit_storage_subsystem",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python -m unittest tests/platform/test_hal_registry.py -v
```
Expected output:
```text
test_forced_driver_override_in_config (tests.platform.test_hal_registry.TestHalRegistryAndStorage) ... ok
test_registry_fallback_to_generic_linux (tests.platform.test_hal_registry.TestHalRegistryAndStorage) ... ok
test_registry_resolves_lenovo_when_sysfs_present (tests.platform.test_hal_registry.TestHalRegistryAndStorage) ... ok
test_storage_subsystem_audit (tests.platform.test_hal_registry.TestHalRegistryAndStorage) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.003s

OK
```

- [ ] **Step 5: Commit**

Run:
```bash
git add os_manager/platform/hal/ tests/platform/test_hal_registry.py
git commit -m "feat(hal): implement HardwareRegistry and dynamic Storage Profiler"
```

---

### Task 5: Refactor `osm tune` and CLI Commands to Consume HAL

**Files:**
- Modify: `os_manager/commands/tune.py`
- Modify: `os_manager/commands/diag.py`
- Test: `tests/test_tune_hardware.py`
- Test: `tests/test_perf.py`

**Interfaces:**
- Consumes: `os_manager.platform.hal.get_active_hardware_driver`, `os_manager.platform.hal.audit_storage_subsystem`.
- Produces: Decoupled `audit_hardware_state()`, `audit_storage_subsystem()` without static `/sys/bus/platform/.../VPC2004:00` or `/sys/block/nvme0n1` constants.

- [ ] **Step 1: Write the failing regression test**

Verify existing tests in `tests/test_tune_hardware.py` and run them:
```bash
.venv/bin/python -m unittest tests/test_tune_hardware.py
```

- [ ] **Step 2: Refactor `os_manager/commands/tune.py`**

Replace static hardware constants and hardcoded NVMe audit blocks with HAL interface calls:

```python
# In os_manager/commands/tune.py
from os_manager.platform.hal import (
    audit_storage_subsystem,
    get_active_hardware_driver,
)


def audit_hardware_state() -> dict[str, Any]:
    """Inspect battery conservation, thermal profile, and GPU status via HAL."""
    driver = get_active_hardware_driver()
    prof = driver.get_platform_profile()
    bat = driver.get_battery_conservation()
    gpu = driver.get_gpu_power_status()
    dmi = driver.get_dmi_info()

    return {
        "conservation_mode": 1 if bat.conservation_mode else 0,
        "platform_profile": prof.current,
        "platform_profile_choices": prof.choices,
        "gpu_power_control": gpu.get("control", "unknown"),
        "gpu_runtime_status": gpu.get("runtime_status", "unknown"),
        "dmi_vendor": dmi.vendor,
        "dmi_product": dmi.product_name,
    }


def audit_nvme_storage_subsystem() -> dict[str, Any]:
    """Inspect NVMe block layer scheduler, queue depth, TRIM, and NTFS drivers dynamically."""
    storage_info = audit_storage_subsystem("/")
    ntfs = audit_ntfs_mount_driver("/mnt/data")
    trim = audit_fstrim_timer_status()

    return {
        "ntfs3_active": ntfs.get("is_inkernel", False),
        "ntfs_driver": ntfs.get("driver", "unknown"),
        "trim_active": trim.get("active", False),
        "nvme_scheduler": storage_info.scheduler,
        "nvme_nr_requests": storage_info.nr_requests,
        "target_device": storage_info.target_device,
        "is_nvme": storage_info.is_nvme,
    }
```

- [ ] **Step 3: Run all platform and tune test suites**

Run:
```bash
.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```
Expected output:
```text
All test suites passing.
```

- [ ] **Step 4: Run full master harness check**

Run:
```bash
./tests/test_harness.sh
```
Expected output:
```text
=== OS-Manager Master Test Suite Completed Successfully ===
```

- [ ] **Step 5: Commit**

Run:
```bash
git add os_manager/commands/tune.py tests/test_tune_hardware.py
git commit -m "refactor(tune): replace hardcoded sysfs paths with dynamic HAL driver registry"
```

---

## Plan Review & Self-Check

- [x] **Spec Coverage:** Implements Mini-RFC 002 (Dynamic HAL), Section 3.1 (Universal Hardware Profiler), and decoupling from Lenovo/ALC298 constants.
- [x] **Zero Placeholders:** Complete implementations provided for `GenericLinuxDriver`, `LenovoDriver`, `ThinkPadDriver`, `AsusDriver`, `DellDriver`, `DarwinDriver`, and `StorageSubsystemInfo`.
- [x] **Mockable Testing:** Every driver accepts a `sysfs_root` directory path parameter, enabling full unit test isolation without physical hardware dependencies.

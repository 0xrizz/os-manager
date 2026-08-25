"""Unit tests to validate open-source packaging manifest syntax and paths."""

from pathlib import Path
import unittest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPackagingManifests(unittest.TestCase):
    """Verify package manifests contain correct descriptions, dependencies, and URLs."""

    def test_homebrew_formula_syntax(self) -> None:
        formula = WORKSPACE_ROOT / "packaging" / "homebrew" / "osm.rb"
        self.assertTrue(formula.is_file(), "Homebrew formula missing")
        content = formula.read_text(encoding="utf-8")
        self.assertIn("class Osm < Formula", content)
        self.assertIn("depends_on \"python@3.11\"", content)
        self.assertIn("bin.install_symlink", content)

    def test_arch_pkgbuild_syntax(self) -> None:
        pkgbuild = WORKSPACE_ROOT / "packaging" / "arch" / "PKGBUILD"
        self.assertTrue(pkgbuild.is_file(), "Arch PKGBUILD missing")
        content = pkgbuild.read_text(encoding="utf-8")
        self.assertIn("pkgname=osm-bin", content)
        self.assertIn("depends=('python'", content)
        self.assertIn("bubblewrap", content)

    def test_debian_control_syntax(self) -> None:
        control = WORKSPACE_ROOT / "packaging" / "debian" / "control"
        self.assertTrue(control.is_file(), "Debian control missing")
        content = control.read_text(encoding="utf-8")
        self.assertIn("Package: 0xrizz-os-manager", content)
        self.assertIn("Depends: python3", content)


if __name__ == "__main__":
    unittest.main()

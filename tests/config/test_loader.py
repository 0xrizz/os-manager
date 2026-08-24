"""Unit tests for declarative configuration loader and schema."""

from pathlib import Path
import tempfile
import unittest

from os_manager.config.loader import get_default_config, load_config
from os_manager.config.schema import OsmConfig, SecurityConfig


class TestConfigLoader(unittest.TestCase):
    """Verify .osm.toml configuration parsing and fallback defaults."""

    def test_default_config_instantiation(self) -> None:
        cfg = get_default_config()
        self.assertIsInstance(cfg, OsmConfig)
        self.assertEqual(cfg.security.profile, "strict")
        self.assertEqual(cfg.security.engine, "ast")
        self.assertTrue(cfg.sandbox.auto_isolate_dangerous)
        self.assertIn("/etc/shadow", cfg.invariants.deny_paths)

    def test_load_config_from_custom_toml(self) -> None:
        custom_toml = """
        [security]
        profile = "permissive"
        engine = "ast"
        fail_action = "prompt"

        [security.sandbox]
        backend = "bubblewrap"
        auto_isolate_dangerous = false
        network_isolation = false
        read_only_root = true
        writable_paths = [".", "/tmp"]

        [security.invariants]
        deny_paths = ["/etc/shadow", "/custom/protected"]
        deny_commands = ["mkfs", "custom_wipe"]

        [hardware]
        driver = "lenovo"
        """
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as tf:
            tf.write(custom_toml)
            temp_path = Path(tf.name)

        try:
            cfg = load_config(temp_path)
            self.assertEqual(cfg.security.profile, "permissive")
            self.assertEqual(cfg.security.fail_action, "prompt")
            self.assertFalse(cfg.sandbox.auto_isolate_dangerous)
            self.assertIn("/custom/protected", cfg.invariants.deny_paths)
            self.assertEqual(cfg.hardware.driver, "lenovo")
        finally:
            temp_path.unlink(missing_ok=True)

    def test_load_config_missing_file_falls_back_to_defaults(self) -> None:
        cfg = load_config(Path("/nonexistent/path/.osm.toml"))
        self.assertEqual(cfg.security.profile, "strict")
        self.assertEqual(cfg.security.engine, "ast")


if __name__ == "__main__":
    unittest.main()

"""Configuration loader for os-manager with TOML parsing and hierarchical fallback."""

import os
from pathlib import Path
import tomllib
from typing import Any, Dict, Optional

from .schema import (
    HardwareConfig,
    InvariantsConfig,
    OsmConfig,
    SandboxConfig,
    SecurityConfig,
)


def get_default_config() -> OsmConfig:
    """Return default configuration instance."""
    return OsmConfig()


def _resolve_config_path(custom_path: Optional[Path | str] = None) -> Optional[Path]:
    """Resolve config file path from custom input, workspace root, or home dir."""
    if custom_path:
        p = Path(custom_path).expanduser().resolve()
        if p.is_file():
            return p
        return None

    # Check current workspace directory
    cwd_path = Path(".osm.toml").resolve()
    if cwd_path.is_file():
        return cwd_path

    # Check OSM_CONFIG environment variable
    env_cfg = os.environ.get("OSM_CONFIG")
    if env_cfg:
        p = Path(env_cfg).expanduser().resolve()
        if p.is_file():
            return p

    # Check ~/.config/osm/config.toml
    user_cfg = Path.home() / ".config" / "osm" / "config.toml"
    if user_cfg.is_file():
        return user_cfg

    return None


def load_config(config_path: Optional[Path | str] = None) -> OsmConfig:
    """Load configuration from TOML file with fallback to default schema."""
    resolved = _resolve_config_path(config_path)
    if not resolved:
        return get_default_config()

    try:
        with open(resolved, "rb") as f:
            data: Dict[str, Any] = tomllib.load(f)
    except Exception:
        return get_default_config()

    sec_data = data.get("security", {})
    sec_cfg = SecurityConfig(
        profile=sec_data.get("profile", "strict"),
        engine=sec_data.get("engine", "ast"),
        fail_action=sec_data.get("fail_action", "deny"),
    )

    sb_data = sec_data.get("sandbox", {})
    sb_cfg = SandboxConfig(
        backend=sb_data.get("backend", "bubblewrap"),
        auto_isolate_dangerous=sb_data.get("auto_isolate_dangerous", True),
        network_isolation=sb_data.get("network_isolation", True),
        read_only_root=sb_data.get("read_only_root", True),
        writable_paths=sb_data.get("writable_paths", [".", "/tmp", "~/.cache"]),
    )

    inv_data = sec_data.get("invariants", {})
    inv_cfg = InvariantsConfig(
        deny_paths=inv_data.get(
            "deny_paths",
            [
                "/etc/shadow",
                "/etc/passwd",
                "/etc/sudoers",
                "/boot",
                "/dev",
                "/mnt/c/Windows",
                "/mnt/c/Program Files",
                "/mnt/c/Program Files (x86)",
            ],
        ),
        deny_commands=inv_data.get(
            "deny_commands",
            [
                "mkfs",
                "fdisk",
                "parted",
                "gdisk",
                "wipefs",
                "dd",
                "wsl --unregister",
                "wsl.exe --unregister",
                "wsl --shutdown",
                "wsl --terminate",
            ],
        ),
        protected_mounts=inv_data.get(
            "protected_mounts", ["/mnt/data", "/mnt/d"]
        ),
    )

    hw_data = data.get("hardware", {})
    hw_cfg = HardwareConfig(
        driver=hw_data.get("driver", "auto"),
        force_override=hw_data.get("force_override", False),
    )

    return OsmConfig(
        security=sec_cfg,
        sandbox=sb_cfg,
        invariants=inv_cfg,
        hardware=hw_cfg,
    )

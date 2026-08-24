"""Data schemas for os-manager configuration."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SecurityConfig:
    profile: str = "strict"  # strict | standard | permissive
    engine: str = "ast"      # ast | legacy_regex
    fail_action: str = "deny"  # deny | prompt | isolate


@dataclass
class SandboxConfig:
    backend: str = "bubblewrap"  # bubblewrap | podman | none
    auto_isolate_dangerous: bool = True
    network_isolation: bool = True
    read_only_root: bool = True
    writable_paths: List[str] = field(
        default_factory=lambda: [".", "/tmp", "~/.cache"]
    )


@dataclass
class InvariantsConfig:
    deny_paths: List[str] = field(
        default_factory=lambda: [
            "/etc/shadow",
            "/etc/passwd",
            "/etc/sudoers",
            "/boot",
            "/dev",
            "/mnt/c/Windows",
            "/mnt/c/Program Files",
            "/mnt/c/Program Files (x86)",
        ]
    )
    deny_commands: List[str] = field(
        default_factory=lambda: [
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
        ]
    )
    protected_mounts: List[str] = field(
        default_factory=lambda: ["/mnt/data", "/mnt/d"]
    )


@dataclass
class HardwareConfig:
    driver: str = "auto"  # auto | lenovo | asus | dell | generic | macos
    force_override: bool = False


@dataclass
class OsmConfig:
    security: SecurityConfig = field(default_factory=SecurityConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    invariants: InvariantsConfig = field(default_factory=InvariantsConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)

"""Platform environment detection utilities."""

import os
import platform
from typing import Dict, Any


def detect_platform() -> Dict[str, Any]:
    """Detect current operating system, kernel, and package manager."""
    system = platform.system()
    info: Dict[str, Any] = {
        "system": system,
        "platform": "unknown",
        "distro_id": "unknown",
        "distro_family": "unknown",
        "pkg_manager": "unknown",
        "service_manager": "none",
        "is_wsl": False,
    }

    if system == "Darwin":
        info.update({
            "platform": "macos",
            "distro_id": "darwin",
            "distro_family": "darwin",
            "pkg_manager": "brew",
            "service_manager": "launchd",
        })
    elif system == "Linux":
        # Check WSL
        is_wsl = False
        try:
            if os.path.exists("/proc/version"):
                with open("/proc/version", "r", encoding="utf-8") as f:
                    if "microsoft" in f.read().lower():
                        is_wsl = True
        except Exception:
            pass

        info["is_wsl"] = is_wsl
        info["platform"] = "wsl" if is_wsl else "linux"
        info["service_manager"] = "systemd"

        # Check /etc/os-release
        if os.path.exists("/etc/os-release"):
            distro_data = {}
            try:
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            distro_data[k] = v.strip("\"'")
                info["distro_id"] = distro_data.get("ID", "linux")
            except Exception:
                pass

        # Map package manager
        dist_id = info["distro_id"]
        if dist_id in ["debian", "ubuntu", "pop", "linuxmint"]:
            info["distro_family"] = "debian"
            info["pkg_manager"] = "apt"
        elif dist_id in ["arch", "manjaro", "endeavouros"]:
            info["distro_family"] = "arch"
            info["pkg_manager"] = "pacman"
        elif dist_id in ["fedora", "rhel", "centos", "rocky"]:
            info["distro_family"] = "fedora"
            info["pkg_manager"] = "dnf"
        elif "suse" in dist_id:
            info["distro_family"] = "suse"
            info["pkg_manager"] = "zypper"
        elif dist_id == "alpine":
            info["distro_family"] = "alpine"
            info["pkg_manager"] = "apk"

    return info

"""System diagnostic collector command."""

import json
import os
import shutil
from typing import List
from ..platform.detector import detect_platform


def run_diag(args: List[str]) -> int:
    """Execute diagnostic inspection and format output."""
    json_mode = "--json" in args
    plat = detect_platform()

    total_b, used_b, free_b = shutil.disk_usage("/")
    cpu_count = os.cpu_count() or 1

    data = {
        "status": "healthy",
        "platform": plat,
        "cpu_count": cpu_count,
        "disk": {
            "total_gb": round(total_b / (1024**3), 2),
            "used_gb": round(used_b / (1024**3), 2),
            "free_gb": round(free_b / (1024**3), 2),
        },
    }

    if json_mode:
        print(json.dumps(data, indent=2))
    else:
        print("=== OS-Manager Diagnostic Report ===")
        print(f"Platform: {plat['platform']} ({plat['distro_id']})")
        print(f"Package Manager: {plat['pkg_manager']}")
        print(f"Service Manager: {plat['service_manager']}")
        print(f"CPUs: {cpu_count}")
        print(f"Disk Free: {data['disk']['free_gb']} GB / {data['disk']['total_gb']} GB")

    return 0

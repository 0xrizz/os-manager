"""System diagnostic collector command."""

import json
import os
import shutil

from ..platform.detector import detect_platform
from ..platform.hal import audit_storage_subsystem, get_active_hardware_driver


def run_diag(args: list[str]) -> int:
    """Execute diagnostic inspection and format output."""
    json_mode = "--json" in args
    plat = detect_platform()
    driver = get_active_hardware_driver()
    dmi = driver.get_dmi_info()
    storage = audit_storage_subsystem("/")
    gpu_subsystem = driver.audit_gpu_subsystem()

    total_b, used_b, free_b = shutil.disk_usage("/")
    cpu_count = os.cpu_count() or 1

    data = {
        "status": "healthy",
        "platform": plat,
        "hardware": {
            "vendor": dmi.vendor,
            "product": dmi.product_name,
            "driver": driver.__class__.__name__,
        },
        "storage": {
            "target_device": storage.target_device,
            "scheduler": storage.scheduler,
            "is_nvme": storage.is_nvme,
        },
        "gpu": {
            "active_profile": gpu_subsystem.active_profile,
            "driver_flavor": gpu_subsystem.driver_flavor,
            "primary_display_gpu": gpu_subsystem.primary_display_gpu.device_name if gpu_subsystem.primary_display_gpu else None,
            "discrete_gpu": gpu_subsystem.discrete_gpu.device_name if gpu_subsystem.discrete_gpu else None,
        },
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
        print(f"Hardware: {dmi.vendor} {dmi.product_name} ({driver.__class__.__name__})")
        print(f"Package Manager: {plat['pkg_manager']}")
        print(f"Service Manager: {plat['service_manager']}")
        print(f"CPUs: {cpu_count}")
        print(f"GPU Profile: {gpu_subsystem.active_profile} (Flavor: {gpu_subsystem.driver_flavor})")
        print(f"Disk Free: {data['disk']['free_gb']} GB / {data['disk']['total_gb']} GB")

    return 0

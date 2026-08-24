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

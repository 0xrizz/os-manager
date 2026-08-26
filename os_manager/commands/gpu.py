"""Dual-GPU Subsystem Management and Application Workload Router CLI."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from ..platform.hal import get_active_hardware_driver
from ..platform.hal.gpu_classifier import sync_desktop_profiles


def run_gpu(argv: List[str]) -> int:
    """Entry point for 'osm gpu' commands."""
    parser = argparse.ArgumentParser(
        prog="osm gpu",
        description="Dual-GPU Subsystem Management and Workload Router",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="GPU action")

    # status
    status_parser = subparsers.add_parser("status", help="Show GPU hardware and runtime telemetry")
    status_parser.add_argument("--json", action="store_true", help="Output telemetry as JSON")

    # install
    install_parser = subparsers.add_parser("install", help="Provision Debian 13 NVIDIA/Intel drivers")
    install_parser.add_argument("--cuda", action="store_true", help="Include NVIDIA CUDA development toolkit")
    install_parser.add_argument("--dry-run", action="store_true", help="Simulate driver installation commands")

    # run
    run_parser = subparsers.add_parser("run", help="Launch application wrapped with PRIME render offload")
    run_parser.add_argument("app_command", nargs=argparse.REMAINDER, help="Application command and arguments")

    # sync-profiles
    sync_parser = subparsers.add_parser("sync-profiles", help="Audit and inject GPU offload tags to .desktop entries")
    sync_parser.add_argument("--dry-run", action="store_true", help="Simulate profile sync without writing files")

    # profile
    profile_parser = subparsers.add_parser("profile", help="Set GPU power gating profile")
    profile_parser.add_argument("profile_mode", choices=["hybrid", "performance", "powersave"], help="Power profile mode")

    args, unknown = parser.parse_known_args(argv)

    if args.subcommand == "status":
        return _handle_status(json_mode=args.json)
    elif args.subcommand == "install":
        return _handle_install(cuda=args.cuda, dry_run=args.dry_run)
    elif args.subcommand == "run":
        cmd = args.app_command
        # If args was parsed with unknown args, append them
        if unknown:
            cmd = unknown + cmd
        return _handle_run(cmd)
    elif args.subcommand == "sync-profiles":
        return _handle_sync_profiles(dry_run=args.dry_run)
    elif args.subcommand == "profile":
        return _handle_profile(args.profile_mode)
    else:
        parser.print_help()
        return 0


def _handle_status(json_mode: bool = False) -> int:
    driver = get_active_hardware_driver()
    subsystem = driver.audit_gpu_subsystem()

    telemetry = {
        "active_profile": subsystem.active_profile,
        "driver_flavor": subsystem.driver_flavor,
        "primary_display_gpu": _serialize_gpu(subsystem.primary_display_gpu),
        "discrete_gpu": _serialize_gpu(subsystem.discrete_gpu),
    }

    if json_mode:
        print(json.dumps(telemetry, indent=2))
    else:
        print("=== Dual-GPU Subsystem Diagnostics ===")
        print(f"Active Profile : {subsystem.active_profile}")
        print(f"Driver Flavor  : {subsystem.driver_flavor}")
        if subsystem.primary_display_gpu:
            p = subsystem.primary_display_gpu
            print(f"Primary iGPU   : {p.vendor} {p.device_name} [{p.pci_slot}] (Driver: {p.driver_in_use}, State: {p.power_state})")
        if subsystem.discrete_gpu:
            d = subsystem.discrete_gpu
            print(f"Discrete dGPU  : {d.vendor} {d.device_name} [{d.pci_slot}] (Driver: {d.driver_in_use}, State: {d.power_state})")
    return 0


def _serialize_gpu(gpu) -> Optional[dict]:
    if not gpu:
        return None
    return {
        "vendor": str(gpu.vendor),
        "device_name": str(gpu.device_name),
        "pci_slot": str(gpu.pci_slot),
        "driver_in_use": str(gpu.driver_in_use),
        "is_discrete": bool(gpu.is_discrete),
        "power_state": str(gpu.power_state),
        "vaapi_supported": bool(gpu.vaapi_supported),
        "cuda_supported": bool(gpu.cuda_supported),
    }


def _handle_install(cuda: bool = False, dry_run: bool = False) -> int:
    driver = get_active_hardware_driver()
    subsystem = driver.audit_gpu_subsystem()

    if subsystem.discrete_gpu and subsystem.discrete_gpu.vendor == "NVIDIA":
        # Enforce proprietary DKMS for Pascal architecture
        pkgs = [
            "nvidia-kernel-dkms",
            "nvidia-driver",
            "firmware-misc-nonfree",
            "intel-media-va-driver-non-free",
        ]
        if cuda:
            pkgs.append("nvidia-cuda-toolkit")

        cmd = ["sudo", "apt-get", "install", "-y"] + pkgs
        print(f"[osm gpu] Provisioning packages: {' '.join(pkgs)}")
        if dry_run:
            print(f"[dry-run] Would execute: {' '.join(cmd)}")
            return 0

        # Execute installation non-interactively
        return _run_privileged(cmd)
    else:
        print("[osm gpu] No discrete NVIDIA GPU identified requiring proprietary DKMS.")
        return 0


def _handle_run(command_args: List[str]) -> int:
    if not command_args:
        print("Error: No application command provided to run.", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
    env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
    env["__VK_LAYER_NV_optimus"] = "non_NVIDIA_only"

    try:
        res = subprocess.run(command_args, env=env)
        return res.returncode
    except Exception as e:
        print(f"Error launching command: {e}", file=sys.stderr)
        return 1


def _handle_sync_profiles(dry_run: bool = False) -> int:
    synced = sync_desktop_profiles(dry_run=dry_run)
    action_label = "Simulated" if dry_run else "Synced"
    print(f"=== Desktop Workload Optimization ({action_label}) ===")
    if not synced:
        print("All applications already properly mapped.")
        return 0

    for item in synced:
        print(f"- {item['app']}: {item['source']} -> {item['target']}")
    print(f"Total overrides created: {len(synced)}")
    return 0


def _handle_profile(mode: str) -> int:
    print(f"[osm gpu] Applying power profile: {mode}")
    # Configuration target: /etc/modprobe.d/nvidia-pm.conf
    # hybrid: NVreg_DynamicPowerManagement=0x02
    # performance: NVreg_DynamicPowerManagement=0x00
    val = "0x02" if mode in ("hybrid", "powersave") else "0x00"
    content = f'options nvidia "NVreg_DynamicPowerManagement={val}"\n'

    conf_path = Path("/etc/modprobe.d/nvidia-pm.conf")
    cmd = ["sudo", "tee", str(conf_path)]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = proc.communicate(input=content)
    if proc.returncode != 0:
        print(f"Failed to update profile: {stderr.strip()}", file=sys.stderr)
        return proc.returncode

    print(f"Successfully configured {conf_path} with NVreg_DynamicPowerManagement={val}.")
    return 0


def _run_privileged(cmd: List[str]) -> int:
    """Run privileged command streaming sudo password if needed."""
    env_file = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".env"
    sudo_pwd = None
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("SUDO_PASSWORD="):
                sudo_pwd = line.split("=", 1)[1].strip()
                break

    if sudo_pwd:
        if cmd[0] == "sudo":
            cmd = ["sudo", "-S"] + cmd[1:]
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
        )
        proc.communicate(input=f"{sudo_pwd}\n")
        return proc.returncode
    else:
        return subprocess.run(cmd).returncode

"""Freedesktop Application Workload Classifier and Profile Sync Engine."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


DISCRETE_GPU_CATEGORIES = {
    "game",
    "3dgraphics",
    "graphics;3d",
    "engineering",
    "videoediting",
    "science;engineering",
}

DISCRETE_GPU_KEYWORDS = {
    "blender",
    "godot",
    "steam",
    "unreal",
    "unity",
    "ollama",
    "pytorch",
    "davinci",
    "kdenlive",
    "obs",
    "retroarch",
    "heroic",
    "lutris",
}


def classify_application(desktop_content: str) -> str:
    """Classify application workload target (intel vs nvidia) based on .desktop content."""
    lines = desktop_content.splitlines()
    categories_val = ""
    name_val = ""
    exec_val = ""

    for line in lines:
        line_clean = line.strip()
        if line_clean.startswith("Categories="):
            categories_val = line_clean.split("=", 1)[1].lower()
        elif line_clean.startswith("Name="):
            name_val = line_clean.split("=", 1)[1].lower()
        elif line_clean.startswith("Exec="):
            exec_val = line_clean.split("=", 1)[1].lower()

    # Check categories
    cat_tokens = [t.strip().lower() for t in categories_val.split(";") if t.strip()]
    for token in cat_tokens:
        if token in DISCRETE_GPU_CATEGORIES or "3d" in token or "game" in token:
            return "nvidia"

    # Check name/exec keywords
    combined_text = f"{name_val} {exec_val}"
    for kw in DISCRETE_GPU_KEYWORDS:
        if kw in combined_text:
            return "nvidia"

    return "intel"


def sync_desktop_profiles(
    source_dirs: Optional[List[Path]] = None,
    target_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """Scan source desktop entries, detect discrete workloads, and generate overrides."""
    if source_dirs is None:
        source_dirs = [
            Path("/usr/share/applications"),
            Path("/var/lib/flatpak/exports/share/applications"),
        ]

    if target_dir is None:
        target_dir = Path.home() / ".local" / "share" / "applications"

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    synced: List[Dict[str, Any]] = []

    for src_dir in source_dirs:
        if not src_dir.is_dir():
            continue

        for desktop_file in sorted(src_dir.glob("*.desktop")):
            try:
                content = desktop_file.read_text(encoding="utf-8")
            except Exception:
                continue

            target_gpu = classify_application(content)
            if target_gpu == "nvidia":
                target_file = target_dir / desktop_file.name
                app_name = desktop_file.stem

                # Check if override already has the keys
                if target_file.exists():
                    existing_content = target_file.read_text(encoding="utf-8")
                    if "PrefersNonDefaultGPU=true" in existing_content:
                        continue

                # Prepare modified content
                new_content = _inject_discrete_gpu_keys(content)

                if not dry_run:
                    target_file.write_text(new_content, encoding="utf-8")

                synced.append({
                    "app": app_name,
                    "source": str(desktop_file),
                    "target": str(target_file),
                    "action": "override_created" if not dry_run else "dry_run",
                })

    return synced


def _inject_discrete_gpu_keys(content: str) -> str:
    """Inject Freedesktop discrete GPU keys under [Desktop Entry] section."""
    lines = content.splitlines()
    output_lines = []
    in_desktop_entry = False
    injected = False

    for line in lines:
        output_lines.append(line)
        if line.strip() == "[Desktop Entry]":
            in_desktop_entry = True
            output_lines.append("PrefersNonDefaultGPU=true")
            output_lines.append("X-KDE-RunOnDiscreteGpu=true")
            injected = True

    if not injected:
        output_lines.insert(0, "[Desktop Entry]\nPrefersNonDefaultGPU=true\nX-KDE-RunOnDiscreteGpu=true")

    return "\n".join(output_lines) + "\n"

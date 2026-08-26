import pytest
from pathlib import Path
from os_manager.platform.hal.gpu_classifier import (
    classify_application,
    sync_desktop_profiles,
)


def test_classify_media_app_to_intel():
    content = """[Desktop Entry]
Name=Spotube
Exec=spotube %U
Categories=AudioVideo;Audio;Player;
"""
    assert classify_application(content) == "intel"


def test_classify_3d_game_to_nvidia():
    content = """[Desktop Entry]
Name=Blender
Exec=blender %f
Categories=Graphics;3DGraphics;
"""
    assert classify_application(content) == "nvidia"


def test_sync_desktop_profiles_creates_overrides(tmp_path: Path):
    system_dir = tmp_path / "usr_share"
    system_dir.mkdir(parents=True)
    user_dir = tmp_path / "user_share"
    user_dir.mkdir(parents=True)

    # Media app (Intel - should not override with discrete)
    (system_dir / "spotube.desktop").write_text(
        "[Desktop Entry]\nName=Spotube\nExec=spotube\nCategories=Audio;Player;\n",
        encoding="utf-8",
    )

    # 3D app (NVIDIA - should create override with PrefersNonDefaultGPU)
    (system_dir / "blender.desktop").write_text(
        "[Desktop Entry]\nName=Blender\nExec=blender\nCategories=Graphics;3DGraphics;\n",
        encoding="utf-8",
    )

    synced = sync_desktop_profiles(source_dirs=[system_dir], target_dir=user_dir)
    assert len(synced) == 1
    assert synced[0]["app"] == "blender"

    override_file = user_dir / "blender.desktop"
    assert override_file.exists()
    content = override_file.read_text(encoding="utf-8")
    assert "PrefersNonDefaultGPU=true" in content
    assert "X-KDE-RunOnDiscreteGpu=true" in content

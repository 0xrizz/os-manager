"""Tests for HSI security hardening module."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from os_manager.commands.hsi import (
    audit_hsi_posture,
    generate_zram_config,
    check_sleep_state,
    check_active_swap,
    run_hsi,
)


def test_generate_zram_config():
    """Verify zram-generator config generation format."""
    cfg = generate_zram_config(ram_fraction="ram / 2", max_mb=8192)
    assert "[zram0]" in cfg
    assert "zram-size = min(ram / 2, 8192)" in cfg
    assert "compression-algorithm = zstd" in cfg
    assert "swap-priority = 100" in cfg


def test_check_sleep_state_s2idle(tmp_path):
    """Test sleep state detection when s2idle is active."""
    mock_mem_sleep = tmp_path / "mem_sleep"
    mock_mem_sleep.write_text("[s2idle] deep\n")
    state = check_sleep_state(sysfs_path=str(mock_mem_sleep))
    assert state["current"] == "s2idle"
    assert state["available"] == ["s2idle", "deep"]
    assert state["hardened"] is True


def test_check_sleep_state_deep(tmp_path):
    """Test sleep state detection when deep is active."""
    mock_mem_sleep = tmp_path / "mem_sleep"
    mock_mem_sleep.write_text("s2idle [deep]\n")
    state = check_sleep_state(sysfs_path=str(mock_mem_sleep))
    assert state["current"] == "deep"
    assert state["hardened"] is False


def test_check_active_swap_with_zram():
    """Test swap audit when zram0 is active."""
    proc_swaps_content = (
        "Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority\n"
        "/dev/zram0                              partition\t8388604\t\t0\t\t100\n"
    )
    with patch("pathlib.Path.read_text", return_value=proc_swaps_content):
        swap_info = check_active_swap()
        assert swap_info["zram_active"] is True
        assert swap_info["unencrypted_disk_swap"] is False
        assert swap_info["hardened"] is True


def test_check_active_swap_with_unencrypted_partition():
    """Test swap audit when unencrypted nvme partition is active."""
    proc_swaps_content = (
        "Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority\n"
        "/dev/nvme0n1p3                          partition\t4194300\t\t0\t\t-2\n"
    )
    with patch("pathlib.Path.read_text", return_value=proc_swaps_content):
        swap_info = check_active_swap()
        assert swap_info["zram_active"] is False
        assert swap_info["unencrypted_disk_swap"] is True
        assert swap_info["hardened"] is False


def test_audit_hsi_posture():
    """Test comprehensive HSI posture audit aggregation."""
    with patch("os_manager.commands.hsi.check_sleep_state", return_value={"current": "s2idle", "hardened": True}), \
         patch("os_manager.commands.hsi.check_active_swap", return_value={"hardened": True, "zram_active": True}), \
         patch("os_manager.commands.hsi.check_fwupd_dbx", return_value={"supported": True, "dbx_version": "371"}):
        res = audit_hsi_posture()
        assert res["sleep_state"]["hardened"] is True
        assert res["swap"]["hardened"] is True
        assert res["overall_status"] == "hardened"


def test_run_hsi_audit_json(capsys):
    """Test run_hsi CLI execution in JSON mode."""
    with patch("os_manager.commands.hsi.audit_hsi_posture", return_value={"overall_status": "hardened"}):
        code = run_hsi(["audit", "--json"])
        captured = capsys.readouterr()
        assert code == 0
        assert '"overall_status": "hardened"' in captured.out

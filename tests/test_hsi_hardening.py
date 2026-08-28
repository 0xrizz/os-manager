"""Tests for HSI security hardening module."""

import os
import subprocess
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.hsi import (
    audit_hsi_posture,
    check_active_swap,
    check_sleep_state,
    generate_zram_config,
    get_sudo_password,
    run_hsi,
    run_privileged_command,
)


def test_generate_zram_config_default():
    """Verify zram-generator config defaults to 100% RAM (min(ram, 8192))."""
    cfg = generate_zram_config()
    assert "[zram0]" in cfg
    assert "zram-size = min(ram, 8192)" in cfg
    assert "compression-algorithm = zstd" in cfg
    assert "swap-priority = 100" in cfg


def test_generate_zram_config_custom():
    """Verify zram-generator config supports custom fractions."""
    cfg = generate_zram_config(ram_fraction="ram / 2", max_mb=4096)
    assert "zram-size = min(ram / 2, 4096)" in cfg


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
         patch("os_manager.commands.hsi.check_fwupd_dbx", return_value={"supported": True, "dbx_version": "371"}), \
         patch("os_manager.commands.hsi.audit_zram_system") as mock_zram:
        mock_zram.return_value = MagicMock(conflicts_detected=False, status="OPTIMAL")
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


def test_get_sudo_password_env_var(monkeypatch):
    """Verify SUDO_PASSWORD is read from os.environ when present."""
    monkeypatch.setenv("SUDO_PASSWORD", "env_secret_123")
    assert get_sudo_password() == "env_secret_123"


def test_get_sudo_password_dotenv_file(tmp_path, monkeypatch):
    """Verify SUDO_PASSWORD is parsed from .env file when not in os.environ."""
    monkeypatch.delenv("SUDO_PASSWORD", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_VAR=foo\nSUDO_PASSWORD=file_secret_456\nOTHER=bar\n")
    assert get_sudo_password(env_path=env_file) == "file_secret_456"


def test_get_sudo_password_none(tmp_path, monkeypatch):
    """Verify get_sudo_password returns None when no password configured."""
    monkeypatch.delenv("SUDO_PASSWORD", raising=False)
    assert get_sudo_password(env_path=tmp_path / ".nonexistent") is None


def test_run_privileged_command_as_root(monkeypatch):
    """Verify command runs without sudo prefix when already root."""
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=["/bin/foo"], returncode=0)
        res = run_privileged_command(["/bin/foo"])
        mock_run.assert_called_once_with(["/bin/foo"])
        assert res.returncode == 0


def test_run_privileged_command_passwordless_sudo(monkeypatch):
    """Verify passwordless sudo is used when sudo -n true succeeds."""
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=["sudo", "-n", "true"], returncode=0),
            subprocess.CompletedProcess(args=["sudo", "/bin/foo"], returncode=0),
        ]
        res = run_privileged_command(["/bin/foo"])
        assert mock_run.call_count == 2
        mock_run.assert_called_with(["sudo", "/bin/foo"])
        assert res.returncode == 0


def test_run_privileged_command_sudo_with_password(monkeypatch):
    """Verify sudo -S with password input when sudo -n true fails and password exists."""
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setenv("SUDO_PASSWORD", "secretpass")
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=["sudo", "-n", "true"], returncode=1),
            subprocess.CompletedProcess(args=["sudo", "-S", "/bin/foo"], returncode=0),
        ]
        res = run_privileged_command(["/bin/foo"])
        assert mock_run.call_count == 2
        mock_run.assert_called_with(
            ["sudo", "-S", "/bin/foo"],
            input="secretpass\n",
            text=True,
        )
        assert res.returncode == 0


def test_run_privileged_command_sudo_fallback(tmp_path, monkeypatch):
    """Verify fallback to standard sudo when no password is available."""
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.delenv("SUDO_PASSWORD", raising=False)
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=["sudo", "-n", "true"], returncode=1),
            subprocess.CompletedProcess(args=["sudo", "/bin/foo"], returncode=0),
        ]
        res = run_privileged_command(["/bin/foo"], env_path=tmp_path / ".nonexistent")
        assert mock_run.call_count == 2
        mock_run.assert_called_with(["sudo", "/bin/foo"])
        assert res.returncode == 0


def test_run_hsi_apply_invokes_privileged_command(tmp_path):
    """Verify run_hsi apply invokes run_privileged_command with script path."""
    with patch("os_manager.commands.hsi.run_privileged_command") as mock_priv, \
         patch("pathlib.Path.is_file", return_value=True):
        mock_priv.return_value = subprocess.CompletedProcess(args=["script"], returncode=0)
        code = run_hsi(["apply"])
        assert code == 0
        assert mock_priv.called

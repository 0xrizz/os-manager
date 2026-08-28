import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from os_manager.memory.zram import (
    audit_zram_system,
    ZramAuditReport,
    ConflictingServiceStatus,
    CONFLICTING_ZRAM_SERVICES,
    remediate_zram_conflicts,
    unmask_zram_service,
    generate_canonical_zram_conf,
)


def test_audit_zram_optimal(tmp_path):
    proc_swaps = tmp_path / "swaps"
    proc_swaps.write_text("Filename Type Size Used Priority\n/dev/zram0 partition 8388604 0 100\n")
    zram_conf = tmp_path / "zram-generator.conf"
    zram_conf.write_text("[zram0]\nzram-size = min(ram, 8192)\ncompression-algorithm = zstd\nswap-priority = 100\n")

    with patch("shutil.which", return_value="/usr/lib/systemd/system-generators/systemd-zram-generator"), \
         patch("subprocess.run") as mock_run:
        # Mock all conflicting services as non-installed or masked
        mock_run.return_value = MagicMock(returncode=1, stdout="masked\n", stderr="")
        report = audit_zram_system(proc_swaps_path=str(proc_swaps), conf_path=str(zram_conf))

        assert isinstance(report, ZramAuditReport)
        assert report.status == "OPTIMAL"
        assert report.zram_device_active is True
        assert report.canonical_configured is True
        assert report.canonical_installed is True
        assert report.conflicts_detected is False
        assert len(report.active_devices) == 1
        assert report.active_devices[0]["device"] == "/dev/zram0"
        assert "OPTIMAL" in report.status or "optimal" in report.summary_message.lower()


def test_audit_zram_conflict_detected(tmp_path):
    proc_swaps = tmp_path / "swaps"
    proc_swaps.write_text("Filename Type Size Used Priority\n/dev/zram0 partition 8388604 0 100\n")
    zram_conf = tmp_path / "zram-generator.conf"
    zram_conf.write_text("[zram0]\nzram-size = min(ram, 8192)\n")

    def mock_subprocess_run(cmd, *args, **kwargs):
        service_name = cmd[2] if len(cmd) > 2 else ""
        if cmd[1] == "list-unit-files":
            if service_name == "zramswap.service":
                return MagicMock(returncode=0, stdout="zramswap.service enabled\n", stderr="")
            return MagicMock(returncode=1, stdout="", stderr="")
        elif cmd[1] == "is-active":
            if service_name == "zramswap.service":
                return MagicMock(returncode=0, stdout="active\n", stderr="")
            return MagicMock(returncode=1, stdout="inactive\n", stderr="")
        elif cmd[1] == "is-failed":
            return MagicMock(returncode=1, stdout="inactive\n", stderr="")
        return MagicMock(returncode=1, stdout="", stderr="")

    with patch("shutil.which", return_value="/usr/lib/systemd/system-generators/systemd-zram-generator"), \
         patch("subprocess.run", side_effect=mock_subprocess_run):
        report = audit_zram_system(proc_swaps_path=str(proc_swaps), conf_path=str(zram_conf))

        assert report.status == "CONFLICT_DETECTED"
        assert report.conflicts_detected is True
        assert len(report.conflicting_services) == 1
        assert report.conflicting_services[0].name == "zramswap.service"
        assert report.conflicting_services[0].installed is True
        assert report.conflicting_services[0].enabled is True
        assert report.conflicting_services[0].active is True


def test_audit_zram_degraded(tmp_path):
    proc_swaps = tmp_path / "swaps"
    proc_swaps.write_text("Filename Type Size Used Priority\n/dev/zram0 partition 8388604 0 100\n")
    zram_conf = tmp_path / "nonexistent.conf"

    with patch("shutil.which", return_value=None), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        report = audit_zram_system(proc_swaps_path=str(proc_swaps), conf_path=str(zram_conf))

        assert report.status == "DEGRADED"
        assert report.zram_device_active is True
        assert report.canonical_configured is False
        assert report.conflicts_detected is False


def test_audit_zram_unconfigured(tmp_path):
    proc_swaps = tmp_path / "swaps"
    proc_swaps.write_text("Filename Type Size Used Priority\n")
    zram_conf = tmp_path / "nonexistent.conf"

    with patch("shutil.which", return_value=None), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        report = audit_zram_system(proc_swaps_path=str(proc_swaps), conf_path=str(zram_conf))

        assert report.status == "UNCONFIGURED"
        assert report.zram_device_active is False
        assert report.canonical_configured is False
        assert report.conflicts_detected is False


def test_generate_canonical_zram_conf():
    conf = generate_canonical_zram_conf()
    assert "[zram0]" in conf
    assert "zram-size = min(ram, 8192)" in conf
    assert "compression-algorithm = zstd" in conf
    assert "swap-priority = 100" in conf


def test_remediate_zram_conflicts_dry_run():
    report = ZramAuditReport(
        conflicts_detected=True,
        conflicting_services=[
            ConflictingServiceStatus(name="zramswap.service", installed=True, failed=True)
        ],
    )
    res = remediate_zram_conflicts(report=report, dry_run=True)
    assert res["success"] is True
    assert res["dry_run"] is True
    assert len(res["actions"]) > 0
    assert any("mask zramswap.service" in a for a in res["actions"])


def test_remediate_zram_conflicts_execution():
    report = ZramAuditReport(
        conflicts_detected=True,
        conflicting_services=[
            ConflictingServiceStatus(name="zramswap.service", installed=True, failed=True)
        ],
    )
    with patch("os_manager.commands.hsi.run_privileged_command") as mock_priv, \
         patch("os_manager.memory.zram.audit_zram_system") as mock_audit:
        mock_priv.return_value = MagicMock(returncode=0)
        mock_audit.return_value = ZramAuditReport(status="OPTIMAL", zram_device_active=True)

        res = remediate_zram_conflicts(report=report, dry_run=False)
        assert res["success"] is True
        assert res["dry_run"] is False
        assert mock_priv.call_count >= 4  # stop, disable, mask, reset-failed, daemon-reload


def test_unmask_zram_service():
    with patch("os_manager.commands.hsi.run_privileged_command") as mock_priv:
        mock_priv.return_value = MagicMock(returncode=0)
        assert unmask_zram_service("zramswap.service") is True
        mock_priv.assert_called_once_with(["systemctl", "unmask", "zramswap.service"], env_path=None, check=False)

        mock_priv.return_value = MagicMock(returncode=1)
        assert unmask_zram_service("zramswap.service") is False


def test_hsi_audit_includes_zram_conflict():
    from os_manager.commands.hsi import audit_hsi_posture
    with patch("os_manager.memory.zram.audit_zram_system") as mock_audit:
        mock_audit.return_value = ZramAuditReport(
            conflicts_detected=True,
            status="CONFLICT_DETECTED",
            zram_device_active=True,
            summary_message="Conflicting zRAM services detected: zramswap.service",
        )
        posture = audit_hsi_posture()
        assert posture["swap"]["zram_conflict_detected"] is True
        assert posture["swap"]["zram_status"] == "CONFLICT_DETECTED"
        assert posture["swap"]["hardened"] is False
        assert posture["overall_status"] == "needs_hardening"


def test_hsi_apply_calls_remediate_zram_conflicts():
    from os_manager.commands.hsi import run_hsi
    with patch("os_manager.commands.hsi.remediate_zram_conflicts") as mock_rem, \
         patch("os_manager.commands.hsi.run_privileged_command") as mock_priv, \
         patch("pathlib.Path.is_file", return_value=True):
        mock_rem.return_value = {"success": True, "dry_run": False}
        mock_priv.return_value = MagicMock(returncode=0)

        code = run_hsi(["apply"])
        assert code == 0
        mock_rem.assert_called_once_with(dry_run=False)
        mock_priv.assert_called_once()


def test_diag_memory_zram_telemetry_json(capsys):
    from os_manager.commands.diag import run_diag
    with patch("os_manager.commands.diag.audit_zram_system") as mock_zram:
        mock_zram.return_value = ZramAuditReport(
            conflicts_detected=True,
            status="CONFLICT_DETECTED",
            zram_device_active=True,
            summary_message="Conflicting zRAM services detected: zramswap.service",
            conflicting_services=[ConflictingServiceStatus(name="zramswap.service", installed=True, active=True)],
        )
        code = run_diag(["--json"])
        assert code == 0
        captured = capsys.readouterr()
        import json
        data = json.loads(captured.out)
        assert "memory" in data
        assert data["memory"]["conflicts_detected"] is True
        assert data["memory"]["zram_status"] == "CONFLICT_DETECTED"
        assert len(data["memory"]["conflicting_services"]) == 1


def test_diag_memory_zram_warning_text(capsys):
    from os_manager.commands.diag import run_diag
    with patch("os_manager.commands.diag.audit_zram_system") as mock_zram:
        mock_zram.return_value = ZramAuditReport(
            conflicts_detected=True,
            status="CONFLICT_DETECTED",
            zram_device_active=True,
            summary_message="Conflicting zRAM services detected: zramswap.service",
        )
        code = run_diag([])
        assert code == 0
        captured = capsys.readouterr()
        assert "CONFLICT_DETECTED" in captured.out
        assert "[WARN]" in captured.out or "Conflict Detected" in captured.out



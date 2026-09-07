"""Tests for osm runtime / toolchain CLI controller."""

import json
import os
from unittest.mock import patch, MagicMock
from os_manager.commands.runtime import run_runtime, get_mise_bin, audit_doctor
from os_manager.cli import main as cli_main


def test_get_mise_bin():
    with patch("shutil.which", return_value="/custom/bin/mise"), \
         patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=True):
        assert get_mise_bin() == "/custom/bin/mise"


def test_get_mise_bin_fallback():
    with patch("shutil.which", return_value=None), \
         patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=True):
        assert get_mise_bin() == os.path.expanduser("~/.local/bin/mise")


def test_get_mise_bin_not_found():
    with patch("shutil.which", return_value=None), \
         patch("os.path.isfile", return_value=False):
        assert get_mise_bin() is None


def test_runtime_status_json(capsys):
    mock_data = [
        {"plugin": "node", "version": "22.0.0", "source": {"type": "mise.toml"}},
        {"plugin": "python", "version": "3.13.0", "source": {"type": "mise.toml"}},
    ]
    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
        rc = run_runtime(["status", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        res = json.loads(captured.out)
        assert "plugins" in res or "runtimes" in res or len(res) == 2


def test_runtime_status_text(capsys):
    mock_data = [
        {"plugin": "node", "version": "22.0.0", "active": True},
        {"plugin": "python", "version": "3.13.0", "active": False},
    ]
    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
        rc = run_runtime(["status"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Declarative Toolchains & Runtimes (mise)" in captured.out
        assert "node" in captured.out
        assert "[active]" in captured.out


def test_runtime_status_dict_data(capsys):
    mock_data = {"node": ["22.0.0"], "python": ["3.13.0"]}
    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_data))
        rc = run_runtime(["status"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "node" in captured.out


def test_runtime_status_mise_not_found(capsys):
    with patch("os_manager.commands.runtime.get_mise_bin", return_value=None):
        rc = run_runtime(["status"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "mise binary not found" in captured.err

        rc_json = run_runtime(["status", "--json"])
        assert rc_json == 1
        captured_json = capsys.readouterr()
        assert "mise binary not found" in json.loads(captured_json.out)["error"]


def test_runtime_status_proc_failure(capsys):
    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=2, stderr="mise failure", stdout="")
        rc = run_runtime(["status"])
        assert rc == 2
        captured = capsys.readouterr()
        assert "Error querying mise ls" in captured.err

        rc_json = run_runtime(["status", "--json"])
        assert rc_json == 2


def test_runtime_sync():
    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        rc = run_runtime(["sync"])
        assert rc == 0
        assert mock_run.call_count == 2  # mise install and mise reshim


def test_runtime_sync_mise_not_found(capsys):
    with patch("os_manager.commands.runtime.get_mise_bin", return_value=None):
        rc = run_runtime(["sync"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "mise binary not found" in captured.err


def test_runtime_sync_failure():
    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        rc = run_runtime(["sync"])
        assert rc == 1
        assert mock_run.call_count == 1


def test_runtime_doctor():
    with patch("os_manager.commands.runtime.audit_doctor") as mock_doc:
        mock_doc.return_value = {"ok": True, "checks": {"mise_installed": True}, "issues": []}
        rc = run_runtime(["doctor"])
        assert rc == 0


def test_runtime_doctor_with_issues(capsys):
    with patch("os_manager.commands.runtime.audit_doctor") as mock_doc:
        mock_doc.return_value = {
            "ok": False,
            "checks": {"mise_installed": False},
            "issues": ["mise executable is not found"],
        }
        rc = run_runtime(["doctor"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Issues Detected" in captured.out
        assert "mise executable is not found" in captured.out


def test_runtime_doctor_json(capsys):
    with patch("os_manager.commands.runtime.audit_doctor") as mock_doc:
        mock_doc.return_value = {"ok": True, "checks": {}, "issues": []}
        rc = run_runtime(["doctor", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True


def test_audit_doctor_logic():
    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch.dict(os.environ, {"PATH": os.path.expanduser("~/.local/share/mise/shims") + ":/bin:/usr/bin"}), \
         patch("os.path.isfile", return_value=True), \
         patch("os.path.islink", return_value=False), \
         patch("os.path.isdir", return_value=True), \
         patch("os.listdir", return_value=[]):
        res = audit_doctor()
        assert res["ok"] is True
        assert res["checks"]["mise_installed"] is True
        assert res["checks"]["shims_in_path"] is True
        assert res["checks"]["system_python_intact"] is True
        assert res["checks"]["shadowed_binaries"] == []


def test_audit_doctor_shadowing():
    shims_path = os.path.expanduser("~/.local/share/mise/shims")
    local_bin = os.path.expanduser("~/.local/bin")

    def mock_listdir(path):
        if path == local_bin:
            return ["node", "osm"]
        elif path == shims_path:
            return ["node", "python"]
        return []

    with patch("os_manager.commands.runtime.get_mise_bin", return_value="/bin/mise"), \
         patch.dict(os.environ, {"PATH": "/bin:/usr/bin"}), \
         patch("os.path.isfile", return_value=True), \
         patch("os.path.islink", return_value=False), \
         patch("os.path.isdir", return_value=True), \
         patch("os.listdir", side_effect=mock_listdir):
        res = audit_doctor()
        assert res["ok"] is False
        assert "node" in res["checks"]["shadowed_binaries"]
        assert len(res["issues"]) >= 2  # shims not in PATH and shadowing node


def test_runtime_help(capsys):
    rc = run_runtime([])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Usage: osm runtime" in captured.out

    rc_help = run_runtime(["--help"])
    assert rc_help == 0


def test_runtime_unknown_subcommand(capsys):
    rc = run_runtime(["invalid_action"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Unknown runtime subcommand" in captured.err


def test_cli_integration_runtime():
    with patch("os_manager.commands.runtime.run_runtime", return_value=0) as mock_rt:
        rc = cli_main(["runtime", "status"])
        assert rc == 0
        mock_rt.assert_called_once_with(["status"])


def test_cli_integration_toolchain():
    with patch("os_manager.commands.runtime.run_runtime", return_value=0) as mock_rt:
        rc = cli_main(["toolchain", "sync"])
        assert rc == 0
        mock_rt.assert_called_once_with(["sync"])

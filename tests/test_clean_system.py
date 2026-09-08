"""Tests for system cache cleanup command."""

from unittest.mock import patch, MagicMock
from os_manager.commands.clean import run_clean, clean_caches


def test_clean_dry_run(capsys):
    rc = run_clean(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[DRY RUN]" in out


def test_clean_caches_invokes_mise():
    with patch("shutil.which", return_value="/usr/local/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        clean_caches(dry_run=False, all_caches=True)
        # Verify mise cache clear was called
        calls = [" ".join(call[0][0]) for call in mock_run.call_args_list]
        assert any("mise" in c and "cache" in c and "clear" in c for c in calls)
        assert any("mise" in c and "prune" in c and "-y" in c for c in calls)


def test_clean_caches_mise_no_prune_when_not_all():
    with patch("shutil.which", return_value="/usr/local/bin/mise"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        clean_caches(dry_run=False, all_caches=False)
        calls = [" ".join(call[0][0]) for call in mock_run.call_args_list]
        assert any("mise" in c and "cache" in c and "clear" in c for c in calls)
        assert not any("prune" in c for c in calls)


def test_clean_caches_dry_run_skips_subprocess(capsys):
    with patch("shutil.which", return_value="/usr/local/bin/mise"), \
         patch("subprocess.run") as mock_run:
        clean_caches(dry_run=True, all_caches=True)
        mock_run.assert_not_called()
        out = capsys.readouterr().out
        assert "[DRY RUN] Cleaning mise toolchain cache..." in out


def test_clean_caches_invokes_uv():
    def fake_which(cmd):
        if cmd == "uv":
            return "/usr/local/bin/uv"
        return None

    with patch("shutil.which", side_effect=fake_which), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        clean_caches(dry_run=False, all_caches=False)
        calls = [" ".join(call[0][0]) for call in mock_run.call_args_list]
        assert any("uv" in c and "cache" in c and "clean" in c for c in calls)


def test_clean_caches_no_binaries_present():
    with patch("shutil.which", return_value=None), \
         patch("os.path.isfile", return_value=False), \
         patch("subprocess.run") as mock_run:
        rc = clean_caches(dry_run=False, all_caches=True)
        assert rc == 0
        mock_run.assert_not_called()


def test_clean_caches_fallback_paths():
    with patch("shutil.which", return_value=None), \
         patch("os.path.isfile", return_value=True), \
         patch("os.access", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        rc = clean_caches(dry_run=False, all_caches=True)
        assert rc == 0
        calls = [" ".join(call[0][0]) for call in mock_run.call_args_list]
        assert any("mise" in c and "cache" in c and "clear" in c for c in calls)
        assert any("uv" in c and "cache" in c and "clean" in c for c in calls)


def test_run_clean_with_all_flag():
    with patch("os_manager.commands.clean.clean_caches") as mock_clean:
        mock_clean.return_value = 0
        rc = run_clean(["--all"])
        assert rc == 0
        mock_clean.assert_called_once_with(dry_run=False, all_caches=True)


def test_run_clean_defaults():
    with patch("os_manager.commands.clean.clean_caches") as mock_clean:
        mock_clean.return_value = 0
        rc = run_clean([])
        assert rc == 0
        mock_clean.assert_called_once_with(dry_run=False, all_caches=False)

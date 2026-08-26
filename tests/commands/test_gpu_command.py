import pytest
from unittest.mock import patch, MagicMock
from os_manager.commands.gpu import run_gpu


def test_gpu_command_status_json(capsys):
    with patch("os_manager.commands.gpu.get_active_hardware_driver") as mock_drv:
        mock_instance = MagicMock()
        mock_subsystem = MagicMock()
        mock_subsystem.active_profile = "hybrid"
        mock_subsystem.driver_flavor = "nouveau"
        mock_subsystem.primary_display_gpu = MagicMock(vendor="Intel", device_name="Iris Plus G1", power_state="active")
        mock_subsystem.discrete_gpu = MagicMock(vendor="NVIDIA", device_name="GeForce MX330", power_state="suspended")
        mock_instance.audit_gpu_subsystem.return_value = mock_subsystem
        mock_drv.return_value = mock_instance

        code = run_gpu(["status", "--json"])
        assert code == 0
        captured = capsys.readouterr()
        assert '"vendor": "Intel"' in captured.out or '"vendor": "NVIDIA"' in captured.out


def test_gpu_command_run_wrapper():
    with patch("os_manager.commands.gpu.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        code = run_gpu(["run", "glxgears"])
        assert code == 0
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        env = kwargs.get("env", {})
        assert env.get("__NV_PRIME_RENDER_OFFLOAD") == "1"
        assert env.get("__GLX_VENDOR_LIBRARY_NAME") == "nvidia"

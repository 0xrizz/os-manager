import json
import pytest
from unittest.mock import patch, MagicMock
from os_manager.commands.diag import run_diag


def test_diag_includes_gpu_telemetry(capsys):
    with patch("os_manager.commands.diag.get_active_hardware_driver") as mock_drv:
        mock_inst = MagicMock()
        mock_subsystem = MagicMock()
        mock_subsystem.active_profile = "hybrid"
        mock_subsystem.driver_flavor = "nouveau"
        mock_subsystem.primary_display_gpu = MagicMock(vendor="Intel", device_name="Iris Plus G1", power_state="active")
        mock_subsystem.discrete_gpu = MagicMock(vendor="NVIDIA", device_name="GeForce MX330", power_state="suspended")
        mock_inst.audit_gpu_subsystem.return_value = mock_subsystem
        mock_inst.get_dmi_info.return_value = MagicMock(vendor="LENOVO", product_name="81WD")
        mock_drv.return_value = mock_inst

        code = run_diag(["--json"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "gpu" in data
        assert data["gpu"]["active_profile"] == "hybrid"

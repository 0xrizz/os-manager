"""Model Context Protocol (MCP) Tool Declarations and Handlers."""

import json
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List

from os_manager.platform.detector import detect_platform
from os_manager.platform.hal import audit_storage_subsystem, get_active_hardware_driver
from os_manager.security.ast_guard import evaluate_payload


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Return Anthropic MCP tools/list JSON schema declarations."""
    return [
        {
            "name": "osm_safe_exec",
            "description": "Execute a shell command with pre-flight Shell AST zero-trust safety verification.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to evaluate and run.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Maximum execution timeout in seconds (default: 30).",
                        "default": 30,
                    },
                },
                "required": ["command"],
            },
        },
        {
            "name": "osm_system_health",
            "description": "Gather real-time system metrics, hardware thermal profiles, and storage status.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "osm_sandbox_run",
            "description": "Run an untrusted shell command inside an ephemeral Bubblewrap rootless container jail.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to isolate inside ephemeral sandbox.",
                    },
                    "workdir": {
                        "type": "string",
                        "description": "Target workspace directory (default: current directory).",
                        "default": ".",
                    },
                },
                "required": ["command"],
            },
        },
        {
            "name": "osm_tune",
            "description": "Query or modify hardware ACPI platform profile and battery charge threshold via HAL.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "set_profile", "set_conservation"],
                        "description": "Action to perform on hardware tuning subsystem.",
                    },
                    "profile": {
                        "type": "string",
                        "description": "Target ACPI thermal profile name (e.g. 'performance', 'balanced', 'low-power').",
                    },
                    "conservation": {
                        "type": "boolean",
                        "description": "Enable or disable battery charge threshold limit (e.g. 80% / 60%).",
                    },
                },
                "required": ["action"],
            },
        },
    ]


def _format_text_response(text: str, is_error: bool = False) -> Dict[str, Any]:
    """Format tool execution response matching MCP content schema."""
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch and execute MCP tool by name."""
    if name == "osm_safe_exec":
        return _handle_safe_exec(arguments)
    elif name == "osm_system_health":
        return _handle_system_health(arguments)
    elif name == "osm_sandbox_run":
        return _handle_sandbox_run(arguments)
    elif name == "osm_tune":
        return _handle_tune(arguments)
    else:
        return _format_text_response(f"Unknown tool: {name}", is_error=True)


def _handle_safe_exec(args: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("command", "")
    timeout = args.get("timeout_seconds", 30)

    # 1. Pre-flight AST evaluation
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    eval_res = evaluate_payload(payload)

    if not eval_res.allowed:
        return _format_text_response(eval_res.reason, is_error=True)

    # 2. Execute safely
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = res.stdout
        if res.stderr:
            output += ("\n" if output else "") + res.stderr
        return _format_text_response(output if output else "[Command finished with no output]")
    except subprocess.TimeoutExpired:
        return _format_text_response(f"Command timed out after {timeout} seconds", is_error=True)
    except Exception as exc:
        return _format_text_response(f"Execution error: {exc}", is_error=True)


def _handle_system_health(_: Dict[str, Any]) -> Dict[str, Any]:
    plat = detect_platform()
    driver = get_active_hardware_driver()
    prof = driver.get_platform_profile()
    bat = driver.get_battery_conservation()
    dmi = driver.get_dmi_info()
    storage = audit_storage_subsystem("/")

    health_data = {
        "platform": plat,
        "dmi": {
            "vendor": dmi.vendor,
            "product": dmi.product_name,
        },
        "cpu_count": os.cpu_count(),
        "platform_profile": prof.current,
        "platform_choices": prof.choices,
        "battery_conservation": bat.conservation_mode,
        "storage": {
            "device": storage.target_device,
            "scheduler": storage.scheduler,
            "nr_requests": storage.nr_requests,
            "is_nvme": storage.is_nvme,
        },
    }
    return _format_text_response(json.dumps(health_data, indent=2))


def _handle_sandbox_run(args: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("command", "")
    workdir = args.get("workdir", ".")

    # Locate sandbox script
    script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "sandbox_bwrap.sh"
    if not script_path.exists():
        # Fallback to podman sandbox
        script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "sandbox_exec.sh"

    if not script_path.exists():
        return _format_text_response("Sandbox runner script not found.", is_error=True)

    try:
        res = subprocess.run(
            [str(script_path), "--workdir", workdir, "--", cmd],
            capture_output=True,
            text=True,
            check=False,
        )
        out = res.stdout
        if res.stderr:
            out += ("\n" if out else "") + res.stderr
        return _format_text_response(out if out else "[Sandboxed execution completed with no output]")
    except Exception as exc:
        return _format_text_response(f"Sandbox execution error: {exc}", is_error=True)


def _handle_tune(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "status")
    driver = get_active_hardware_driver()

    if action == "status":
        prof = driver.get_platform_profile()
        bat = driver.get_battery_conservation()
        return _format_text_response(
            json.dumps(
                {
                    "profile": prof.current,
                    "available_profiles": prof.choices,
                    "battery_conservation": bat.conservation_mode,
                    "threshold": bat.threshold,
                },
                indent=2,
            )
        )
    elif action == "set_profile":
        target_profile = args.get("profile")
        if not target_profile:
            return _format_text_response("Missing required 'profile' argument", is_error=True)
        try:
            ok = driver.set_platform_profile(target_profile)
            return _format_text_response(f"Profile set to '{target_profile}': {ok}")
        except Exception as exc:
            return _format_text_response(f"Failed to set profile: {exc}", is_error=True)
    elif action == "set_conservation":
        conservation = args.get("conservation", False)
        ok = driver.set_battery_conservation(conservation)
        return _format_text_response(f"Battery conservation set to {conservation}: {ok}")

    return _format_text_response(f"Invalid tuning action: {action}", is_error=True)

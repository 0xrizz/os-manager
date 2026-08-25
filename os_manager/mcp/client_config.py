"""Multi-client MCP configuration installer for Claude Code, Cursor, and Antigravity."""

import json
from pathlib import Path
from typing import Any, Dict, Optional


def _build_mcp_server_entry() -> Dict[str, Any]:
    """Generate standard MCP server configuration block."""
    return {
        "command": "osm",
        "args": ["mcp", "serve"],
        "env": {},
    }


def _update_mcp_json_file(file_path: Path) -> bool:
    """Idempotently add os-manager server entry to a target JSON config file."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}

        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}

        data["mcpServers"]["os-manager"] = _build_mcp_server_entry()
        file_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def install_claude_mcp_config(target_file: Optional[Path] = None) -> bool:
    """Inject os-manager MCP server into Claude Code settings."""
    target = target_file or (Path.home() / ".claude" / "settings.json")
    return _update_mcp_json_file(target)


def install_cursor_mcp_config(target_file: Optional[Path] = None) -> bool:
    """Inject os-manager MCP server into Cursor MCP settings."""
    target = target_file or (Path.home() / ".cursor" / "mcp.json")
    return _update_mcp_json_file(target)


def install_antigravity_mcp_config(target_file: Optional[Path] = None) -> bool:
    """Inject os-manager MCP server into Google Antigravity settings."""
    target = target_file or (Path.home() / ".gemini" / "config" / "mcp.json")
    return _update_mcp_json_file(target)

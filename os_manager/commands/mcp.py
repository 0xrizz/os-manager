"""CLI Command handler for `osm mcp`."""

import argparse
import asyncio
import sys

from os_manager.mcp.client_config import (
    install_antigravity_mcp_config,
    install_claude_mcp_config,
    install_cursor_mcp_config,
)
from os_manager.mcp.server import run_stdio_server
from os_manager.mcp.tools import get_tool_definitions


def run_mcp(argv: list[str]) -> int:
    """Route `osm mcp` subcommands: serve, install, list-tools."""
    parser = argparse.ArgumentParser(
        prog="osm mcp",
        description="Model Context Protocol (MCP) server engine for os-manager.",
    )
    subparsers = parser.add_subparsers(dest="subaction", help="MCP Subcommands")

    subparsers.add_parser("serve", help="Run MCP stdio server daemon")

    install_parser = subparsers.add_parser("install", help="Auto-configure MCP clients")
    install_parser.add_argument(
        "--client",
        choices=["all", "claude", "cursor", "antigravity"],
        default="all",
        help="Target client to configure (default: all)",
    )

    subparsers.add_parser("tools", help="List available MCP tool schemas")

    args = parser.parse_args(argv)

    if args.subaction == "serve":
        try:
            asyncio.run(run_stdio_server())
            return 0
        except KeyboardInterrupt:
            return 0
    elif args.subaction == "install":
        print("=== Configuring MCP Clients for os-manager ===")
        if args.client in ("all", "claude"):
            ok = install_claude_mcp_config()
            print(f" • Claude Code (~/.claude/settings.json) : {'[OK]' if ok else '[FAIL]'}")
        if args.client in ("all", "cursor"):
            ok = install_cursor_mcp_config()
            print(f" • Cursor IDE (~/.cursor/mcp.json)        : {'[OK]' if ok else '[FAIL]'}")
        if args.client in ("all", "antigravity"):
            ok = install_antigravity_mcp_config()
            print(f" • Antigravity (~/.gemini/config/mcp.json): {'[OK]' if ok else '[FAIL]'}")
        return 0
    elif args.subaction == "tools":
        tools = get_tool_definitions()
        print(f"Available MCP Tools ({len(tools)}):")
        for t in tools:
            print(f" • {t['name']:<20} : {t['description']}")
        return 0
    else:
        parser.print_help()
        return 0

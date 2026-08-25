# HANDOFF: Open-Source Transformation Milestone 3 (Native MCP Server & Protocol Engine)

**Date**: 2026-08-25
**Originating Session**: Milestone 2 Execution & Subagent Open-Source Decoupling completed (commit `26e455f`, PR #5 updated).
**Target Next Session**: Execute and verify **Plan 3: Native FastMCP Server & Protocol Engine (Milestone 3)**.
**Execution Method**: `subagent-driven-development`

---

## 1. Context & Artifact References
- **Current Status**:
  - Milestones 1 & 2 fully landed and verified.
  - All 9 subagents in `.claude/agents/` and `.agents/agents/` 100% decoupled and verified with `tests/test_agent_definitions.py`.
  - 269/269 Pytest test suite and 75/75 master harness assertions passing.
  - PR #5: https://github.com/0xrizz/os-manager/pull/5
- **Relevant Artifacts**:
  - Spec: `docs/superpowers/specs/2026-08-24-open-source-transformation-roadmap-design.md` (Sections 2.4, 3.3, 4.3, Mini-RFC 003)
  - Plan: `docs/superpowers/plans/2026-08-24-native-mcp-server-engine.md`
  - Target Modules: `os_manager/mcp/` (server, tools, resources, prompts, auth)
  - Current Branch: `feat/dynamic-hal-registry`
  - Current Commit: `26e455f6feea1ac9c4ea355ac836089e8bb0df26`

---

## 2. Next Session Directives
1. **Step 1 - Load Context**:
   - Read the plan: `docs/superpowers/plans/2026-08-24-native-mcp-server-engine.md`.
   - Read the spec: `docs/superpowers/specs/2026-08-24-open-source-transformation-roadmap-design.md`.
2. **Step 2 - Execute Implementation via Subagent-Driven Development**:
   - Invoke `subagent-driven-development` skill.
   - Dispatch one subagent per task (Tasks 1 through 5) following strict 5-step TDD:
     - **Task 1**: FastMCP Core Server & JSON-RPC Transport (`os_manager/mcp/server.py`).
     - **Task 2**: Model Context Protocol Tools Implementation (`os_manager/mcp/tools/*.py`).
     - **Task 3**: Dynamic Resource & Prompt Provider Subsystem (`os_manager/mcp/resources.py`, `os_manager/mcp/prompts.py`).
     - **Task 4**: CLI MCP Server Command & Subsystem Integration (`osm mcp serve`, `os_manager/commands/mcp.py`).
     - **Task 5**: Full MCP Protocol Test Harness & Integration Suite (`tests/mcp/test_*.py`).
3. **Step 3 - Verification & Tests**:
   - Run python unit tests: `.venv/bin/pytest tests/`.
   - Run master harness suite: `./tests/test_harness.sh` and `./scripts/harness_check.sh`.
4. **Step 4 - Mandatory Cleanup (Rule 2)**:
   - Once all tasks in Plan 3 are completed and verified, **refresh/clear** `.claude/temp/HANDOFF.md` (truncate to 0 bytes / empty file, keep file present).

---

## 3. Suggested Skills for Next Session
- `subagent-driven-development`
- `test-driven-development`
- `verification-before-completion`
- `harness-check`

---

## 4. Technical Constraints & Invariants
- **Non-Blocking Protocol Loops**: FastMCP server must support standard stdio and stream transport without deadlocks.
- **Strict AST Guard Integration**: All mutating tool calls dispatched through MCP must be routed through the AST security policy engine.
- **Fail-Safe Resource Introspection**: MCP resource providers must handle missing sysfs/hardware gracefully with default mockable fallbacks.

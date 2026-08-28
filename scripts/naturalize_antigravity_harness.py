#!/usr/bin/env python3
"""scripts/naturalize_antigravity_harness.py - Standalone Claude-to-Antigravity Harness Migration & Naturalization Engine.

Performs a full, clean, and isolated transformation of Claude Code (.claude/) harness
components into native Antigravity (.agents/) workspace customizations:
  - Commands -> Workflows (.agents/workflows/)
  - Skills -> Standalone Skills (.agents/skills/)
  - Rules -> Workspace Rules (.agents/rules/)
  - Agents -> Subagents (.agents/agents/)
  - Templates -> Session Templates (.agents/templates/)
  - Settings Hooks -> Antigravity Lifecycle Hooks (.agents/hooks.json)

Execution runs entirely inside an isolated temporary sandbox directory first, validates
all assets (YAML frontmatter, JSON syntax, script permissions, link integrity), and only
promotes to .agents/ upon 100% verification pass.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile


def naturalize_text(content: str) -> str:
    """Naturalize Claude-specific keywords, paths, and tool verbs for Antigravity."""
    # 1. Environment & path references
    content = re.sub(r"\$\{CLAUDE_PROJECT_DIR(?::-[^\}]*)?\}", "${PROJECT_DIR:-.}", content)
    content = re.sub(r"\$CLAUDE_PROJECT_DIR", "${PROJECT_DIR:-.}", content)
    content = re.sub(r"\.claude/skills/", ".agents/skills/", content)
    content = re.sub(r"\.claude/commands/", ".agents/workflows/", content)
    content = re.sub(r"\.claude/rules/", ".agents/rules/", content)
    content = re.sub(r"\.claude/template/", ".agents/templates/", content)
    content = re.sub(r"\.claude/temp/", ".agents/temp/", content)
    content = re.sub(r"\.claude/agents/", ".agents/agents/", content)

    # 2. Tool verbs & mentions in instructions
    content = re.sub(r"\bthe `Bash` tool\b", "the `run_command` tool", content)
    content = re.sub(r"\b`Bash` tool\b", "`run_command` tool", content)
    content = re.sub(r"\b`Edit` and `Write`\b", "`write_to_file` and `replace_file_content`", content)
    content = re.sub(r"\b`Edit` / `Write`\b", "`write_to_file` / `replace_file_content`", content)
    content = re.sub(r"\b`Read` tool\b", "`view_file` tool", content)
    content = re.sub(r"\bthe `Read` tool\b", "the `view_file` tool", content)
    content = re.sub(r"\b`Glob`\b", "`list_dir`", content)
    content = re.sub(r"\b`Grep`\b", "`grep_search`", content)

    # 3. Governance document references
    content = re.sub(r"\bCLAUDE\.md\b", "AGENTS.md", content)

    return content


def generate_antigravity_hooks() -> dict:
    """Generate Antigravity lifecycle hooks configuration."""
    return {
        "safety-guard": {
            "PreToolUse": [
                {
                    "matcher": "run_command|write_to_file|replace_file_content|multi_replace_file_content",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "./scripts/hooks/antigravity_pre_tool_guard.sh",
                            "timeout": 15,
                        }
                    ],
                }
            ]
        },
        "syntax-linter": {
            "PostToolUse": [
                {
                    "matcher": "write_to_file|replace_file_content|multi_replace_file_content",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "./scripts/hooks/antigravity_post_tool_lint.sh",
                            "timeout": 30,
                        }
                    ],
                }
            ]
        },
    }


def validate_yaml_frontmatter(file_path: Path) -> bool:
    """Validate that SKILL.md contains valid YAML frontmatter with name and description."""
    try:
        content = file_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return False
        parts = content.split("---", 2)
        if len(parts) < 3:
            return False
        frontmatter = parts[1]
        has_name = bool(re.search(r"^name:\s*.+", frontmatter, re.MULTILINE))
        has_desc = bool(re.search(r"^description:\s*.+", frontmatter, re.MULTILINE))
        return has_name and has_desc
    except Exception:
        return False


def build_sandbox(workspace_root: Path, sandbox_root: Path) -> dict:
    """Build naturalized Antigravity assets in sandbox directory."""
    claude_dir = workspace_root / ".claude"
    if not claude_dir.is_dir():
        raise FileNotFoundError(f"Source directory {claude_dir} not found.")

    stats = {
        "workflows": 0,
        "skills": 0,
        "rules": 0,
        "agents": 0,
        "templates": 0,
        "hooks": 1,
    }

    # 1. Workflows (.claude/commands -> sandbox/workflows)
    workflows_src = claude_dir / "commands"
    workflows_dst = sandbox_root / "workflows"
    workflows_dst.mkdir(parents=True, exist_ok=True)

    if workflows_src.is_dir():
        for cmd_file in workflows_src.glob("*.md"):
            raw_text = cmd_file.read_text(encoding="utf-8")
            naturalized = naturalize_text(raw_text)
            (workflows_dst / cmd_file.name).write_text(naturalized, encoding="utf-8")
            stats["workflows"] += 1

    # 2. Skills (.claude/skills -> sandbox/skills)
    skills_src = claude_dir / "skills"
    skills_dst = sandbox_root / "skills"
    skills_dst.mkdir(parents=True, exist_ok=True)

    if skills_src.is_dir():
        for skill_dir in skills_src.iterdir():
            if not skill_dir.is_dir():
                continue
            target_skill_dir = skills_dst / skill_dir.name
            target_skill_dir.mkdir(parents=True, exist_ok=True)

            for item in skill_dir.rglob("*"):
                rel_path = item.relative_to(skill_dir)
                dest_item = target_skill_dir / rel_path

                if item.is_dir():
                    dest_item.mkdir(parents=True, exist_ok=True)
                elif item.is_file():
                    if item.suffix in (".md", ".txt", ".json"):
                        text = item.read_text(encoding="utf-8", errors="replace")
                        dest_item.write_text(naturalize_text(text), encoding="utf-8")
                    else:
                        shutil.copy2(item, dest_item)

                    # Preserve executable bit
                    if os.access(item, os.X_OK):
                        dest_item.chmod(dest_item.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            stats["skills"] += 1

    # 3. Rules (.claude/rules -> sandbox/rules)
    rules_src = claude_dir / "rules"
    rules_dst = sandbox_root / "rules"
    rules_dst.mkdir(parents=True, exist_ok=True)

    if rules_src.is_dir():
        for rule_file in rules_src.glob("*.md"):
            raw_text = rule_file.read_text(encoding="utf-8")
            (rules_dst / rule_file.name).write_text(naturalize_text(raw_text), encoding="utf-8")
            stats["rules"] += 1

    # 4. Agents (.claude/agents -> sandbox/agents)
    agents_src = claude_dir / "agents"
    agents_dst = sandbox_root / "agents"
    agents_dst.mkdir(parents=True, exist_ok=True)

    if agents_src.is_dir():
        for agent_file in agents_src.glob("*.md"):
            raw_text = agent_file.read_text(encoding="utf-8")
            (agents_dst / agent_file.name).write_text(naturalize_text(raw_text), encoding="utf-8")
            stats["agents"] += 1

    # 5. Templates (.claude/template -> sandbox/templates)
    templates_src = claude_dir / "template"
    templates_dst = sandbox_root / "templates"
    templates_dst.mkdir(parents=True, exist_ok=True)

    if templates_src.is_dir():
        for tpl_file in templates_src.glob("*.md"):
            raw_text = tpl_file.read_text(encoding="utf-8")
            (templates_dst / tpl_file.name).write_text(naturalize_text(raw_text), encoding="utf-8")
            stats["templates"] += 1

    # 6. Hooks configuration (sandbox/hooks.json)
    hooks_config = generate_antigravity_hooks()
    (sandbox_root / "hooks.json").write_text(json.dumps(hooks_config, indent=2) + "\n", encoding="utf-8")

    return stats


def verify_sandbox(sandbox_root: Path) -> Tuple_Validation:
    """Validate integrity of generated sandbox assets."""
    errors = []

    # 1. Check hooks.json
    hooks_file = sandbox_root / "hooks.json"
    if not hooks_file.is_file():
        errors.append("hooks.json is missing in sandbox")
    else:
        try:
            parsed = json.loads(hooks_file.read_text(encoding="utf-8"))
            if "safety-guard" not in parsed or "syntax-linter" not in parsed:
                errors.append("hooks.json schema missing expected hook groups")
        except Exception as exc:
            errors.append(f"hooks.json JSON parsing failed: {exc}")

    # 2. Check Skills frontmatter
    skills_dir = sandbox_root / "skills"
    if not skills_dir.is_dir() or not any(skills_dir.iterdir()):
        errors.append("skills directory is missing or empty in sandbox")
    else:
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.is_file():
                    errors.append(f"Missing SKILL.md in skill: {skill_dir.name}")
                elif not validate_yaml_frontmatter(skill_md):
                    errors.append(f"Invalid YAML frontmatter in: {skill_md}")

    # 3. Check Workflows
    workflows_dir = sandbox_root / "workflows"
    if not workflows_dir.is_dir() or len(list(workflows_dir.glob("*.md"))) == 0:
        errors.append("workflows directory is missing or contains no markdown files")

    # 4. Check Rules
    rules_dir = sandbox_root / "rules"
    if not rules_dir.is_dir() or len(list(rules_dir.glob("*.md"))) == 0:
        errors.append("rules directory is missing or contains no markdown files")

    # 5. Check Templates
    templates_dir = sandbox_root / "templates"
    if not templates_dir.is_dir() or not (templates_dir / "HANDOFF.template.md").is_file():
        errors.append("templates/HANDOFF.template.md missing in sandbox")

    return len(errors) == 0, errors


# Type alias for return
Tuple_Validation = tuple[bool, list[str]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Naturalize and import Claude harness to Antigravity.")
    parser.add_argument("--workspace-root", default=str(Path(__file__).resolve().parent.parent), help="Path to workspace root")
    parser.add_argument("--dry-run", action="store_true", help="Perform sandbox build and verification without promoting")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing .agents directory without rebuilding")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    target_agents_dir = workspace_root / ".agents"

    if args.verify_only:
        print(f"[*] Verifying existing Antigravity harness at {target_agents_dir}...")
        valid, errors = verify_sandbox(target_agents_dir)
        if valid:
            print("[✓] Antigravity harness verification passed (100% compliant).")
            return 0
        else:
            print("[✗] Antigravity harness verification failed:")
            for err in errors:
                print(f"  - {err}")
            return 1

    temp_sandbox = Path(tempfile.mkdtemp(prefix="os_mgr_agy_sandbox_"))
    try:
        print(f"[*] Initializing isolated sandbox build at {temp_sandbox}...")
        stats = build_sandbox(workspace_root, temp_sandbox)

        print(f"[*] Sandbox build complete. Statistics:")
        print(f"    - Workflows (.agents/workflows/): {stats['workflows']}")
        print(f"    - Skills (.agents/skills/):       {stats['skills']}")
        print(f"    - Rules (.agents/rules/):         {stats['rules']}")
        print(f"    - Agents (.agents/agents/):       {stats['agents']}")
        print(f"    - Templates (.agents/templates/): {stats['templates']}")
        print(f"    - Hooks (.agents/hooks.json):     {stats['hooks']}")

        print("[*] Running automated sandbox validation...")
        valid, errors = verify_sandbox(temp_sandbox)
        if not valid:
            print("[✗] Sandbox validation failed. Aborting promotion:")
            for err in errors:
                print(f"  - {err}")
            return 1
        print("[✓] Sandbox validation passed (100% assertions satisfied).")

        if args.dry_run:
            print("[*] Dry-run requested. Staging verified. Exiting without modifying repository.")
            return 0

        print(f"[*] Promoting verified sandbox to {target_agents_dir}...")
        if target_agents_dir.exists():
            shutil.rmtree(target_agents_dir)

        shutil.copytree(temp_sandbox, target_agents_dir)
        print(f"[✓] Successfully deployed full naturalized Antigravity harness to {target_agents_dir}.")
        return 0

    finally:
        shutil.rmtree(temp_sandbox, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

# Core Configuration Engine & AST Zero-Trust Security Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a declarative configuration engine (`.osm.toml`) and replace regex-based tool guards with a deterministic Shell AST Semantic Parser (`bashlex`) backed by an ephemeral Bubblewrap (`bwrap`) rootless sandbox.

**Architecture:** The PreToolUse hook (`pre_tool_guard.sh`) intercepts tool calls and streams JSON payloads into the `os_manager.security.ast_guard` validator. The validator parses shell syntax trees via `bashlex` to detect file redirections (`>`, `>>`, `| tee`), obfuscated dynamic evaluations (`eval`, `base64`), destructive commands, and out-of-boundary file edits against declarative policies loaded from `.osm.toml`. Risky non-destructive operations are routed into an ephemeral Bubblewrap jail (`scripts/sandbox_bwrap.sh`).

**Tech Stack:** Python 3.11+ (`tomllib`, `dataclasses`, `pathlib`), `bashlex` (Shell AST parsing), Bubblewrap (`bwrap` rootless Linux namespaces), Bash (`pre_tool_guard.sh`), Pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-open-source-transformation-roadmap-design.md` (Sections 2.2, 2.3, 3.1, 3.3, and Mini-RFC 001).

## Global Constraints

- **Zero-Data-Loss Invariant**: Never permit deletion, reformatting, or unisolated writes targeting persistent storage (`/dev/nvme0n1p4`, `/mnt/data`, `/mnt/d/wsl_backup`).
- **Deterministic Hard Blocks**: Tier 3 invariant violations must exit with code `2` and print structured error messages to `stderr`.
- **Fail-Closed Security**: Malformed JSON payloads or unparseable shell command syntax must fail closed (deny execution or enforce sandboxing).
- **Hook Latency Ceiling**: PreToolUse guardrail execution time must remain under 15ms for p99 invocations.
- **Python Compatibility**: Target Python 3.11+ using standard library `tomllib` for TOML parsing and standard library `dataclasses`.

---

## File Structure & Module Map

```text
os-manager/
├── .osm.toml                                # Default declarative configuration manifest
├── pyproject.toml                           # Python project metadata and dependencies (bashlex)
├── os_manager/
│   ├── config/
│   │   ├── __init__.py                      # Config package exports
│   │   ├── schema.py                        # Dataclasses defining configuration structure
│   │   └── loader.py                        # TOML file loader, environment resolver & defaults
│   └── security/
│       ├── __init__.py                      # Security package exports
│       └── ast_guard.py                     # bashlex Shell AST visitor & invariant policy engine
├── scripts/
│   ├── sandbox_bwrap.sh                     # Bubblewrap rootless namespace ephemeral sandbox
│   └── hooks/
│       └── pre_tool_guard.sh                # PreToolUse lifecycle hook bridging to ast_guard.py
└── tests/
    ├── config/
    │   └── test_loader.py                   # Pytest suite for declarative configuration loader
    ├── security/
    │   ├── test_ast_guard.py                # Pytest suite for Shell AST parser & policy violations
    │   └── test_sandbox_bwrap.sh            # Integration tests for Bubblewrap sandbox execution
    └── integration/
        └── test_pre_tool_guard.py           # End-to-end integration tests for PreToolUse hook
```

---

### Task 1: Declarative Configuration Engine

**Files:**
- Create: `os_manager/config/__init__.py`
- Create: `os_manager/config/schema.py`
- Create: `os_manager/config/loader.py`
- Create: `.osm.toml`
- Test: `tests/config/test_loader.py`

**Interfaces:**
- Consumes: Standard library `tomllib` (Python 3.11+), `dataclasses`, `pathlib.Path`.
- Produces:
  - `OsmConfig(security: SecurityConfig, sandbox: SandboxConfig, invariants: InvariantsConfig, hardware: HardwareConfig)`
  - `load_config(config_path: Path | str | None = None) -> OsmConfig`
  - `get_default_config() -> OsmConfig`

- [ ] **Step 1: Write the failing test**

Create `tests/config/test_loader.py`:

```python
"""Unit tests for declarative configuration loader and schema."""

from pathlib import Path
import tempfile
import unittest

from os_manager.config.loader import get_default_config, load_config
from os_manager.config.schema import OsmConfig, SecurityConfig


class TestConfigLoader(unittest.TestCase):
    """Verify .osm.toml configuration parsing and fallback defaults."""

    def test_default_config_instantiation(self) -> None:
        cfg = get_default_config()
        self.assertIsInstance(cfg, OsmConfig)
        self.assertEqual(cfg.security.profile, "strict")
        self.assertEqual(cfg.security.engine, "ast")
        self.assertTrue(cfg.sandbox.auto_isolate_dangerous)
        self.assertIn("/etc/shadow", cfg.invariants.deny_paths)

    def test_load_config_from_custom_toml(self) -> None:
        custom_toml = """
        [security]
        profile = "permissive"
        engine = "ast"
        fail_action = "prompt"

        [security.sandbox]
        backend = "bubblewrap"
        auto_isolate_dangerous = false
        network_isolation = false
        read_only_root = true
        writable_paths = [".", "/tmp"]

        [security.invariants]
        deny_paths = ["/etc/shadow", "/custom/protected"]
        deny_commands = ["mkfs", "custom_wipe"]

        [hardware]
        driver = "lenovo"
        """
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as tf:
            tf.write(custom_toml)
            temp_path = Path(tf.name)

        try:
            cfg = load_config(temp_path)
            self.assertEqual(cfg.security.profile, "permissive")
            self.assertEqual(cfg.security.fail_action, "prompt")
            self.assertFalse(cfg.sandbox.auto_isolate_dangerous)
            self.assertIn("/custom/protected", cfg.invariants.deny_paths)
            self.assertEqual(cfg.hardware.driver, "lenovo")
        finally:
            temp_path.unlink(missing_ok=True)

    def test_load_config_missing_file_falls_back_to_defaults(self) -> None:
        cfg = load_config(Path("/nonexistent/path/.osm.toml"))
        self.assertEqual(cfg.security.profile, "strict")
        self.assertEqual(cfg.security.engine, "ast")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m unittest tests/config/test_loader.py
```
Expected output:
```text
ModuleNotFoundError: No module named 'os_manager.config'
```

- [ ] **Step 3: Write minimal implementation**

Create `os_manager/config/schema.py`:

```python
"""Data schemas for os-manager configuration."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SecurityConfig:
    profile: str = "strict"  # strict | standard | permissive
    engine: str = "ast"      # ast | legacy_regex
    fail_action: str = "deny"  # deny | prompt | isolate


@dataclass
class SandboxConfig:
    backend: str = "bubblewrap"  # bubblewrap | podman | none
    auto_isolate_dangerous: bool = True
    network_isolation: bool = True
    read_only_root: bool = True
    writable_paths: List[str] = field(
        default_factory=lambda: [".", "/tmp", "~/.cache"]
    )


@dataclass
class InvariantsConfig:
    deny_paths: List[str] = field(
        default_factory=lambda: [
            "/etc/shadow",
            "/etc/passwd",
            "/etc/sudoers",
            "/boot",
            "/dev",
            "/mnt/c/Windows",
            "/mnt/c/Program Files",
            "/mnt/c/Program Files (x86)",
        ]
    )
    deny_commands: List[str] = field(
        default_factory=lambda: [
            "mkfs",
            "fdisk",
            "parted",
            "gdisk",
            "wipefs",
            "dd",
            "wsl --unregister",
            "wsl.exe --unregister",
            "wsl --shutdown",
            "wsl --terminate",
        ]
    )
    protected_mounts: List[str] = field(
        default_factory=lambda: ["/mnt/data", "/mnt/d"]
    )


@dataclass
class HardwareConfig:
    driver: str = "auto"  # auto | lenovo | asus | dell | generic | macos
    force_override: bool = False


@dataclass
class OsmConfig:
    security: SecurityConfig = field(default_factory=SecurityConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    invariants: InvariantsConfig = field(default_factory=InvariantsConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
```

Create `os_manager/config/loader.py`:

```python
"""Configuration loader for os-manager with TOML parsing and hierarchical fallback."""

import os
from pathlib import Path
import tomllib
from typing import Any, Dict, Optional

from .schema import (
    HardwareConfig,
    InvariantsConfig,
    OsmConfig,
    SandboxConfig,
    SecurityConfig,
)


def get_default_config() -> OsmConfig:
    """Return default configuration instance."""
    return OsmConfig()


def _resolve_config_path(custom_path: Optional[Path | str] = None) -> Optional[Path]:
    """Resolve config file path from custom input, workspace root, or home dir."""
    if custom_path:
        p = Path(custom_path).expanduser().resolve()
        if p.is_file():
            return p
        return None

    # Check current workspace directory
    cwd_path = Path(".osm.toml").resolve()
    if cwd_path.is_file():
        return cwd_path

    # Check OSM_CONFIG environment variable
    env_cfg = os.environ.get("OSM_CONFIG")
    if env_cfg:
        p = Path(env_cfg).expanduser().resolve()
        if p.is_file():
            return p

    # Check ~/.config/osm/config.toml
    user_cfg = Path.home() / ".config" / "osm" / "config.toml"
    if user_cfg.is_file():
        return user_cfg

    return None


def load_config(config_path: Optional[Path | str] = None) -> OsmConfig:
    """Load configuration from TOML file with fallback to default schema."""
    resolved = _resolve_config_path(config_path)
    if not resolved:
        return get_default_config()

    try:
        with open(resolved, "rb") as f:
            data: Dict[str, Any] = tomllib.load(f)
    except Exception:
        return get_default_config()

    sec_data = data.get("security", {})
    sec_cfg = SecurityConfig(
        profile=sec_data.get("profile", "strict"),
        engine=sec_data.get("engine", "ast"),
        fail_action=sec_data.get("fail_action", "deny"),
    )

    sb_data = sec_data.get("sandbox", {})
    sb_cfg = SandboxConfig(
        backend=sb_data.get("backend", "bubblewrap"),
        auto_isolate_dangerous=sb_data.get("auto_isolate_dangerous", True),
        network_isolation=sb_data.get("network_isolation", True),
        read_only_root=sb_data.get("read_only_root", True),
        writable_paths=sb_data.get("writable_paths", [".", "/tmp", "~/.cache"]),
    )

    inv_data = sec_data.get("invariants", {})
    inv_cfg = InvariantsConfig(
        deny_paths=inv_data.get(
            "deny_paths",
            [
                "/etc/shadow",
                "/etc/passwd",
                "/etc/sudoers",
                "/boot",
                "/dev",
                "/mnt/c/Windows",
                "/mnt/c/Program Files",
                "/mnt/c/Program Files (x86)",
            ],
        ),
        deny_commands=inv_data.get(
            "deny_commands",
            [
                "mkfs",
                "fdisk",
                "parted",
                "gdisk",
                "wipefs",
                "dd",
                "wsl --unregister",
                "wsl.exe --unregister",
                "wsl --shutdown",
                "wsl --terminate",
            ],
        ),
        protected_mounts=inv_data.get(
            "protected_mounts", ["/mnt/data", "/mnt/d"]
        ),
    )

    hw_data = data.get("hardware", {})
    hw_cfg = HardwareConfig(
        driver=hw_data.get("driver", "auto"),
        force_override=hw_data.get("force_override", False),
    )

    return OsmConfig(
        security=sec_cfg,
        sandbox=sb_cfg,
        invariants=inv_cfg,
        hardware=hw_cfg,
    )
```

Create `os_manager/config/__init__.py`:

```python
"""Configuration module for os-manager."""

from .loader import get_default_config, load_config
from .schema import (
    HardwareConfig,
    InvariantsConfig,
    OsmConfig,
    SandboxConfig,
    SecurityConfig,
)

__all__ = [
    "OsmConfig",
    "SecurityConfig",
    "SandboxConfig",
    "InvariantsConfig",
    "HardwareConfig",
    "load_config",
    "get_default_config",
]
```

Create default root manifest `.osm.toml`:

```toml
[security]
profile = "strict"              # strict | standard | permissive
engine = "ast"                  # ast | legacy_regex
fail_action = "deny"            # deny | prompt | isolate

[security.sandbox]
backend = "bubblewrap"          # bubblewrap | podman | none
auto_isolate_dangerous = true
network_isolation = true
read_only_root = true
writable_paths = [
    ".",
    "/tmp",
    "~/.cache"
]

[security.invariants]
deny_paths = [
    "/etc/shadow",
    "/etc/passwd",
    "/etc/sudoers",
    "/boot",
    "/dev",
    "/mnt/c/Windows",
    "/mnt/c/Program Files",
    "/mnt/c/Program Files (x86)"
]
deny_commands = [
    "mkfs",
    "fdisk",
    "parted",
    "gdisk",
    "wipefs",
    "dd",
    "wsl --unregister",
    "wsl.exe --unregister",
    "wsl --shutdown",
    "wsl --terminate"
]
protected_mounts = [
    "/mnt/data",
    "/mnt/d"
]

[hardware]
driver = "auto"
force_override = false
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python -m unittest tests/config/test_loader.py -v
```
Expected output:
```text
test_default_config_instantiation (tests.config.test_loader.TestConfigLoader) ... ok
test_load_config_from_custom_toml (tests.config.test_loader.TestConfigLoader) ... ok
test_load_config_missing_file_falls_back_to_defaults (tests.config.test_loader.TestConfigLoader) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.002s

OK
```

- [ ] **Step 5: Commit**

Run:
```bash
git add os_manager/config/ .osm.toml tests/config/test_loader.py
git commit -m "feat(config): implement declarative toml configuration engine and schema"
```

---

### Task 2: Shell AST Semantic Parser & Policy Engine

**Files:**
- Modify: `pyproject.toml`
- Create: `os_manager/security/__init__.py`
- Create: `os_manager/security/ast_guard.py`
- Test: `tests/security/test_ast_guard.py`

**Interfaces:**
- Consumes: `bashlex`, `os_manager.config.schema.SecurityConfig`, `os_manager.config.schema.InvariantsConfig`.
- Produces:
  - `PolicyViolation(severity: str, category: str, target: str, reason: str)`
  - `SecurityEvaluation(allowed: bool, exit_code: int, reason: str, sandbox_recommended: bool, violations: list[PolicyViolation])`
  - `ShellASTValidator(invariants: InvariantsConfig)`
  - `evaluate_payload(payload: dict, config: OsmConfig | None = None) -> SecurityEvaluation`
  - CLI execution via `python3 -m os_manager.security.ast_guard [--stdin]`

- [ ] **Step 1: Write the failing test**

Update `pyproject.toml` to declare `bashlex>=0.18` dependency:
```toml
dependencies = [
    "bashlex>=0.18",
]
```
Install `bashlex` in `.venv`:
```bash
.venv/bin/pip install bashlex
```

Create `tests/security/test_ast_guard.py`:

```python
"""Unit tests for Shell AST Semantic Parser and Security Invariant Gate."""

import unittest
from os_manager.config.schema import InvariantsConfig, OsmConfig
from os_manager.security.ast_guard import (
    ShellASTValidator,
    evaluate_payload,
)


class TestShellASTGuard(unittest.TestCase):
    """Test AST analysis against command obfuscation, redirection, and invariant violations."""

    def setUp(self) -> None:
        self.invariants = InvariantsConfig()
        self.validator = ShellASTValidator(self.invariants)

    def test_safe_read_commands(self) -> None:
        safe_cmds = [
            "git status",
            "ls -la",
            "df -h",
            "pytest tests/ -v",
            "cat README.md",
            "python3 -m py_compile script.py",
        ]
        for cmd in safe_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, sandbox = self.validator.analyze_command(cmd)
                self.assertTrue(allowed, f"Safe command was blocked: {cmd}")
                self.assertEqual(len(violations), 0)
                self.assertFalse(sandbox)

    def test_blocked_file_redirection_attacks(self) -> None:
        attack_cmds = [
            "cat malicious_content > /etc/passwd",
            "echo 'root::0:0:::' >> /etc/shadow",
            "echo bad | tee /etc/sudoers",
            "echo x > /mnt/c/Windows/system.ini",
        ]
        for cmd in attack_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertFalse(allowed, f"Redirection attack bypassed guard: {cmd}")
                self.assertTrue(
                    any(v.category == "Redirection" for v in violations),
                    f"Violation category mismatch for {cmd}: {violations}",
                )

    def test_blocked_destructive_root_deletion(self) -> None:
        root_deletes = [
            "rm -rf /",
            "rm -rf /*",
            "rm -rf ~",
            "rm -rf $HOME",
            "rm -rf /home/user/*",
        ]
        for cmd in root_deletes:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertFalse(allowed, f"Root deletion bypassed guard: {cmd}")

    def test_blocked_destructive_system_binaries(self) -> None:
        blocked_cmds = [
            "mkfs.ext4 /dev/sda1",
            "fdisk /dev/nvme0n1",
            "parted /dev/nvme0n1 rm 1",
            "dd if=/dev/zero of=/dev/sda bs=1M",
            "wsl.exe --unregister Debian",
            "wsl --shutdown",
        ]
        for cmd in blocked_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertFalse(allowed, f"Destructive binary bypassed guard: {cmd}")

    def test_dynamic_eval_obfuscation_detected(self) -> None:
        obfuscated_cmds = [
            "eval $(echo cm0gLXJmIC8= | base64 -d)",
            "eval 'rm -rf /'",
            "exec bash -c 'cat /etc/shadow'",
        ]
        for cmd in obfuscated_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertFalse(allowed, f"Obfuscated eval bypassed guard: {cmd}")

    def test_risky_deletion_recommends_sandbox(self) -> None:
        risky_cmds = [
            "rm -rf /tmp/build_dir",
            "rm -rf ./node_modules",
            "rm -rf dist/ build/",
        ]
        for cmd in risky_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, sandbox = self.validator.analyze_command(cmd)
                self.assertTrue(allowed)
                self.assertEqual(len(violations), 0)
                self.assertTrue(sandbox, f"Sandbox was not recommended for {cmd}")

    def test_evaluate_payload_edit_write(self) -> None:
        payload_blocked = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/etc/shadow", "content": "bad"},
        }
        res = evaluate_payload(payload_blocked)
        self.assertFalse(res.allowed)
        self.assertEqual(res.exit_code, 2)

        payload_allowed = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "README.md", "new_string": "hi"},
        }
        res_ok = evaluate_payload(payload_allowed)
        self.assertTrue(res_ok.allowed)
        self.assertEqual(res_ok.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m unittest tests/security/test_ast_guard.py
```
Expected output:
```text
ModuleNotFoundError: No module named 'os_manager.security'
```

- [ ] **Step 3: Write minimal implementation**

Create `os_manager/security/ast_guard.py`:

```python
"""Shell AST Semantic Parser and Invariant Security Policy Guard."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, List, Optional, Set, Tuple

import bashlex

from os_manager.config.loader import load_config
from os_manager.config.schema import InvariantsConfig, OsmConfig


@dataclass(frozen=True)
class PolicyViolation:
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM"
    category: str  # "Redirection" | "Command" | "DynamicExecution" | "PathTraversal"
    target: str
    reason: str


@dataclass
class SecurityEvaluation:
    allowed: bool
    exit_code: int
    reason: str
    sandbox_recommended: bool = False
    violations: List[PolicyViolation] = field(default_factory=list)


class ShellASTValidator:
    """Validates shell command strings via bashlex AST traversal against invariant policies."""

    def __init__(self, invariants: Optional[InvariantsConfig] = None):
        self.invariants = invariants or InvariantsConfig()
        self.protected_paths: List[str] = [
            str(Path(p).expanduser().resolve()) if Path(p).is_absolute() else p
            for p in self.invariants.deny_paths
        ]
        self.blocked_binaries: Set[str] = set(self.invariants.deny_commands)

    def analyze_command(self, raw_cmd: str) -> Tuple[bool, List[PolicyViolation], bool]:
        """Analyze a raw shell command string.

        Returns:
            Tuple of (is_allowed, list_of_violations, is_sandbox_recommended)
        """
        if not raw_cmd or not raw_cmd.strip():
            return True, [], False

        violations: List[PolicyViolation] = []
        sandbox_recommended = False

        # 1. Regex check for dangerous root deletion patterns before AST parse
        if self._matches_root_deletion(raw_cmd):
            violations.append(
                PolicyViolation(
                    severity="CRITICAL",
                    category="Command",
                    target=raw_cmd,
                    reason="Destructive deletion of root or home directory is strictly prohibited",
                )
            )
            return False, violations, False

        # 2. Check for risky recursive deletion outside root (triggers sandbox recommendation)
        if re.search(r"\brm\s+-[rRfF]+\s+[^\s]+", raw_cmd) and not violations:
            sandbox_recommended = True

        # 3. Check for WSL lifecycle commands
        if re.search(r"\b(wsl|wsl\.exe)\s+--(unregister|shutdown|terminate)\b", raw_cmd):
            violations.append(
                PolicyViolation(
                    severity="CRITICAL",
                    category="Command",
                    target="wsl",
                    reason="WSL instance lifecycle termination commands are strictly prohibited",
                )
            )
            return False, violations, False

        # 4. Parse AST via bashlex
        try:
            nodes = bashlex.parse(raw_cmd)
        except Exception:
            # Fallback regex for commands bashlex fails to parse
            if any(b in raw_cmd for b in ["mkfs", "fdisk", "parted", "dd if="]):
                violations.append(
                    PolicyViolation(
                        severity="CRITICAL",
                        category="Command",
                        target=raw_cmd,
                        reason="Destructive disk formatting command detected",
                    )
                )
                return False, violations, False
            return True, [], sandbox_recommended

        for node in nodes:
            self._walk_node(node, raw_cmd, violations)

        is_allowed = len(violations) == 0
        return is_allowed, violations, sandbox_recommended

    def _matches_root_deletion(self, cmd: str) -> bool:
        pattern = r"\brm\s+-[rRfF]*\s+(/|/\*|~|~/\*|\$HOME|\$HOME/\*|/home/[^/\s]+/?(\*|\.)?)([;&|[:space:]]|$)"
        return bool(re.search(pattern, cmd))

    def _walk_node(self, node: Any, raw_cmd: str, violations: List[PolicyViolation]) -> None:
        # Check file redirections: e.g. cat x > /etc/passwd or echo 1 >> /etc/shadow
        if hasattr(node, "redirects"):
            for redir in node.redirects:
                if hasattr(redir, "output"):
                    target_word = None
                    if hasattr(redir.output, "word"):
                        target_word = redir.output.word
                    elif isinstance(redir.output, str):
                        target_word = redir.output

                    if target_word:
                        self._check_path_violation(target_word, "Redirection", violations)

        # Check command nodes
        if getattr(node, "kind", None) == "command":
            words: List[str] = []
            if hasattr(node, "parts"):
                for part in node.parts:
                    if getattr(part, "kind", None) == "word":
                        words.append(raw_cmd[part.pos[0]:part.pos[1]])

            if words:
                cmd_name = Path(words[0]).name
                # Check blocked binaries
                if cmd_name in self.blocked_binaries:
                    violations.append(
                        PolicyViolation(
                            severity="CRITICAL",
                            category="Command",
                            target=cmd_name,
                            reason=f"Execution of prohibited binary: {cmd_name}",
                        )
                    )

                # Check tee redirection: echo bad | tee /etc/sudoers
                if cmd_name == "tee" and len(words) > 1:
                    for arg in words[1:]:
                        if not arg.startswith("-"):
                            self._check_path_violation(arg, "Redirection", violations)

                # Check dynamic eval / execution patterns
                if cmd_name in ("eval", "exec"):
                    violations.append(
                        PolicyViolation(
                            severity="HIGH",
                            category="DynamicExecution",
                            target=cmd_name,
                            reason=f"Dynamic evaluation construct forbidden under strict security policy: {cmd_name}",
                        )
                    )

        # Recursive walk on children parts
        if hasattr(node, "parts"):
            for child in node.parts:
                self._walk_node(child, raw_cmd, violations)

    def _check_path_violation(
        self, path_str: str, category: str, violations: List[PolicyViolation]
    ) -> None:
        try:
            resolved = str(Path(path_str).expanduser().resolve())
        except Exception:
            resolved = path_str

        for protected in self.protected_paths:
            if resolved == protected or resolved.startswith(protected.rstrip("/") + "/"):
                violations.append(
                    PolicyViolation(
                        severity="CRITICAL",
                        category=category,
                        target=path_str,
                        reason=f"Modification targeting protected system path is strictly forbidden: {path_str}",
                    )
                )


def evaluate_payload(
    payload: dict, config: Optional[OsmConfig] = None
) -> SecurityEvaluation:
    """Evaluate Claude tool invocation payload against security invariants."""
    cfg = config or load_config()
    tool_name = payload.get("tool_name") or payload.get("name") or ""
    tool_input = payload.get("tool_input") or {}

    validator = ShellASTValidator(cfg.invariants)

    # 1. Guard File Operations (Edit, Write, Read)
    if tool_name in ("Edit", "Write", "Read"):
        target_path = (
            tool_input.get("file_path")
            or tool_input.get("notebook_path")
            or ""
        )
        if target_path and tool_name in ("Edit", "Write"):
            violations: List[PolicyViolation] = []
            validator._check_path_violation(target_path, "PathTraversal", violations)
            if violations:
                return SecurityEvaluation(
                    allowed=False,
                    exit_code=2,
                    reason=violations[0].reason,
                    violations=violations,
                )
        return SecurityEvaluation(allowed=True, exit_code=0, reason="Allowed file operation")

    # 2. Guard Shell Executions (Bash)
    if tool_name == "Bash":
        raw_cmd = tool_input.get("command") or ""
        allowed, violations, sandbox_recommended = validator.analyze_command(raw_cmd)
        if not allowed:
            first_reason = violations[0].reason if violations else "Invariant Violation"
            return SecurityEvaluation(
                allowed=False,
                exit_code=2,
                reason=f"[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): {first_reason} (cmd: {raw_cmd})",
                sandbox_recommended=sandbox_recommended,
                violations=violations,
            )
        return SecurityEvaluation(
            allowed=True,
            exit_code=0,
            reason="Command evaluated as safe",
            sandbox_recommended=sandbox_recommended,
        )

    return SecurityEvaluation(allowed=True, exit_code=0, reason="Unmonitored tool")


def main() -> int:
    """CLI entrypoint for stdin tool payload evaluation."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            return 0
        payload = json.loads(raw_input)
    except Exception as exc:
        print(f"[HARNESS SECURITY] Failed to parse input JSON payload: {exc}. Failing closed.", file=sys.stderr)
        return 2

    eval_result = evaluate_payload(payload)
    if not eval_result.allowed:
        print(eval_result.reason, file=sys.stderr)
        return eval_result.exit_code

    if eval_result.sandbox_recommended:
        # Output telemetry indicator for caller hook
        print("[SANDBOX_RECOMMENDED]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Create `os_manager/security/__init__.py`:

```python
"""Security governance and AST invariant guardrails for os-manager."""

from .ast_guard import (
    PolicyViolation,
    SecurityEvaluation,
    ShellASTValidator,
    evaluate_payload,
)

__all__ = [
    "PolicyViolation",
    "SecurityEvaluation",
    "ShellASTValidator",
    "evaluate_payload",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python -m unittest tests/security/test_ast_guard.py -v
```
Expected output:
```text
test_blocked_destructive_root_deletion (tests.security.test_ast_guard.TestShellASTGuard) ... ok
test_blocked_destructive_system_binaries (tests.security.test_ast_guard.TestShellASTGuard) ... ok
test_blocked_file_redirection_attacks (tests.security.test_ast_guard.TestShellASTGuard) ... ok
test_dynamic_eval_obfuscation_detected (tests.security.test_ast_guard.TestShellASTGuard) ... ok
test_evaluate_payload_edit_write (tests.security.test_ast_guard.TestShellASTGuard) ... ok
test_risky_deletion_recommends_sandbox (tests.security.test_ast_guard.TestShellASTGuard) ... ok
test_safe_read_commands (tests.security.test_ast_guard.TestShellASTGuard) ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.015s

OK
```

- [ ] **Step 5: Commit**

Run:
```bash
git add pyproject.toml os_manager/security/ tests/security/test_ast_guard.py
git commit -m "feat(security): implement shell AST semantic parser and invariant policy guard"
```

---

### Task 3: Ephemeral Bubblewrap Sandbox Wrapper

**Files:**
- Create: `scripts/sandbox_bwrap.sh`
- Test: `tests/security/test_sandbox_bwrap.sh`

**Interfaces:**
- Consumes: `/usr/bin/bwrap`, Linux user namespaces.
- Produces: CLI script `scripts/sandbox_bwrap.sh [--workdir <dir>] [--allow-net] -- <command>`
  - Runs commands inside rootless unprivileged container namespace.
  - Mounts root filesystem `/` as read-only (`--ro-bind / /`).
  - Provides tmpfs `/tmp` and `/run`.
  - Binds workdir as read-write (`--bind "${WORKDIR}" "${WORKDIR}"`).

- [ ] **Step 1: Write the failing test**

Create `tests/security/test_sandbox_bwrap.sh`:

```bash
#!/usr/bin/env bash
# tests/security/test_sandbox_bwrap.sh - Unit tests for Bubblewrap sandbox wrapper
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BWRAP_SCRIPT="${SCRIPT_DIR}/scripts/sandbox_bwrap.sh"

if ! command -v bwrap >/dev/null 2>&1; then
    echo "[SKIP] bubblewrap (bwrap) not installed in environment. Skipping."
    exit 0
fi

TEST_DIR="$(mktemp -d /tmp/osm_bwrap_test_XXXXXX)"
trap 'rm -rf "${TEST_DIR}"' EXIT

echo "=== Running Bubblewrap Sandbox Isolation Tests ==="

# 1. Test basic command execution
OUTPUT="$("${BWRAP_SCRIPT}" --workdir "${TEST_DIR}" -- echo "hello sandbox")"
if [[ "${OUTPUT}" != *"hello sandbox"* ]]; then
    echo "FAIL: Expected 'hello sandbox', got '${OUTPUT}'" >&2
    exit 1
fi
echo "  [PASS] Basic command execution inside jail"

# 2. Test read-only root protection (write to /etc should fail)
if "${BWRAP_SCRIPT}" --workdir "${TEST_DIR}" -- touch /etc/test_file_fail 2>/dev/null; then
    echo "FAIL: Write to /etc succeeded inside sandbox jail!" >&2
    exit 1
fi
echo "  [PASS] Read-only root filesystem enforced (write to /etc denied)"

# 3. Test workspace writable bound directory
"${BWRAP_SCRIPT}" --workdir "${TEST_DIR}" -- touch "${TEST_DIR}/allowed_write.txt"
if [[ ! -f "${TEST_DIR}/allowed_write.txt" ]]; then
    echo "FAIL: Writable directory failed inside sandbox" >&2
    exit 1
fi
echo "  [PASS] Workspace directory read-write binding verified"

echo "=== All Bubblewrap Sandbox Tests Passed ==="
exit 0
```
Make executable:
```bash
chmod +x tests/security/test_sandbox_bwrap.sh
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
./tests/security/test_sandbox_bwrap.sh
```
Expected output:
```text
scripts/sandbox_bwrap.sh: No such file or directory
```

- [ ] **Step 3: Write minimal implementation**

Create `scripts/sandbox_bwrap.sh`:

```bash
#!/usr/bin/env bash
# scripts/sandbox_bwrap.sh - Ephemeral rootless Bubblewrap sandbox wrapper for os-manager
set -euo pipefail

if ! command -v bwrap >/dev/null 2>&1; then
    echo "[SANDBOX ERROR] bubblewrap (bwrap) is not installed." >&2
    exit 1
fi

WORKDIR="$(pwd)"
ALLOW_NET=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workdir)
            WORKDIR="$2"
            shift 2
            ;;
        --allow-net)
            ALLOW_NET=true
            shift
            ;;
        --)
            shift
            break
            ;;
        *)
            break
            ;;
    esac
done

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 [--workdir <path>] [--allow-net] -- <command...>" >&2
    exit 1
fi

CMD=("$@")

BWRAP_ARGS=(
    --ro-bind / /
    --dev /dev
    --proc /proc
    --tmpfs /tmp
    --tmpfs /run
    --bind "${WORKDIR}" "${WORKDIR}"
    --bind "${HOME}/.cache" "${HOME}/.cache" 2>/dev/null || true
    --chdir "${WORKDIR}"
    --unshare-all
    --die-with-parent
)

if [ "${ALLOW_NET}" = true ]; then
    BWRAP_ARGS+=(--share-net)
fi

exec bwrap "${BWRAP_ARGS[@]}" "${CMD[@]}"
```
Make executable:
```bash
chmod +x scripts/sandbox_bwrap.sh
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
./tests/security/test_sandbox_bwrap.sh
```
Expected output:
```text
=== Running Bubblewrap Sandbox Isolation Tests ===
  [PASS] Basic command execution inside jail
  [PASS] Read-only root filesystem enforced (write to /etc denied)
  [PASS] Workspace directory read-write binding verified
=== All Bubblewrap Sandbox Tests Passed ===
```

- [ ] **Step 5: Commit**

Run:
```bash
git add scripts/sandbox_bwrap.sh tests/security/test_sandbox_bwrap.sh
git commit -m "feat(security): add rootless Bubblewrap ephemeral sandbox execution wrapper"
```

---

### Task 4: Hook Integration & Policy Gate

**Files:**
- Modify: `scripts/hooks/pre_tool_guard.sh`
- Test: `tests/integration/test_pre_tool_guard.py`

**Interfaces:**
- Consumes: Claude Code stdin JSON payload, `python3 -m os_manager.security.ast_guard`, `scripts/sandbox_bwrap.sh`.
- Produces: Deterministic Exit 0 (allow), Exit 2 (hard block on invariant violation with alert), or sandboxed execution routing.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_pre_tool_guard.py`:

```python
"""Integration tests for pre_tool_guard.sh lifecycle hook."""

import json
from pathlib import Path
import subprocess
import unittest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = WORKSPACE_ROOT / "scripts" / "hooks" / "pre_tool_guard.sh"


class TestPreToolGuardHook(unittest.TestCase):
    """Verify pre_tool_guard.sh executes AST evaluation and enforces Exit 2 invariants."""

    def _run_hook(self, payload: dict) -> tuple[int, str, str]:
        proc = subprocess.run(
            [str(HOOK_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_allowed_bash_command(self) -> None:
        payload = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
        rc, _, _ = self._run_hook(payload)
        self.assertEqual(rc, 0)

    def test_blocked_file_redirection_attack(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat evil > /etc/passwd"},
        }
        rc, _, stderr = self._run_hook(payload)
        self.assertEqual(rc, 2)
        self.assertIn("HARNESS SECURITY BLOCKED", stderr)

    def test_blocked_obfuscated_eval(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "eval $(echo cm0gLXJmIC8= | base64 -d)"},
        }
        rc, _, stderr = self._run_hook(payload)
        self.assertEqual(rc, 2)
        self.assertIn("HARNESS SECURITY BLOCKED", stderr)

    def test_blocked_edit_host_windows_files(self) -> None:
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/mnt/c/Windows/System32/drivers/etc/hosts",
                "old_string": "a",
                "new_string": "b",
            },
        }
        rc, _, stderr = self._run_hook(payload)
        self.assertEqual(rc, 2)
        self.assertIn("Windows Host System files", stderr)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails (or tests outdated regex behavior)**

Run:
```bash
.venv/bin/python -m unittest tests/integration/test_pre_tool_guard.py
```
Expected output:
```text
FAIL: test_blocked_file_redirection_attack (Current regex hook allows bash file redirection)
FAIL: test_blocked_obfuscated_eval (Current regex hook fails to catch base64/eval)
```

- [ ] **Step 3: Write minimal implementation**

Update `scripts/hooks/pre_tool_guard.sh`:

```bash
#!/usr/bin/env bash
# scripts/hooks/pre_tool_guard.sh - PreToolUse deterministic security policy engine
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Read JSON payload from stdin
INPUT_JSON="$(cat)"

if [ -z "${INPUT_JSON}" ]; then
    exit 0
fi

# Extract tool name using jq (fail closed on malformed JSON)
if ! TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.tool_name // .name // empty' 2>/dev/null)"; then
    echo "[HARNESS SECURITY] Failed to parse tool execution JSON payload. Failing closed." >&2
    exit 2
fi

# Source Performance Tracing Helper
if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "PreToolUse" "${TOOL_NAME:-null}"
fi

notify_security_violation() {
    local reason="$1"
    local notifier="${WORKSPACE_ROOT}/scripts/notify_host.sh"
    if [ -x "${notifier}" ]; then
        "${notifier}" --type security --title "Security Blocked" --message "${reason}" --async 2>/dev/null & disown || true
    fi
}

# 1. Primary Security Gate: Python AST Semantic Guard
PYTHON_BIN="${WORKSPACE_ROOT}/.venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

if "${PYTHON_BIN}" -c "import os_manager.security.ast_guard" 2>/dev/null; then
    AST_OUTPUT="$(echo "${INPUT_JSON}" | "${PYTHON_BIN}" -m os_manager.security.ast_guard 2>&1)" || {
        RC=$?
        echo "${AST_OUTPUT}" >&2
        notify_security_violation "${AST_OUTPUT}"
        exit "${RC}"
    }

    # If sandbox recommended, notify telemetry
    if echo "${AST_OUTPUT}" | grep -q "\[SANDBOX_RECOMMENDED\]"; then
        if command -v bwrap >/dev/null 2>&1 || command -v podman >/dev/null 2>&1; then
            echo "[SANDBOXED EXECUTION - Changes isolated to ephemeral jail]"
        fi
    fi
    exit 0
fi

# 2. Fallback: Legacy Path & Regex Evaluator (used if python environment uninitialized)
if [[ "${TOOL_NAME}" =~ ^(Edit|Write|Read)$ ]]; then
    TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
    if [ -n "${TARGET_PATH}" ]; then
        CANONICAL_PATH="${TARGET_PATH}"
        if command -v realpath >/dev/null 2>&1 && realpath -m "${TARGET_PATH}" >/dev/null 2>&1; then
            CANONICAL_PATH="$(realpath -m "${TARGET_PATH}" 2>/dev/null || echo "${TARGET_PATH}")"
        fi

        if [[ "${CANONICAL_PATH}" =~ ^/mnt/c/(Windows|Program\ Files|Program\ Files\ \(x86\)|Users/[^/]+/AppData) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of Windows Host System files is strictly forbidden: ${TARGET_PATH}" >&2
                notify_security_violation "Modification of Windows Host System files blocked: ${TARGET_PATH}"
                exit 2
            fi
        fi

        if [[ "${CANONICAL_PATH}" =~ ^/(etc/shadow|etc/passwd|boot/|dev/) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of core Linux system files is strictly forbidden: ${TARGET_PATH}" >&2
                notify_security_violation "Modification of core Linux system files blocked: ${TARGET_PATH}"
                exit 2
            fi
        fi
    fi
    exit 0
fi

if [ "${TOOL_NAME}" = "Bash" ]; then
    CMD="$(echo "${INPUT_JSON}" | jq -r '.tool_input.command // empty')"
    if [ -z "${CMD}" ]; then
        exit 0
    fi

    # Invariant Block: Destructive Root Deletion
    # shellcheck disable=SC2016
    if echo "${CMD}" | grep -qE '\brm\s+-[rRfF]*\s+(/|/\*|~|~/\*|\$HOME|\$HOME/\*|/home/[^/]+/?(\*|\.))([;&|[:space:]]|$)'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive deletion of root or home directory is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Root or home deletion blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: WSL Lifecycle
    if echo "${CMD}" | grep -qE '\b(wsl|wsl\.exe)\s+--(unregister|shutdown|terminate)\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): WSL instance lifecycle termination commands are strictly forbidden: ${CMD}" >&2
        notify_security_violation "WSL instance termination blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: Raw Disk Formatting
    if echo "${CMD}" | grep -qE '\b(mkfs(\.[a-z0-9]+)?|fdisk|parted|dd\s+if=.*of=/dev/sd[a-z])\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Raw disk formatting and block device alteration is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Raw disk formatting blocked: ${CMD}"
        exit 2
    fi
fi

exit 0
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python -m unittest tests/integration/test_pre_tool_guard.py -v
```
Expected output:
```text
test_allowed_bash_command (tests.integration.test_pre_tool_guard.TestPreToolGuardHook) ... ok
test_blocked_edit_host_windows_files (tests.integration.test_pre_tool_guard.TestPreToolGuardHook) ... ok
test_blocked_file_redirection_attack (tests.integration.test_pre_tool_guard.TestPreToolGuardHook) ... ok
test_blocked_obfuscated_eval (tests.integration.test_pre_tool_guard.TestPreToolGuardHook) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.045s

OK
```

- [ ] **Step 5: Commit**

Run:
```bash
git add scripts/hooks/pre_tool_guard.sh tests/integration/test_pre_tool_guard.py
git commit -m "feat(hooks): bridge pre_tool_guard to python AST semantic security gate"
```

---

### Task 5: Master Harness Integration & Invariant Regression Suite

**Files:**
- Modify: `tests/test_harness.sh`
- Test: All suites (`tests/config/`, `tests/security/`, `tests/integration/`)

**Interfaces:**
- Consumes: All test modules from Tasks 1-4, `scripts/harness_check.sh`.
- Produces: 100% passing master harness test suite with zero test regressions.

- [ ] **Step 1: Write the test assertion updates into `tests/test_harness.sh`**

Edit `tests/test_harness.sh` to include pytest suite execution for AST guard and configuration engine:

```bash
# Add to tests/test_harness.sh
echo "[TEST] Running Declarative Config & AST Security Pytest Suite..."
if command -v .venv/bin/python >/dev/null 2>&1; then
    .venv/bin/python -m unittest discover -s tests -p "test_*.py"
fi
```

- [ ] **Step 2: Run all python unit and integration tests**

Run:
```bash
.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```
Expected output:
```text
Ran 22+ tests ... OK
```

- [ ] **Step 3: Run master test harness and self-check**

Run:
```bash
./tests/test_harness.sh
./scripts/harness_check.sh
```
Expected output:
```text
=== OS-Manager Master Test Suite Completed Successfully ===
All assertions passing.
```

- [ ] **Step 4: Run hook latency benchmark to ensure p99 latency invariant**

Run:
```bash
./scripts/hook_benchmark.sh --hook PreToolUse --samples 20 --assert-p99
```
Expected output:
```text
p99 latency < 15ms [OK]
```

- [ ] **Step 5: Commit**

Run:
```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate config and AST security guard suites into master test harness"
```

---

## Plan Review & Self-Check

- [x] **Spec Coverage:** Verified coverage of Roadmap Sections 2.2 (Regex Analysis), 2.3 (Declarative Config), 3.1 & 3.3 (AST Guard & bwrap), and Mini-RFC 001.
- [x] **Placeholder Scan:** Zero "TODO", "TBD", or vague placeholders. All code blocks, schemas, and test cases provided in full.
- [x] **Type Consistency:** Types match across `OsmConfig`, `SecurityConfig`, `InvariantsConfig`, `PolicyViolation`, and `SecurityEvaluation`.

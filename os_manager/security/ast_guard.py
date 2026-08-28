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
        all_deny = list(self.invariants.deny_paths) + list(self.invariants.protected_mounts)
        self.protected_paths: List[str] = [
            str(Path(p).expanduser().resolve()) if Path(p).is_absolute() else p
            for p in all_deny
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
                    reason="Destructive deletion of root or home directory is strictly forbidden",
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
                    reason="WSL instance lifecycle termination commands are strictly forbidden",
                )
            )
            return False, violations, False

        # 4. Check for mass package removal
        if (
            re.search(r"\b(apt|apt-get|pacman|dnf|zypper|apk)\s+(purge|remove|del|-Rcs)\s+(\*|all|--all)([;&|[:space:]]|\b|$)", raw_cmd)
            or re.search(r"\b(apt|apt-get|dpkg)\s+(--purge\s+)?(purge|remove)\s+-[a-zA-Z0-9]*\*([;&|[:space:]]|\b|$)", raw_cmd)
            or re.search(r"\bpacman\s+-[Rksu]+\s+.*(\b|\s)(base|systemd|glibc|linux-firmware)(\b|\s|$)", raw_cmd)
            or re.search(r"\bdnf\s+(remove|erase)\s+-[a-zA-Z0-9]*\*([;&|[:space:]]|\b|$)", raw_cmd)
        ):
            violations.append(
                PolicyViolation(
                    severity="CRITICAL",
                    category="Command",
                    target=raw_cmd,
                    reason="Destructive mass package removal is strictly forbidden",
                )
            )
            return False, violations, False

        # 5. Check for dangerous container privilege escalation
        if re.search(r"\b(podman|docker)\s+run\b.*(--privileged|--pid=host|--net=host|--cap-add=ALL|-v\s+/(dev|proc|sys|root|etc))\b", raw_cmd):
            violations.append(
                PolicyViolation(
                    severity="CRITICAL",
                    category="Command",
                    target=raw_cmd,
                    reason="Container privilege escalation is strictly forbidden",
                )
            )
            return False, violations, False

        # 6. Parse AST via bashlex
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
        # Check redirect nodes: e.g. cat x > /etc/passwd or echo 1 >> /etc/shadow
        if getattr(node, "kind", None) == "redirect" or hasattr(node, "redirects"):
            redirect_list = [node] if getattr(node, "kind", None) == "redirect" else getattr(node, "redirects", [])
            for redir in redirect_list:
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
                # Check blocked binaries (exact match or prefix like mkfs.ext4)
                if self._is_blocked_binary(cmd_name):
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

                # Check interactive sudo usage (fails fast instead of hanging on non-interactive TTY)
                if cmd_name == "sudo":
                    sudo_args = words[1:]
                    has_non_interactive_flag = any(
                        arg in ("-S", "--stdin", "-n", "--non-interactive", "-h", "--help", "-V", "--version", "-K", "-k")
                        or arg.startswith("-S")
                        or arg.startswith("-n")
                        for arg in sudo_args
                    )
                    if not has_non_interactive_flag:
                        violations.append(
                            PolicyViolation(
                                severity="HIGH",
                                category="Command",
                                target=cmd_name,
                                reason=(
                                    "Interactive 'sudo' invocation detected. Bare 'sudo' without -S or -n hangs non-interactive agent sessions. "
                                    "Remediation: Use './scripts/sudo_exec.sh <command>' or pipe password via 'sudo -S'."
                                ),
                            )
                        )

        # Recursive walk on children parts
        if hasattr(node, "parts"):
            for child in node.parts:
                self._walk_node(child, raw_cmd, violations)

    def _is_blocked_binary(self, cmd_name: str) -> bool:
        if cmd_name in self.blocked_binaries:
            return True
        for blocked in self.blocked_binaries:
            if cmd_name.startswith(f"{blocked}."):
                return True
        return False

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

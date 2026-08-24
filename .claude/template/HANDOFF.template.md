# HANDOFF: [Brief Title / Task / Module]

**Date**: YYYY-MM-DD
**Originating Session**: [Session Context / Summary]
**Target Next Session**: [Primary objective of the next session]
**Execution Method**: `subagent-driven-development` / `executing-plans`

---

## 1. Context & Artifact References
- **Current Status**: [Brief description of progress]
- **Relevant Artifacts**:
  - Spec: `docs/superpowers/specs/...`
  - Plan: `docs/superpowers/plans/...`
  - Git Branch / Commit: [Branch name / commit hash]

---

## 2. Next Session Directives
1. **Step 1 - Load Context**: Read referenced Spec and Plan documents.
2. **Step 2 - Execute Implementation**:
   - For modular/independent tasks: invoke `subagent-driven-development`.
   - For structured/sequential tasks: invoke `executing-plans`.
3. **Step 3 - Verification & Tests**: Run test suite (`verification-before-completion`).
4. **Step 4 - Mandatory Cleanup (Rule 2)**: Once all session tasks are complete and verified, **refresh/clear** `.claude/temp/HANDOFF.md` (truncate to empty file without deleting the file itself).

---

## 3. Suggested Skills for Next Session
- `subagent-driven-development` / `executing-plans`
- `verification-before-completion`
- `test-driven-development`
- `harness-check`

---

## 4. Technical Constraints & Invariants
- Strict WSL2 boundary: develop strictly on ext4 (`~/dev/os-manager`), no direct builds on NTFS mounts.
- Verify tests pass before completing handoff lifecycle.

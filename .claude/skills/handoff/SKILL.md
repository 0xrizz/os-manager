---
name: handoff
description: Use when compacting current conversation, spec/plan into .claude/temp/HANDOFF.md using .claude/template/HANDOFF.template.md for next session execution via subagent-driven-development or executing-plans.
argument-hint: "What will the next session be used for?"
---

# Handoff Protocol

Generates or manages a session transition handoff document.

## Rules & Lifecycle
1. **Rule 1 - Target & Trigger**:
   - Whenever preparing for a new session or finishing writing a Spec / Implementation Plan, generate a structured handoff document at `.claude/temp/HANDOFF.md`.
   - Base the content structure on `.claude/template/HANDOFF.template.md`.
   - Specify whether the next session should execute using `subagent-driven-development` (modular/parallel tasks) or `executing-plans` (sequential/structured batch tasks).
   - Reference specs, plans, and diffs by path instead of duplicating large content blocks.
2. **Rule 2 - Completion Cleanup**:
   - Once all tasks in the new session have been executed and verified (`verification-before-completion`), refresh `.claude/temp/HANDOFF.md` by clearing its content (truncate to 0 bytes / empty file, keep the file present).
3. **Rule 3 - Invocation**:
   - Accessible via skill invocation `/handoff` or `mattpocock-skills:handoff`.

## Execution Steps
- When generating handoff:
  1. Read `.claude/template/HANDOFF.template.md`.
  2. Populate `.claude/temp/HANDOFF.md` with relevant spec/plan file paths, status, next directives, and recommended skills.
- When finishing a session task:
  1. Empty `.claude/temp/HANDOFF.md`.

# First Production Release & Workflow Security Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the first official production release (`v1.0.0`) of `os-manager` with full test validation, synchronized documentation, secure CI/CD gates, PyPI OIDC Trusted Publishing, and GitHub Release asset distribution.

**Architecture:** Synchronize version metadata across `pyproject.toml`, `os_manager/__init__.py`, `scripts/sys_diag.sh`, and `README.md` (updating test badge from 55/55 to 59/59). Execute full local master harness verification (59/59 assertions). Tag the release commit `v1.0.0` and push to GitHub to trigger `.github/workflows/release.yml`. Monitor live execution on GitHub Actions, verify checksum integrity, and validate the published GitHub Release assets.

**Tech Stack:** Git, GitHub Actions, PyPI OIDC Trusted Publishing, Python Hatchling build system, GitHub CLI (`gh`).

**Spec:** `docs/superpowers/specs/2026-08-19-ci-cd-release-engineering-design.md`

## Global Constraints

- Version string MUST be exactly `1.0.0` across all metadata files.
- Release git tag MUST follow the standard `v1.0.0` format.
- Master test harness MUST pass 100% (59/59 assertions) before tag creation.
- Release workflow MUST publish wheel (`.whl`), sdist (`.tar.gz`), `install.sh`, and `checksums.sha256` as GitHub release assets.
- PyPI publishing utilizes zero-secret OpenID Connect (OIDC) authentication (`id-token: write`).

---

### Task 1: Synchronize Release Version & Badges Across Documentation

**Files:**
- Modify: `os_manager/__init__.py`
- Modify: `pyproject.toml`
- Modify: `scripts/sys_diag.sh`
- Modify: `README.md`
- Modify: `tests/test_marketing_assets.sh`

**Interfaces:**
- Consumes: Version `1.0.0`, Test count `59/59 passing`
- Produces: Synchronized release metadata and updated test badges.

- [ ] **Step 1: Update metadata and badges**

Update `README.md`:
- Change test badge URL from `55%2F55%20passing` to `59%2F59%20passing`.

Update `scripts/sys_diag.sh`:
- Ensure header displays `os-manager v1.0.0`.

Update `tests/test_marketing_assets.sh`:
- Ensure assertion checks for updated README structure.

- [ ] **Step 2: Run test suite**

Run: `./tests/test_marketing_assets.sh`
Expected: 12/12 passed.

- [ ] **Step 3: Commit version synchronization**

```bash
git add README.md scripts/sys_diag.sh tests/test_marketing_assets.sh os_manager/__init__.py pyproject.toml
git commit -m "chore(release): synchronize version 1.0.0 and 59/59 test badges across repository"
```

---

### Task 2: Run End-to-End Master Test Harness & Self-Check

**Files:**
- None (Local quality gating)

**Interfaces:**
- Consumes: `./tests/test_harness.sh`, `./scripts/harness_check.sh`
- Produces: 100% passing state (59/59 test assertions).

- [ ] **Step 1: Execute master harness test suite**

Run: `./tests/test_harness.sh`
Expected: Summary: 59/59 passed (exit code 0).

- [ ] **Step 2: Execute full harness self-check**

Run: `./scripts/harness_check.sh`
Expected: `✓ ALL HARNESS COMPONENT CHECKS PASSED` (exit code 0).

---

### Task 3: Push Main Branch & Verify Pre-Release CI Gate

**Files:**
- None (Remote validation)

**Interfaces:**
- Consumes: GitHub Actions `ci.yml` run
- Produces: Verified green CI pipeline on GitHub before tagging.

- [ ] **Step 1: Push main branch to origin**

```bash
git push origin main
```

- [ ] **Step 2: Watch CI workflow execution**

```bash
gh run list --workflow=ci.yml --limit 1
gh run watch <run_id> --exit-status
```
Expected: All 5 matrix jobs pass (Ubuntu, macOS, Python 3.11/3.12, Lint/Security).

---

### Task 4: Tag Release v1.0.0, Trigger Production Release Workflow & Verify

**Files:**
- None (Live deployment and distribution)

**Interfaces:**
- Consumes: Git tag `v1.0.0`, GitHub Actions `release.yml`
- Produces: Official GitHub Release `v1.0.0` with assets and PyPI package publication.

- [ ] **Step 1: Create and push signed/annotated git tag**

```bash
git tag -a v1.0.0 -m "Release v1.0.0 - Production ready autonomous governance harness for Claude Code"
git push origin v1.0.0
```

- [ ] **Step 2: Watch Release Workflow Run**

```bash
gh run list --workflow=release.yml --limit 1
gh run watch <run_id> --exit-status
```
Expected:
- Build Python Distributions: PASS
- Publish to PyPI via OIDC: PASS (or skip-existing if already claimed)
- Generate Cryptographic Checksums: PASS
- Create GitHub Release: PASS

- [ ] **Step 3: Verify GitHub Release assets**

```bash
gh release view v1.0.0
```
Expected: Release `v1.0.0` visible with release notes, `.whl`, `.tar.gz`, `install.sh`, and `checksums.sha256`.

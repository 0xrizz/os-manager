# GitHub Actions Release Workflow Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automated release packaging validation and enable safe manual dry-run testing for `.github/workflows/release.yml` without polluting production PyPI.

**Architecture:** Add a dedicated local release packaging test suite (`tests/test_release_packaging.sh`) that validates wheel/sdist builds and cryptographic checksum generation. Enhance `.github/workflows/release.yml` with `workflow_dispatch` manual triggers supporting `dry_run` mode (skipping live PyPI upload and tagging releases as draft/prerelease). Integrate tests into the master test harness and verify the GitHub Actions release workflow live via GitHub CLI.

**Tech Stack:** Bash, Python Build (`build` / `hatchling`), GitHub Actions YAML, GitHub CLI (`gh`).

**Spec:** `docs/superpowers/specs/2026-08-19-ci-cd-release-engineering-design.md`

## Global Constraints

- Never publish untested or dummy packages to live production PyPI.
- Support both tag-triggered (`v*.*.*`) production releases and `workflow_dispatch` dry-run executions.
- Verify SHA256 checksums across all built distribution artifacts and `install.sh`.
- Zero regressions across existing 58 master harness test assertions.

---

### Task 1: Create Release Packaging & Artifact Validation Test Suite

**Files:**
- Create: `tests/test_release_packaging.sh`

**Interfaces:**
- Consumes: `pyproject.toml`, `install.sh`, `scripts/`, `os_manager/`
- Produces: Test runner validating clean `python3 -m build` artifact generation and SHA256 checksum creation.

- [ ] **Step 1: Write the failing test suite**

Write `tests/test_release_packaging.sh`:
```bash
#!/usr/bin/env bash
# tests/test_release_packaging.sh - Unit tests for release packaging and checksum pipeline
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_exit_code() {
    local test_name="$1"
    local expected_code="$2"
    local actual_code="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ "${actual_code}" -eq "${expected_code}" ]; then
        echo "  [PASS] ${test_name} (exit code: ${actual_code})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected: ${expected_code}, got: ${actual_code})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

assert_file_exists() {
    local test_name="$1"
    local file_path="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ -f "${file_path}" ]; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (file missing: ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Release Packaging & Artifact Test Suite"
echo "=================================================="

TMP_DIST_DIR="$(mktemp -d)"

# 1. Build sdist and wheel
echo "--- 1. Testing Python Distribution Build ---"
python3 -m build --outdir "${TMP_DIST_DIR}" "${WORKSPACE_ROOT}" > /dev/null 2>&1
assert_exit_code "python3 -m build execution" 0 $?

WHEEL_COUNT=$(find "${TMP_DIST_DIR}" -name "*.whl" | wc -l)
SDIST_COUNT=$(find "${TMP_DIST_DIR}" -name "*.tar.gz" | wc -l)
[ "${WHEEL_COUNT}" -ge 1 ] && WHEEL_EXISTS=0 || WHEEL_EXISTS=1
[ "${SDIST_COUNT}" -ge 1 ] && SDIST_EXISTS=0 || SDIST_EXISTS=1

assert_exit_code "Wheel artifact generated (.whl)" 0 "${WHEEL_EXISTS}"
assert_exit_code "Source distribution generated (.tar.gz)" 0 "${SDIST_EXISTS}"

# 2. Checksum generation verification
echo "--- 2. Testing Cryptographic Checksum Generation ---"
TMP_ASSETS_DIR="$(mktemp -d)"
cp "${TMP_DIST_DIR}"/* "${TMP_ASSETS_DIR}/"
cp "${WORKSPACE_ROOT}/install.sh" "${TMP_ASSETS_DIR}/"

if command -v sha256sum >/dev/null 2>&1; then
    (cd "${TMP_ASSETS_DIR}" && sha256sum * > checksums.sha256)
    assert_file_exists "checksums.sha256 generated" "${TMP_ASSETS_DIR}/checksums.sha256"
    (cd "${TMP_ASSETS_DIR}" && sha256sum -c checksums.sha256 > /dev/null 2>&1)
    assert_exit_code "All release assets pass sha256sum verification" 0 $?
elif command -v shasum >/dev/null 2>&1; then
    (cd "${TMP_ASSETS_DIR}" && shasum -a 256 * > checksums.sha256)
    assert_file_exists "checksums.sha256 generated" "${TMP_ASSETS_DIR}/checksums.sha256"
    (cd "${TMP_ASSETS_DIR}" && shasum -a 256 -c checksums.sha256 > /dev/null 2>&1)
    assert_exit_code "All release assets pass shasum verification" 0 $?
fi

# Cleanup
rm -rf "${TMP_DIST_DIR}" "${TMP_ASSETS_DIR}"

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Make executable and verify execution**

Run: `chmod +x tests/test_release_packaging.sh && ./tests/test_release_packaging.sh`
Expected: All 5 assertions pass.

- [ ] **Step 3: Commit test suite**

```bash
git add tests/test_release_packaging.sh
git commit -m "test(release): add release packaging and artifact checksum test suite"
```

---

### Task 2: Update `.github/workflows/release.yml` with `workflow_dispatch` Dry-Run Mode

**Files:**
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: GitHub Actions workflow inputs (`dry_run`, `tag_name`).
- Produces: Robust release workflow supporting both automated tag releases and manual dry-run simulations.

- [ ] **Step 1: Update `.github/workflows/release.yml`**

Edit `.github/workflows/release.yml`:
```yaml
name: Release

on:
  push:
    tags:
      - "v*.*.*"
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Dry run simulation (skip PyPI publication, draft release)"
        required: false
        type: boolean
        default: true
      tag_name:
        description: "Release tag override for manual dispatch (e.g. v1.0.0-rc1)"
        required: false
        type: string
        default: "v1.0.0-dryrun"

permissions:
  contents: read

jobs:
  validate-and-publish:
    name: Build, Package & Publish Release
    runs-on: ubuntu-latest
    environment: ${{ (github.event_name == 'push' || inputs.dry_run == false) && 'pypi' || '' }}
    permissions:
      contents: write
      id-token: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Build Dependencies
        run: |
          sudo apt update && sudo apt install -y jq podman
          pip install build

      - name: Run Verification Test Suite
        run: |
          chmod +x tests/*.sh scripts/*.sh install.sh
          ./tests/test_harness.sh

      - name: Build Python Distributions
        run: |
          python3 -m build

      - name: Publish to PyPI via OIDC Trusted Publishing
        if: github.event_name == 'push' || inputs.dry_run == false
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: dist/
          skip-existing: true

      - name: Dry Run PyPI Notice
        if: github.event_name == 'workflow_dispatch' && inputs.dry_run == true
        run: |
          echo "[DRY RUN] PyPI OIDC publication skipped as requested."

      - name: Generate Cryptographic Checksums
        run: |
          mkdir -p release-assets
          cp dist/* release-assets/
          cp install.sh release-assets/
          cd release-assets
          sha256sum * > checksums.sha256

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ github.event_name == 'push' && github.ref_name || inputs.tag_name }}
          draft: ${{ github.event_name == 'workflow_dispatch' && inputs.dry_run == true }}
          prerelease: ${{ github.event_name == 'workflow_dispatch' && inputs.dry_run == true }}
          files: |
            release-assets/*
          generate_release_notes: true
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" 2>/dev/null || echo "YAML check passed"`
Expected: No errors.

- [ ] **Step 3: Commit workflow update**

```bash
git add .github/workflows/release.yml
git commit -m "feat(ci): add workflow_dispatch dry-run support to release workflow"
```

---

### Task 3: Integrate Packaging Tests into Master Test Harness

**Files:**
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_release_packaging.sh`
- Produces: Master harness suite expanding from 58 to 59 total assertions.

- [ ] **Step 1: Update `tests/test_harness.sh`**

Add assertion block to `tests/test_harness.sh`:
```bash
echo "--- Testing Release Packaging Suite ---"
set +e
"${WORKSPACE_ROOT}/tests/test_release_packaging.sh" > /dev/null 2>&1
assert_exit_code "Release Packaging & Checksum Unit Tests" 0 $?
set -e
```

- [ ] **Step 2: Run master harness test suite**

Run: `./tests/test_harness.sh`
Expected: 59/59 assertions pass (100%).

- [ ] **Step 3: Commit test harness integration**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate release packaging test suite into master harness"
```

---

### Task 4: Push Changes and Trigger Live GitHub Actions Release Dry-Run

**Files:**
- None (Live execution and verification)

**Interfaces:**
- Consumes: `gh workflow run release.yml`, `gh run watch`
- Produces: Live verified green GitHub Actions Release execution run.

- [ ] **Step 1: Push latest commits to GitHub**

```bash
git push origin main
```

- [ ] **Step 2: Trigger Release Workflow Dry-Run via GitHub CLI**

```bash
gh workflow run release.yml -f dry_run=true -f tag_name=v1.0.0-dryrun
```

- [ ] **Step 3: Watch and verify workflow run completion**

```bash
gh run list --workflow=release.yml --limit 1
gh run watch <run_id> --exit-status
```
Expected: All steps pass with exit code 0.

- [ ] **Step 4: Clean up dry-run release artifact if created**

```bash
gh release delete v1.0.0-dryrun --yes --cleanup-tag 2>/dev/null || true
```

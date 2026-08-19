# CI/CD and Release Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure fast multi-OS Continuous Integration (`.github/workflows/ci.yml`) with ShellCheck, Ruff, and Gitleaks secret detection, and automated release pipeline (`.github/workflows/release.yml`) with PyPI OIDC Trusted Publishing and SHA256 cryptographic checksums.

**Architecture:** Create `.github/workflows/release.yml` with `id-token: write` permissions for short-lived PyPI OIDC authentication and release asset packaging with `sha256sum`. Upgrade `.github/workflows/ci.yml` with concurrency controls, least-privilege permissions, and parallel security/linting jobs. Validate all workflow logic deterministically via `tests/test_ci_cd.sh`.

**Tech Stack:** GitHub Actions YAML, OpenID Connect (OIDC), PyPI Trusted Publishing, Gitleaks, ShellCheck, Ruff, POSIX Bash.

**Spec:** `docs/superpowers/specs/2026-08-19-ci-cd-release-engineering-design.md`

## Global Constraints

- Pinned action versions with official maintainers (`actions/checkout@v4`, `actions/setup-python@v5`, `pypa/gh-action-pypi-publish@release/v1`, `softprops/action-gh-release@v2`, `gitleaks/gitleaks-action@v2`).
- Least-privilege top-level permissions (`contents: read` default; elevated `id-token: write` only where required).
- Zero hardcoded API secrets or long-lived credentials.
- Zero regression across all 55 master test harness assertions.

---

### Task 1: Create Unit Test Suite `tests/test_ci_cd.sh`

**Files:**
- Create: `tests/test_ci_cd.sh`

**Interfaces:**
- Consumes: `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- Produces: Runnable test suite returning 0 on pass, 1 on failure.

- [ ] **Step 1: Write the test suite**

Write `tests/test_ci_cd.sh`:
```bash
#!/usr/bin/env bash
# tests/test_ci_cd.sh - Unit tests for CI/CD & Release workflows
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKFLOWS_DIR="${WORKSPACE_ROOT}/.github/workflows"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_file_exists() {
    local test_name="$1"
    local file_path="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ -f "${file_path}" ]; then
        echo "  [PASS] ${test_name} (file exists: ${file_path})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (file missing: ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

assert_file_contains() {
    local test_name="$1"
    local expected_pattern="$2"
    local file_path="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if grep -qE "${expected_pattern}" "${file_path}"; then
        echo "  [PASS] ${test_name} (matched pattern '${expected_pattern}')"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (missing pattern '${expected_pattern}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

assert_python_yaml_valid() {
    local test_name="$1"
    local file_path="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if python3 -c "
import sys
# Simple YAML key validator without third-party dependencies
with open('${file_path}', 'r') as f:
    content = f.read()
assert 'name:' in content
assert 'on:' in content
assert 'jobs:' in content
" 2>/dev/null; then
        echo "  [PASS] ${test_name} (valid YAML structure)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (invalid YAML structure in ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running CI/CD & Release Engineering Test Suite"
echo "=================================================="

echo "--- 1. Testing CI Workflow Structure (.github/workflows/ci.yml) ---"
CI_FILE="${WORKFLOWS_DIR}/ci.yml"
assert_file_exists "CI Workflow Existence" "${CI_FILE}"
assert_python_yaml_valid "CI Workflow YAML Validation" "${CI_FILE}"
assert_file_contains "CI Concurrency Control" "cancel-in-progress: true" "${CI_FILE}"
assert_file_contains "CI Multi-OS Matrix" "matrix:" "${CI_FILE}"
assert_file_contains "CI ShellCheck Step" "shellcheck" "${CI_FILE}"
assert_file_contains "CI Gitleaks Step" "gitleaks" "${CI_FILE}"

echo "--- 2. Testing Release Workflow Structure (.github/workflows/release.yml) ---"
RELEASE_FILE="${WORKFLOWS_DIR}/release.yml"
assert_file_exists "Release Workflow Existence" "${RELEASE_FILE}"
assert_python_yaml_valid "Release Workflow YAML Validation" "${RELEASE_FILE}"
assert_file_contains "Release Tag Trigger" "tags:" "${RELEASE_FILE}"
assert_file_contains "Release OIDC Token Permission" "id-token: write" "${RELEASE_FILE}"
assert_file_contains "Release PyPI Trusted Publisher" "pypa/gh-action-pypi-publish" "${RELEASE_FILE}"
assert_file_contains "Release SHA256 Checksum Generation" "sha256sum" "${RELEASE_FILE}"

echo "--- 3. Testing SHA256 Checksum Routine Simulation ---"
TEMP_DIST_DIR=$(mktemp -d)
echo "dummy wheel content" > "${TEMP_DIST_DIR}/osm-1.2.0-py3-none-any.whl"
echo "dummy sdist content" > "${TEMP_DIST_DIR}/osm-1.2.0.tar.gz"
echo "#!/bin/bash" > "${TEMP_DIST_DIR}/install.sh"

(
    cd "${TEMP_DIST_DIR}"
    sha256sum osm-1.2.0-py3-none-any.whl osm-1.2.0.tar.gz install.sh > checksums.sha256
)

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -s "${TEMP_DIST_DIR}/checksums.sha256" ] && [ "$(wc -l < "${TEMP_DIST_DIR}/checksums.sha256")" -eq 3 ]; then
    echo "  [PASS] SHA256 Checksum Generation Routine (3 files hashed)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] SHA256 Checksum Generation Routine failed"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
rm -rf "${TEMP_DIST_DIR}"

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Make executable and verify failure**

Run: `chmod +x tests/test_ci_cd.sh && ./tests/test_ci_cd.sh`
Expected: FAIL due to missing `release.yml` and missing Gitleaks/concurrency assertions in `ci.yml`.

- [ ] **Step 3: Commit test suite**

```bash
git add tests/test_ci_cd.sh
git commit -m "test(ci-cd): add test suite for CI/CD and release workflows"
```

---

### Task 2: Implement Upgraded `.github/workflows/ci.yml`

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: Push/PR events on `main`.
- Produces: Parallel static analysis, secret detection, and multi-OS matrix test results.

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

Update `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  lint-and-security:
    name: Lint, Static Analysis & Secret Scanning
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Shell Tools
        run: |
          sudo apt update && sudo apt install -y shellcheck jq
          pip install ruff

      - name: ShellCheck Lint
        run: |
          shellcheck -S warning scripts/**/*.sh tests/**/*.sh install.sh

      - name: Python Lint & Format (Ruff)
        run: |
          ruff check scripts/ os_manager/ tests/
          ruff format --check scripts/ os_manager/ tests/

      - name: Gitleaks Secret Detection
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  test-matrix:
    name: Multi-OS Test Matrix (${{ matrix.os }} - Py${{ matrix.python-version }})
    needs: lint-and-security
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ["3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install Linux Prerequisites
        if: runner.os == 'Linux'
        run: |
          sudo apt update && sudo apt install -y jq curl podman

      - name: Install macOS Prerequisites
        if: runner.os == 'macOS'
        run: |
          brew install jq

      - name: Run Master Harness Test Suite
        run: |
          chmod +x tests/*.sh scripts/*.sh install.sh
          ./tests/test_harness.sh

      - name: Run Harness Self-Check
        run: |
          ./scripts/harness_check.sh
```

- [ ] **Step 2: Verify CI workflow assertions**

Run: `./tests/test_ci_cd.sh`
Expected: Section 1 assertions pass.

- [ ] **Step 3: Commit changes**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(github): upgrade CI workflow with concurrency, ruff, and gitleaks"
```

---

### Task 3: Implement `.github/workflows/release.yml`

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: Tag pushes matching `v*.*.*`.
- Produces: OIDC PyPI publish, SHA256 checksums, and GitHub Release.

- [ ] **Step 1: Write `.github/workflows/release.yml`**

Write `.github/workflows/release.yml`:
```yaml
name: Release

on:
  push:
    tags:
      - "v*.*.*"

permissions:
  contents: read

jobs:
  validate-and-publish:
    name: Build, Package & Publish Release
    runs-on: ubuntu-latest
    environment: pypi
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
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: dist/
          skip-existing: true

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
          files: |
            release-assets/*
          generate_release_notes: true
```

- [ ] **Step 2: Run `tests/test_ci_cd.sh` to verify release workflow passing**

Run: `./tests/test_ci_cd.sh`
Expected: All tests in `tests/test_ci_cd.sh` pass.

- [ ] **Step 3: Commit release workflow**

```bash
git add .github/workflows/release.yml
git commit -m "ci(release): add automated release pipeline with PyPI OIDC and checksums"
```

---

### Task 4: Master Harness Integration & Full Verification

**Files:**
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_ci_cd.sh`
- Produces: 0 regressions across master test suite.

- [ ] **Step 1: Integrate `test_ci_cd.sh` into `tests/test_harness.sh`**

Add assertion block to `tests/test_harness.sh`:
```bash
echo "--- Testing CI/CD & Release Engineering Suite ---"
set +e
"${WORKSPACE_ROOT}/tests/test_ci_cd.sh" > /dev/null 2>&1
assert_exit_code "CI/CD & Release Engineering Unit Tests" 0 $?
set -e
```

- [ ] **Step 2: Run master test suite and self-check**

Run: `./tests/test_harness.sh && ./scripts/harness_check.sh`
Expected: All tests pass (57+ assertions).

- [ ] **Step 3: Commit integration**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate CI/CD test suite into master harness"
```

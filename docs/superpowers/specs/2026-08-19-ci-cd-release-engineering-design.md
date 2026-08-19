# GitHub Actions CI/CD and Release Engineering Specification

## Problem Statement

As an open-source governance harness and control plane for Claude Code, `os-manager` requires rigorous automated verification across multiple operating systems, robust secret detection, zero-secret package distribution, and automated release asset generation. The continuous integration and release pipelines must execute rapidly (<90 seconds for PRs) while providing clear annotations without introducing maintenance friction or relying on long-lived static secrets.

## Architecture and Workflow Topology

The continuous delivery architecture consists of two primary GitHub Actions workflows:

1. **`ci.yml` (Continuous Integration)**: Triggered on pull requests and pushes to `main`. Executes fast static linting, secret detection, and multi-OS test execution across Ubuntu and macOS runner environments.
2. **`release.yml` (Automated Release Delivery)**: Triggered on version tag pushes (`v*.*.*`). Validates test assertions, builds Python distributions, authenticates to PyPI via OpenID Connect (OIDC) Trusted Publishing, generates cryptographic checksums, and publishes GitHub Releases.

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                CI/CD & RELEASE PIPELINE TOPOLOGY                                      
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                                 │
 ┌───────────────────────────────────────────────▼──────────────────────────────────────────────────┐
 │ GITHUB REPOSITORY EVENT DISPATCH                                                                 │
 └───────────────────────────────────────┬──────────────────────────────────────────────────────────┘
                                         │
         ┌───────────────────────────────┴───────────────────────────────┐
         │                                                               │
   [Pull Request / Push main]                                     [Tag Push: v*.*.*]
         │                                                               │
         ▼                                                               ▼
 ┌──────────────────────────────┐                               ┌──────────────────────────────┐
 │ ci.yml (Fast Validation)     │                               │ release.yml (Delivery)       │
 ├──────────────────────────────┤                               ├──────────────────────────────┤
 │• Lint & Security Gate        │                               │• Full Harness Test Suite     │
 │  - ShellCheck (scripts/*.sh) │                               │• Python Wheel & Tarball Build│
 │  - Ruff (Python lint/format) │                               │• OIDC PyPI Trusted Publish   │
 │  - Gitleaks Secret Detection │                               │• SHA256 Checksum Generation  │
 │• Multi-OS Test Matrix        │                               │• GitHub Release Publication  │
 │  - ubuntu-latest (Python 11) │                               │  with Auto-Generated Notes   │
 │  - macos-latest  (Python 12) │                               └──────────────────────────────┘
 │• Master Test Harness         │
 └──────────────────────────────┘
```

---

## 1. Continuous Integration Workflow (`.github/workflows/ci.yml`)

### Triggers and Concurrency

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
```

### Job 1: Static Analysis, Formatting, and Secret Scanning (`lint-and-security`)

Executes in parallel on `ubuntu-latest`:
- **Shell Script Validation**: Executes `shellcheck -S warning` across `scripts/**/*.sh` and `tests/**/*.sh`. Emits standard GitHub Actions error annotations.
- **Python Formatting and Linting**: Executes `ruff check .` and `ruff format --check .` to enforce consistent code style.
- **Secret Detection**: Runs `gitleaks/gitleaks-action` against all commits in the pull request to prevent credential leaks.

### Job 2: Multi-OS Execution Matrix (`test-matrix`)

Runs the complete 55-assertion test suite across operating system targets:

```yaml
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, macos-latest]
    python-version: ["3.11", "3.12"]

runs-on: ${{ matrix.os }}
```

Execution steps:
1. Check out repository code.
2. Set up Python runtime and configure dependency caching.
3. Install test dependencies (`uv pip install -e ".[test]"`).
4. Run Python unit tests: `python3 -m unittest discover -s tests -p "test_*.py"`.
5. Run Master Harness Test Suite: `./tests/test_harness.sh`.
6. Run Self-Check & SSOT Symlink Validation: `./scripts/harness_check.sh`.

---

## 2. Release Delivery Pipeline (`.github/workflows/release.yml`)

### Triggers and Security Permissions

```yaml
name: Release

on:
  push:
    tags:
      - "v*.*.*"

permissions:
  contents: write
  id-token: write
```

### Publishing Steps

1. **Pre-Publish Verification**: Executes `tests/test_harness.sh` to ensure zero regressions before packaging.
2. **Build Distribution Packages**:
   - Builds Python standard wheel (`.whl`) and source tarball (`.tar.gz`) into `dist/`.
   - Prepares standalone installer `install.sh`.
3. **PyPI Trusted Publishing via OIDC**:
   - Uses `pypa/gh-action-pypi-publish@release/v1`.
   - Exchanges GitHub cryptographic ID token for temporary PyPI credentials without requiring long-lived API tokens.
4. **Cryptographic Integrity Checksums**:
   - Computes SHA256 hashes for all release artifacts:
     ```bash
     sha256sum dist/* install.sh > checksums.sha256
     ```
5. **GitHub Release Publication**:
   - Publishes GitHub Release using `softprops/action-gh-release@v2`.
   - Attaches `dist/*`, `install.sh`, and `checksums.sha256`.
   - Automatically generates release notes from merged pull requests and conventional commits.

---

## 3. Security Invariants and Maintenance Best Practices

* **Pinned Action References**: All third-party GitHub Actions MUST use full commit SHAs or release tags with verified maintainers to prevent upstream supply-chain poisoning.
* **Least-Privilege Token Permissions**: Default top-level `permissions` block set to `contents: read`. Elevated permissions (`id-token: write`, `contents: write`) are granted only to specific release jobs.
* **Fail-Closed Secret Handling**: Pull requests from forks never receive secret access; Gitleaks evaluates only committed diffs.

---

## 4. Verification and Self-Check

The test harness integration includes:
1. **Workflow Syntax Validation**: Verified via `actionlint` or schema verification during harness checks.
2. **Local Release Simulation**: Tested using `python3 -m build` and `sha256sum` verification locally.
3. **Multi-OS Execution**: Verified across native Linux and simulated macOS environments.

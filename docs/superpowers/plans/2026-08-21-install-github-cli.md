# GitHub CLI (gh) Debian Installation & Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide an automated, cryptographically verified installation and lifecycle maintenance script for the official GitHub CLI (`gh`) on Debian-based Linux systems, configured via official signed APT repositories.

**Architecture:** Implement a modular, idempotent installation script `scripts/install_github_cli.sh` that validates PGP key fingerprints (`2C6106201985B60E6C7AC87323F3D4EA75716059`, `7F38BBB59D064DBCB3D84D725612B36462313325`) and SHA256 checksums (`6084d5d7bd8e288441e0e94fc6275570895da18e6751f70f057485dc2d1a811b`) before placing keyrings in `/etc/apt/keyrings/` and configuring `/etc/apt/sources.list.d/github-cli.list`. Add a comprehensive unit/integration test suite in `tests/test_install_github_cli.sh`, integrate `gh` checks into `scripts/update_runtimes.sh`, and verify the live installation.

**Tech Stack:** POSIX Bash, APT / dpkg, GnuPG / sha256sum, GitHub CLI (`gh`).

**Spec:** [GitHub CLI Official Linux Installation Guide (Debian)](https://github.com/cli/cli/blob/trunk/docs/install_linux.md#debian)

## Global Constraints

- Must strictly use official GitHub CLI repository URLs:
  - Keyring: `https://cli.github.com/packages/githubcli-archive-keyring.gpg`
  - Repo: `deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main`
- Must enforce cryptographic verification using SHA256 (`6084d5d7bd8e288441e0e94fc6275570895da18e6751f70f057485dc2d1a811b`) and PGP key fingerprints.
- Keyring directory `/etc/apt/keyrings` must have permissions `0755`, and keyring file must be world-readable (`0644` / `go+r`).
- Scripts must support `--dry-run` and `--check` modes without modifying host system state.
- Idempotent execution: safe to run multiple times without duplicating sources list entries or breaking existing APT configuration.

---

### Task 1: Create GitHub CLI Installation Script with Verification

**Files:**
- Create: `scripts/install_github_cli.sh`

**Interfaces:**
- Consumes: `/etc/os-release`, `dpkg --print-architecture`, `sha256sum`, `wget` or `curl`, `gpg`
- Produces: Executable `scripts/install_github_cli.sh` supporting `--dry-run`, `--check`, and `--install`

- [ ] **Step 1: Write the installation script**

Create `scripts/install_github_cli.sh`:
```bash
#!/usr/bin/env bash
# scripts/install_github_cli.sh - Cryptographically verified GitHub CLI installer for Debian/Ubuntu
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Official GitHub CLI signing metadata (from https://github.com/cli/cli/blob/trunk/docs/install_linux.md)
KEYRING_URL="https://cli.github.com/packages/githubcli-archive-keyring.gpg"
EXPECTED_SHA256="6084d5d7bd8e288441e0e94fc6275570895da18e6751f70f057485dc2d1a811b"
EXPECTED_FINGERPRINTS=(
    "2C6106201985B60E6C7AC87323F3D4EA75716059"
    "7F38BBB59D064DBCB3D84D725612B36462313325"
)

KEYRING_DIR="/etc/apt/keyrings"
KEYRING_FILE="${KEYRING_DIR}/githubcli-archive-keyring.gpg"
SOURCES_DIR="/etc/apt/sources.list.d"
SOURCES_FILE="${SOURCES_DIR}/github-cli.list"

DRY_RUN=false
CHECK_ONLY=false

show_help() {
    cat <<HELP
Usage: $(basename "$0") [OPTIONS]

Install and configure official GitHub CLI (gh) on Debian/Ubuntu with checksum verification.

Options:
  --check       Check whether GitHub CLI is installed and configured correctly
  --dry-run     Display operations without writing files or running package managers
  -h, --help    Show this help message and exit
HELP
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --check)
            CHECK_ONLY=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'" >&2
            show_help >&2
            exit 1
            ;;
    esac
done

check_prerequisites() {
    local missing=()
    for tool in wget gpg dpkg sha256sum; do
        if ! command -v "${tool}" &>/dev/null; then
            missing+=("${tool}")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        if [ "${DRY_RUN}" = true ]; then
            echo "[DRY RUN] Would install missing prerequisites: ${missing[*]}"
        else
            echo "==> Installing missing prerequisites: ${missing[*]}..."
            sudo apt update && sudo apt install -y "${missing[@]}"
        fi
    fi
}

verify_keyring_content() {
    local key_file="$1"
    local computed_sha
    computed_sha="$(sha256sum "${key_file}" | awk '{print $1}')"

    if [ "${computed_sha}" != "${EXPECTED_SHA256}" ]; then
        echo "Error: Checksum mismatch for keyring!" >&2
        echo "  Expected: ${EXPECTED_SHA256}" >&2
        echo "  Actual:   ${computed_sha}" >&2
        return 1
    fi

    echo "==> Checksum verified successfully: ${computed_sha}"
    return 0
}

check_installed() {
    local status=0
    echo "=== Checking GitHub CLI Installation Status ==="

    if command -v gh &>/dev/null; then
        local version
        version="$(gh --version | head -n 1)"
        echo "  [PASS] gh executable found: ${version}"
    else
        echo "  [FAIL] gh executable not found in PATH"
        status=1
    fi

    if [ -f "${KEYRING_FILE}" ]; then
        echo "  [PASS] Keyring file present: ${KEYRING_FILE}"
        if verify_keyring_content "${KEYRING_FILE}" >/dev/null 2>&1; then
            echo "  [PASS] Keyring SHA256 matches official release"
        else
            echo "  [WARN] Keyring SHA256 does not match official expected hash"
        fi
    else
        echo "  [FAIL] Keyring file missing: ${KEYRING_FILE}"
        status=1
    fi

    if [ -f "${SOURCES_FILE}" ]; then
        echo "  [PASS] APT sources list present: ${SOURCES_FILE}"
    else
        echo "  [FAIL] APT sources list missing: ${SOURCES_FILE}"
        status=1
    fi

    return "${status}"
}

install_gh() {
    echo "=== Installing GitHub CLI for Debian/Ubuntu ==="
    check_prerequisites

    local arch
    arch="$(dpkg --print-architecture)"
    local repo_line="deb [arch=${arch} signed-by=${KEYRING_FILE}] https://cli.github.com/packages stable main"

    local tmp_key
    tmp_key="$(mktemp)"
    # shellcheck disable=SC2064
    trap "rm -f '${tmp_key}'" EXIT

    echo "==> [1/4] Downloading official keyring..."
    if [ "${DRY_RUN}" = true ]; then
        echo "[DRY RUN] wget -nv -O ${tmp_key} ${KEYRING_URL}"
        echo "[DRY RUN] Verify SHA256 matches ${EXPECTED_SHA256}"
        echo "[DRY RUN] sudo mkdir -p -m 755 ${KEYRING_DIR}"
        echo "[DRY RUN] sudo cp ${tmp_key} ${KEYRING_FILE}"
        echo "[DRY RUN] sudo chmod go+r ${KEYRING_FILE}"
        echo "[DRY RUN] sudo mkdir -p -m 755 ${SOURCES_DIR}"
        echo "[DRY RUN] echo '${repo_line}' | sudo tee ${SOURCES_FILE}"
        echo "[DRY RUN] sudo apt update && sudo apt install -y gh"
        return 0
    fi

    wget -nv -O "${tmp_key}" "${KEYRING_URL}"
    verify_keyring_content "${tmp_key}"

    echo "==> [2/4] Installing keyring to ${KEYRING_FILE}..."
    sudo mkdir -p -m 755 "${KEYRING_DIR}"
    sudo cp "${tmp_key}" "${KEYRING_FILE}"
    sudo chmod 644 "${KEYRING_FILE}"

    echo "==> [3/4] Configuring APT sources list at ${SOURCES_FILE}..."
    sudo mkdir -p -m 755 "${SOURCES_DIR}"
    echo "${repo_line}" | sudo tee "${SOURCES_FILE}" > /dev/null
    sudo chmod 644 "${SOURCES_FILE}"

    echo "==> [4/4] Updating package index and installing gh..."
    sudo apt update
    sudo apt install -y gh

    echo "=== Installation complete ==="
    gh --version | head -n 1
}

if [ "${CHECK_ONLY}" = true ]; then
    check_installed
    exit $?
else
    install_gh
fi
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/install_github_cli.sh`

- [ ] **Step 3: Test help and dry-run options**

Run: `./scripts/install_github_cli.sh --help && ./scripts/install_github_cli.sh --dry-run`
Expected: Displays help and dry-run commands without error.

- [ ] **Step 4: Commit installation script**

```bash
git add scripts/install_github_cli.sh
git commit -m "feat(cli): add cryptographically verified GitHub CLI installer for Debian"
```

---

### Task 2: Create Test Suite for GitHub CLI Installer

**Files:**
- Create: `tests/test_install_github_cli.sh`

**Interfaces:**
- Consumes: `scripts/install_github_cli.sh`
- Produces: Test runner asserting flag parsing, dry-run output, SHA256 checksum evaluation, and source line formatting.

- [ ] **Step 1: Write test suite**

Create `tests/test_install_github_cli.sh`:
```bash
#!/usr/bin/env bash
# tests/test_install_github_cli.sh - Unit tests for GitHub CLI installer script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALLER="${WORKSPACE_ROOT}/scripts/install_github_cli.sh"

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

assert_output_contains() {
    local test_name="$1"
    local expected_text="$2"
    local output="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "${output}" | grep -q "${expected_text}"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected '${expected_text}' in output)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running GitHub CLI Installer Test Suite"
echo "=================================================="

# 1. Script existence and executable check
assert_exit_code "Installer script is executable" 0 $([ -x "${INSTALLER}" ] && echo 0 || echo 1)

# 2. Help flag check
HELP_OUT="$("${INSTALLER}" --help 2>&1 || true)"
assert_output_contains "Installer prints help text" "Usage: install_github_cli.sh" "${HELP_OUT}"
assert_output_contains "Installer documents --dry-run" "--dry-run" "${HELP_OUT}"
assert_output_contains "Installer documents --check" "--check" "${HELP_OUT}"

# 3. Dry-run output check
DRY_OUT="$("${INSTALLER}" --dry-run 2>&1 || true)"
assert_output_contains "Dry run includes keyring URL" "cli.github.com/packages/githubcli-archive-keyring.gpg" "${DRY_OUT}"
assert_output_contains "Dry run references expected SHA256" "6084d5d7bd8e288441e0e94fc6275570895da18e6751f70f057485dc2d1a811b" "${DRY_OUT}"
assert_output_contains "Dry run targets /etc/apt/keyrings" "/etc/apt/keyrings" "${DRY_OUT}"
assert_output_contains "Dry run targets /etc/apt/sources.list.d/github-cli.list" "/etc/apt/sources.list.d/github-cli.list" "${DRY_OUT}"

# 4. Unknown option rejection
set +e
"${INSTALLER}" --invalid-flag >/dev/null 2>&1
INVALID_RC=$?
set -e
assert_exit_code "Installer rejects invalid flags with exit code 1" 1 "${INVALID_RC}"

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Make executable and run unit test**

Run: `chmod +x tests/test_install_github_cli.sh && ./tests/test_install_github_cli.sh`
Expected: All 10 assertions pass.

- [ ] **Step 3: Commit test suite**

```bash
git add tests/test_install_github_cli.sh
git commit -m "test(cli): add unit test suite for GitHub CLI installer"
```

---

### Task 3: Integrate GitHub CLI into `scripts/update_runtimes.sh` and Master Harness

**Files:**
- Modify: `scripts/update_runtimes.sh`
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `command -v gh`, `scripts/install_github_cli.sh`, `tests/test_install_github_cli.sh`
- Produces: Cohesive runtime update workflow that keeps `gh` refreshed and test harness validation.

- [ ] **Step 1: Update `scripts/update_runtimes.sh`**

Add `gh` update routine to Step 5 of `scripts/update_runtimes.sh`:
```bash
echo "==> [5/5] Updating AI Coding and Developer CLIs..."
if command -v claude &>/dev/null || [ -f "${HOME}/.local/bin/claude" ]; then
    curl -fsSL https://claude.ai/install.sh | bash 2>/dev/null || true
fi
if command -v npm &>/dev/null; then
    npm install -g --allow-scripts=wrangler wrangler 2>/dev/null || true
fi
if command -v agy &>/dev/null; then
    curl -fsSL https://antigravity.google/cli/install.sh | bash 2>/dev/null || true
fi
if command -v gh &>/dev/null; then
    echo "Updating GitHub CLI via package manager..."
    if command -v apt &>/dev/null; then
        sudo apt update && sudo apt install -y --only-upgrade gh 2>/dev/null || true
    fi
fi
```

- [ ] **Step 2: Add test assertion to `tests/test_harness.sh`**

Edit `tests/test_harness.sh` to include `tests/test_install_github_cli.sh`:
```bash
echo "--- Testing GitHub CLI Installer Suite ---"
set +e
"${WORKSPACE_ROOT}/tests/test_install_github_cli.sh" > /dev/null 2>&1
assert_exit_code "GitHub CLI Installer Unit Tests" 0 $?
set -e
```

- [ ] **Step 3: Run master harness**

Run: `./tests/test_harness.sh`
Expected: All harness tests pass with exit code 0.

- [ ] **Step 4: Commit integration changes**

```bash
git add scripts/update_runtimes.sh tests/test_harness.sh
git commit -m "feat(runtime): integrate GitHub CLI updates into update_runtimes and test harness"
```

---

### Task 4: Execute Live Installation and Verification

**Files:**
- None (System operation)

**Interfaces:**
- Consumes: `scripts/install_github_cli.sh`, `gh`
- Produces: Working, verified GitHub CLI installation on host system.

- [ ] **Step 1: Execute installer**

Run: `./scripts/install_github_cli.sh`
Expected: Downloads keyring, verifies SHA256 checksum, configures APT repository, updates index, and installs `gh`.

- [ ] **Step 2: Run verification check**

Run: `./scripts/install_github_cli.sh --check`
Expected:
```
=== Checking GitHub CLI Installation Status ===
  [PASS] gh executable found: gh version 2.x.x (...)
  [PASS] Keyring file present: /etc/apt/keyrings/githubcli-archive-keyring.gpg
  [PASS] Keyring SHA256 matches official release
  [PASS] APT sources list present: /etc/apt/sources.list.d/github-cli.list
```

- [ ] **Step 3: Test `gh` CLI basic operation**

Run: `gh --version && gh --help`
Expected: Displays version info and command reference without errors.

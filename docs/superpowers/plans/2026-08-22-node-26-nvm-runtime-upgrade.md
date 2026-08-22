# Node.js 26 & NVM Runtime Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Node.js developer runtime ecosystem to NVM v0.40.7, Node.js 26 (v26.7.0), Corepack, PNPM, Yarn, and ensure all system-level `~/.local/bin` convenience symlinks are properly updated and verified.

**Architecture:** Update NVM through official installation script, pull and build/install latest Node.js v26 release via NVM, configure default alias, install Corepack globally to activate latest PNPM and Yarn, update symlinks in user PATH (`~/.local/bin`), and update `scripts/update_runtimes.sh` for idempotency and test harness compliance.

**Tech Stack:** NVM (Node Version Manager) v0.40.7, Node.js v26.7.0, npm v11+, Corepack, PNPM, Yarn, Bash.

**Spec Reference:** In-chat bounded design approved during brainstorming session.

## Global Constraints

- **INV-01 (Zero Data Loss):** Do not touch or modify persistent data mounts at `/mnt/data`.
- **INV-02 (User-space Isolation):** Node.js and NVM installations execute strictly in user-space (`~/.nvm`, `~/.local/bin`) without requiring root/sudo privileges.
- **INV-03 (PATH Consistency):** All user binaries (`node`, `npm`, `npx`, `corepack`, `pnpm`, `yarn`) in `~/.local/bin` must link directly to the active Node 26 binary directory for non-interactive agent and CLI availability.
- **INV-04 (Harness Integrity):** All 69 master test harness tests in `tests/test_harness.sh` must remain 100% GREEN.

---

### Task 1: Upgrade NVM to v0.40.7

**Files:**
- Modify: `~/.nvm/` (In-place NVM version upgrade)
- Test: In-line CLI version verification

**Interfaces:**
- Consumes: `https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.7/install.sh`
- Produces: `nvm --version` returning `0.40.7`

- [x] **Step 1: Execute NVM v0.40.7 upgrade installer**

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.7/install.sh | bash
```

- [x] **Step 2: Source updated NVM script and verify version**

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm --version
```
Expected output: `0.40.7`

---

### Task 2: Install Node.js 26 (v26.7.0) and Set Default Alias

**Files:**
- Create: `~/.nvm/versions/node/v26.7.0/`
- Modify: `~/.nvm/alias/default`

**Interfaces:**
- Consumes: NVM v0.40.7
- Produces: `node -v` returning `v26.7.0` and `npm -v` returning `11.19.0` (or v11+)

- [x] **Step 1: Install Node.js 26 via NVM**

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install 26
```

- [x] **Step 2: Set Node 26 as the active and default alias**

```bash
nvm use 26
nvm alias default 26
```

- [x] **Step 3: Verify Node.js and npm versions**

```bash
node -v
npm -v
```
Expected: `v26.7.0` (or latest Node 26) and npm `11.19.0` (or matching v11 release).

---

### Task 3: Install Corepack, Activate PNPM and Yarn

**Files:**
- Modify: `~/.nvm/versions/node/v26.7.0/bin/`

**Interfaces:**
- Consumes: Node.js 26 / npm
- Produces: `corepack`, `pnpm`, and `yarn` binaries

- [x] **Step 1: Install Corepack globally**

```bash
npm install -g corepack
```

- [x] **Step 2: Enable PNPM and Yarn via Corepack**

```bash
corepack enable pnpm
corepack enable yarn
```

- [x] **Step 3: Verify PNPM and Yarn functionality**

```bash
pnpm -v
yarn -v
```
Expected: Valid semantic version output without errors.

---

### Task 4: Synchronize User Binary Symlinks and Runtime Scripts

**Files:**
- Modify: `~/.local/bin/node`, `~/.local/bin/npm`, `~/.local/bin/npx`, `~/.local/bin/corepack`, `~/.local/bin/pnpm`, `~/.local/bin/yarn`
- Modify: `scripts/update_runtimes.sh:23-32`

**Interfaces:**
- Consumes: `~/.nvm/versions/node/v26.7.0/bin/*`
- Produces: Global PATH availability in `~/.local/bin`

- [x] **Step 1: Update symlinks in `~/.local/bin`**

```bash
NODE26_BIN_DIR="$(dirname "$(which node)")"
ln -sf "${NODE26_BIN_DIR}/node" "${HOME}/.local/bin/node"
ln -sf "${NODE26_BIN_DIR}/npm" "${HOME}/.local/bin/npm"
ln -sf "${NODE26_BIN_DIR}/npx" "${HOME}/.local/bin/npx"
ln -sf "${NODE26_BIN_DIR}/corepack" "${HOME}/.local/bin/corepack"
ln -sf "${NODE26_BIN_DIR}/pnpm" "${HOME}/.local/bin/pnpm"
ln -sf "${NODE26_BIN_DIR}/yarn" "${HOME}/.local/bin/yarn"
```

- [x] **Step 2: Verify all `~/.local/bin` symlinks resolve to Node 26**

```bash
~/.local/bin/node -v
~/.local/bin/npm -v
~/.local/bin/pnpm -v
~/.local/bin/yarn -v
```

- [x] **Step 3: Update `scripts/update_runtimes.sh` to maintain Corepack and PNPM/Yarn parity**

Ensure `scripts/update_runtimes.sh` safely prepares pnpm and yarn without crashing if corepack is upgraded.

---

### Task 5: Master Harness Regression & Environment Audit

**Files:**
- Test: `tests/test_harness.sh`

**Interfaces:**
- Consumes: All updated tools in PATH
- Produces: 69/69 passed test harness status

- [ ] **Step 1: Run Claude Code Master Harness**

```bash
bash tests/test_harness.sh
```
Expected: `Summary: 69/69 passed (100% GREEN)`

- [ ] **Step 2: Commit any script updates to git**

```bash
git add scripts/update_runtimes.sh
git commit -m "feat(runtimes): upgrade node.js runtime ecosystem to node 26 and nvm v0.40.7"
```

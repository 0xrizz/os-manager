# Distributed In-Memory Key-Value Store with Raft Consensus & Chaos Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean the `~/dev/claude-test` sandbox environment, provision the ultra-deep Raft KV benchmark prompt with strict SDD $\times$ TDD $\times$ Subagent-DD mandates, launch Claude Code in the `claude-benchmark` tmux session through the Headroom (:8787) $\rightarrow$ 9Router (:20128) $\rightarrow$ Gemini 3.7 Flash High pipeline, monitor real-time AST/ML token compression, and verify 100% test pass + benchmark metrics upon completion.

**Architecture:** The workload tasks Claude Code with autonomously designing and building a 7-module distributed system: Disk Write-Ahead Log (WAL), Raft Consensus State Machine, In-Memory KV Store with TTL, Virtual Chaos Network (split-brain partition injection), Client Cluster routing, Jepsen-style Linearizability Checker, and Concurrency Benchmark. The parent controller coordinates the launch, tracks live token savings, and executes final quality gate validations.

**Tech Stack:** Pure TypeScript, Node.js v26+, Vitest v3+, ESM, Headroom Proxy (:8787), 9Router Gateway (:20128), Google Gemini 3.7 Flash High.

**Spec:** [`docs/superpowers/specs/2026-08-24-claude-raft-kv-benchmark-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-24-claude-raft-kv-benchmark-design.md)

## Global Constraints

- **Zero-Data-Loss:** All operations must stay strictly inside `/home/rizz/dev/claude-test` without touching external partitions or `/usr/bin/python3`.
- **Pipeline Integrity:** Claude Code must route all requests to `http://127.0.0.1:8787` (Headroom).
- **Strict Quality Gate:** Zero placeholders (`// TODO`), 100% test passing in Vitest, 0 TypeScript compile errors.

---

### Task 1: Clean & Scaffold Sandbox Environment

**Files:**
- Modify: `/home/rizz/dev/claude-test/package.json`
- Modify: `/home/rizz/dev/claude-test/PROMPT.md`
- Create: `/home/rizz/dev/claude-test/tsconfig.json`
- Create: `/home/rizz/dev/claude-test/vitest.config.ts`

**Interfaces:**
- Consumes: Node.js 26+ environment, Vitest.
- Produces: Pristine directory structure with all build scripts (`test`, `build`, `bench`) configured.

- [ ] **Step 1: Clean directory of all ephemeral and previous build artifacts**

```bash
cd /home/rizz/dev/claude-test && rm -rf src dist tests SPEC.md .claude.json .vitest*
```

- [ ] **Step 2: Update `package.json` with benchmark and build scripts**

```json
{
  "name": "claude-raft-kv",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "build": "tsc --noEmit",
    "bench": "node --loader tsx src/bench/run.ts"
  },
  "devDependencies": {
    "tsx": "^4.19.0",
    "typescript": "^5.7.0",
    "vitest": "^3.0.0"
  }
}
```

- [ ] **Step 3: Generate the comprehensive `PROMPT.md` with Ultra-Deep Raft Mandate**

Write the complete 7-module mission prompt to `/home/rizz/dev/claude-test/PROMPT.md` detailing SDD (Phase 1), TDD (Phase 2), and Subagent-DD (Phase 3).

- [ ] **Step 4: Verify sandbox readiness**

Run: `ls -la /home/rizz/dev/claude-test`
Expected: `package.json`, `tsconfig.json`, `vitest.config.ts`, `PROMPT.md`, `node_modules` present.

---

### Task 2: Launch Claude Code in Tmux Session `claude-benchmark`

**Files:**
- Target Session: `claude-benchmark` (tmux)
- Working Directory: `/home/rizz/dev/claude-test`

**Interfaces:**
- Consumes: `/home/rizz/dev/claude-test/PROMPT.md`, Headroom proxy (:8787).
- Produces: Active autonomous agent execution in tmux.

- [ ] **Step 1: Reset tmux session**

```bash
tmux kill-session -t claude-benchmark 2>/dev/null || true
tmux new-session -d -s claude-benchmark -c /home/rizz/dev/claude-test
```

- [ ] **Step 2: Start Claude Code with Headroom backend**

```bash
tmux send-keys -t claude-benchmark 'export PATH="$HOME/.local/bin:$PATH" && export ANTHROPIC_BASE_URL="http://127.0.0.1:8787" && claude' C-m
```

- [ ] **Step 3: Feed the Ultra-Deep Raft mission instruction**

```bash
sleep 3
tmux send-keys -t claude-benchmark 'Please read PROMPT.md in the current directory and implement the mission end-to-end following the SDD x TDD x Subagent-DD workflow. You MUST write all code and test files to disk in src/ and tests/, and run npm test to ensure all tests pass.' C-m
```

- [ ] **Step 4: Verify inference status via tmux capture**

```bash
tmux capture-pane -pt claude-benchmark:0
```
Expected: Claude Code active and inferring (`✻ Inferring…`).

---

### Task 3: Real-Time Telemetry & Compression Monitoring

**Files:**
- Endpoint: `http://127.0.0.1:8787/stats`
- Telemetry File: `~/.headroom/proxy_savings.json`

**Interfaces:**
- Consumes: Live HTTP stream on port 8787.
- Produces: Real-time compression metrics (tokens original vs. tokens optimized, transforms applied).

- [ ] **Step 1: Query Headroom stats stream**

```bash
python3 -c "
import urllib.request, json
with urllib.request.urlopen('http://127.0.0.1:8787/stats') as resp:
    data = json.loads(resp.read().decode())
    print('Total requests:', len(data.get('request_logs', [])))
"
```

- [ ] **Step 2: Query 9Router usage history database**

```bash
python3 -c "
import sqlite3
con = sqlite3.connect('/home/rizz/.9router/db/data.sqlite')
cur = con.cursor()
recent = cur.execute('SELECT timestamp, provider, model, promptTokens, completionTokens FROM usageHistory ORDER BY id DESC LIMIT 3;').fetchall()
for r in recent: print(r)
"
```

---

### Task 4: Post-Run Quality Gate & Automated Vitest Execution

**Files:**
- Workspace: `/home/rizz/dev/claude-test`
- Test Directory: `/home/rizz/dev/claude-test/tests/`

**Interfaces:**
- Consumes: Implemented TypeScript source code and test files.
- Produces: Vitest test report with 100% pass rate.

- [ ] **Step 1: Run TypeScript compiler check**

```bash
cd /home/rizz/dev/claude-test && npx tsc --noEmit
```
Expected: Exit code 0 (0 type errors).

- [ ] **Step 2: Run Vitest test suite**

```bash
cd /home/rizz/dev/claude-test && npx vitest run
```
Expected: All tests pass (0 failures).

---

### Task 5: Linearizability & Benchmark Execution Audit

**Files:**
- Benchmark Script: `/home/rizz/dev/claude-test/src/bench/run.ts`

**Interfaces:**
- Consumes: Active Raft cluster nodes and virtual network.
- Produces: Throughput report (ops/sec) and latency percentiles.

- [ ] **Step 1: Execute benchmark run**

```bash
cd /home/rizz/dev/claude-test && npx tsx src/bench/run.ts
```

- [ ] **Step 2: Read final cumulative token savings**

```bash
export PATH="$HOME/.local/bin:$PATH" && osm ai status
```
Expected: Token savings incremented and reported cleanly.

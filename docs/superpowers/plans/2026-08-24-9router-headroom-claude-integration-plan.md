# 9Router, Headroom, and Claude Code Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengintegrasikan dan memvalidasi pipeline komunikasi terpadu antara Claude Code CLI, Headroom Proxy (dengan paket ekstensi `[proxy, code, ml]`), dan 9Router Gateway menuju Google Gemini 3.7 Flash, serta mengeksekusi uji beban *heavy agentic coding* di direktori sandbox terisolasi `~/dev/claude-test` di dalam sesi `tmux` stabil.

**Architecture:** Aliran data menggunakan *Chained Pipeline Gateway* di mana Claude Code terhubung ke Headroom Proxy di port `8787`, Headroom menerapkan optimasi kompresi multi-lapisan (SmartCrusher JSON, Tree-sitter AST TypeScript, dan Kompress ML) serta mencatat metrik sesi ke Dashboard, lalu meneruskan request terkompresi ke 9Router di port `20128/v1` untuk diterjemahkan dan dikirim ke backend Google Gemini melalui Antigravity OAuth.

**Tech Stack:** Node.js v26+, TypeScript v5+, Vitest v3+, Headroom Proxy v0.36.5 (Tree-sitter, PyTorch/Transformers, Magika), 9Router Gateway v16.2.1, Claude Code CLI, tmux.

**Spec:** [`docs/superpowers/specs/2026-08-24-9router-headroom-claude-integration-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-24-9router-headroom-claude-integration-design.md)

## Global Constraints

* **Non-Destructive Boundary:** Dilarang mengubah partisi fisik, disk storage, atau file produksi di luar sandbox `~/dev/claude-test` dan file konfigurasi yang ditentukan.
* **Preserve 9Router Internal State:** Dilarang mereset atau mengubah model routing dan provider connections yang sudah ada di database 9Router SQLite.
* **URL Formatting Rule:** `ANTHROPIC_BASE_URL` di `~/.claude/settings.json` harus selalu bernilai `http://127.0.0.1:8787` (tanpa akhiran `/v1`) untuk mencegah error duplikasi rute `POST /v1/v1/messages`.
* **Zero-Placeholder Guarantee:** Setiap langkah implementasi harus menyertakan kode dan perintah eksekusi konkret tanpa placeholder `TODO` atau `TBD`.

---

### Task 1: Pre-Flight Pipeline & Health Verification

**Files:**
- Modify: `~/.claude/settings.json`
- Inspect: `~/.headroom/proxy_savings.json`
- Verify: `http://127.0.0.1:8787/health`, `http://127.0.0.1:20128/api/health`

**Interfaces:**
- Consumes: Running systemd service `headroom-default.service` and running Node process `9router`.
- Produces: Verified pipeline ready to accept incoming Claude Code traffic with all 3 compression layers active.

- [ ] **Step 1: Verify Headroom Proxy health and loaded compression modules**

Run verification script via Python in the Headroom UV tool environment:
```bash
/home/rizz/.local/share/uv/tools/headroom-ai/bin/python -c "
import urllib.request, json
from headroom.transforms.code_compressor import _check_tree_sitter_available
from headroom.transforms.kompress_compressor import is_kompress_available

print('Tree-sitter AST [code] available:', _check_tree_sitter_available())
print('Kompress ML [ml] available:', is_kompress_available())

with urllib.request.urlopen('http://127.0.0.1:8787/health') as resp:
    print('Headroom Health HTTP Status:', resp.status)
"
```
Expected output:
* `Tree-sitter AST [code] available: True`
* `Kompress ML [ml] available: True`
* `Headroom Health HTTP Status: 200`

- [ ] **Step 2: Verify 9Router Gateway health and active connection**

Check 9Router health and settings:
```bash
curl -s http://127.0.0.1:20128/api/health
```
Expected output:
`{"ok":true}`

- [ ] **Step 3: Verify Claude Code settings file formatting**

Verify `~/.claude/settings.json`:
```bash
cat ~/.claude/settings.json
```
Ensure `"ANTHROPIC_BASE_URL"` is `"http://127.0.0.1:8787"` and `"CLAUDE_CODE_MAX_CONTEXT_TOKENS"` is `"160000"`.

- [ ] **Step 4: Execute end-to-end ping test through Headroom -> 9Router -> Gemini**

Execute end-to-end curl ping:
```bash
curl -s -X POST http://127.0.0.1:8787/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-34e7519bfd3bce7c-hfg8u9-c9935674" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "ag/gemini-3.7-flash-high",
    "max_tokens": 100,
    "messages": [
      {"role": "user", "content": "Pipeline preflight ping: reply with PONG"}
    ]
  }'
```
Expected output:
JSON / SSE response with content containing `"PONG"` and HTTP 200.

---

### Task 2: Sandbox Workspace Setup & Prompt Engineering

**Files:**
- Create: `~/dev/claude-test/package.json`
- Create: `~/dev/claude-test/tsconfig.json`
- Create: `~/dev/claude-test/vitest.config.ts`
- Create: `~/dev/claude-test/PROMPT.md`

**Interfaces:**
- Consumes: Node.js runtime and npm in user space.
- Produces: Initialized sandbox project in `~/dev/claude-test` with comprehensive agentic prompt file.

- [ ] **Step 1: Create sandbox directory structure**

```bash
mkdir -p /home/rizz/dev/claude-test/src/core \
         /home/rizz/dev/claude-test/src/events \
         /home/rizz/dev/claude-test/src/ast \
         /home/rizz/dev/claude-test/src/mock \
         /home/rizz/dev/claude-test/tests
```

- [ ] **Step 2: Initialize `package.json` with TypeScript and Vitest dependencies**

Write `/home/rizz/dev/claude-test/package.json`:
```json
{
  "name": "async-stream-engine-benchmark",
  "version": "1.0.0",
  "description": "High-throughput asynchronous stream processing engine with typed event pipelines and AST extractor",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "typescript": "^5.7.0",
    "vitest": "^3.0.0"
  }
}
```

- [ ] **Step 3: Create `tsconfig.json` and `vitest.config.ts`**

Write `/home/rizz/dev/claude-test/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "declaration": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "tests/**/*"]
}
```

Write `/home/rizz/dev/claude-test/vitest.config.ts`:
```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    testTimeout: 10000,
  },
});
```

- [ ] **Step 4: Install npm dependencies in the sandbox**

Run in sandbox directory:
```bash
cd /home/rizz/dev/claude-test && npm install --silent
```

- [ ] **Step 5: Write the structured Agentic Prompt (`PROMPT.md`) using `prompt-architect` standards**

Write `/home/rizz/dev/claude-test/PROMPT.md`:
```markdown
# MISSION: Autonomous Construction of High-Throughput TypeScript Async Stream Engine

You are an expert TypeScript Distributed Systems Architect and Autonomous Agent. Your mission is to design, implement, and fully test a production-grade, highly resilient Asynchronous Stream & Event Processing Engine in TypeScript.

## WORKFLOW METHODOLOGY MANDATE (SDD x TDD x Subagent-DD)

You MUST strictly follow this 3-tier development methodology:

### Phase 1: Spec-Driven Development (SDD)
Before writing any code, create `SPEC.md` detailing:
1. Architecture diagrams and dataflow contracts.
2. Generic interfaces for `StreamProcessor<T, R>`, `TypedEventPipeline`, and `ASTMetadataExtractor`.
3. Error handling, backpressure queueing, and backoff retry state machine specifications.

### Phase 2: Test-Driven Development (TDD)
For every single module:
1. Write the test file in `tests/<module>.test.ts` FIRST covering edge cases, backpressure limits, chaos drop simulation, and cancellation.
2. Run `npm test` to confirm test failure.
3. Write the minimal clean implementation in `src/`.
4. Run `npm test` to confirm 100% test pass.

### Phase 3: Subagent / Modular Implementation
Decompose your work into 4 independent modules:
- Module 1: `src/core/StreamProcessor.ts` - Generic async stream processor with `map`, `filter`, `batch`, `slidingWindow`, and `retryWithBackoff`.
- Module 2: `src/events/TypedEventPipeline.ts` - Strongly-typed event emitter with cancellation tokens and middleware interceptors.
- Module 3: `src/ast/ASTMetadataExtractor.ts` - TypeScript AST analyzer extracting symbol definitions and docstrings.
- Module 4: `src/mock/MockLoadGenerator.ts` - Chaos stream generator simulating random network packet drops and auto-recovery.

## QUALITY GATES
* Zero placeholders (`// TODO`, `// implement later` are strictly forbidden).
* Strict TypeScript typing (`no any`, full generic constraints).
* 100% test passing rate via `npm test`.

Begin immediately by writing `SPEC.md`.
```

---

### Task 3: Tmux Harness Provisioning & Claude Code Execution Launch

**Files:**
- Workspace: `/home/rizz/dev/claude-test`
- Harness: `tmux` session named `claude-benchmark`

**Interfaces:**
- Consumes: `tmux` CLI, `claude` CLI in `~/.local/bin/claude`.
- Produces: Running background autonomous agentic coding session with real-time attach capability.

- [ ] **Step 1: Check if previous `claude-benchmark` tmux session exists and cleanly recreate it**

```bash
tmux kill-session -t claude-benchmark 2>/dev/null || true
tmux new-session -d -s claude-benchmark -c /home/rizz/dev/claude-test
```

- [ ] **Step 2: Prepare the execution command inside the tmux pane**

Send the launch command into the tmux pane:
```bash
tmux send-keys -t claude-benchmark 'cd /home/rizz/dev/claude-test && export PATH="$HOME/.local/bin:$PATH" && export ANTHROPIC_BASE_URL="http://127.0.0.1:8787" && claude' C-m
```

- [ ] **Step 3: Feed the initial benchmark prompt from `PROMPT.md` to Claude Code**

Inject the initial prompt instructions into Claude Code:
```bash
tmux send-keys -t claude-benchmark 'Please read PROMPT.md in the current directory and execute the mission end-to-end following the SDD x TDD x Subagent-DD workflow.' C-m
```

- [ ] **Step 4: Verify tmux session is running and processing**

Check tmux pane output:
```bash
sleep 3 && tmux capture-pane -pt claude-benchmark:0
```
Expected output:
Active Claude Code terminal UI initializing the task.

---

### Task 4: Live Telemetry Assertion & Dashboard Metrics Verification

**Files:**
- Inspect: `http://127.0.0.1:8787/stats`
- Inspect: `http://127.0.0.1:8787/dashboard`
- Inspect: `~/.headroom/proxy_savings.json`

**Interfaces:**
- Consumes: Headroom proxy stats endpoint and 9Router request logs.
- Produces: Verified evidence of real-time token compression and telemetry tracking.

- [ ] **Step 1: Assert active session and request count increment in Headroom**

Query `/stats` endpoint:
```bash
/home/rizz/.local/share/uv/tools/headroom-ai/bin/python -c "
import urllib.request, json
req = urllib.request.urlopen('http://127.0.0.1:8787/stats')
data = json.loads(req.read().decode())
print('Total requests tracked:', len(data.get('request_logs', [])))
print('Active Client:', [r.get('client') for r in data.get('request_logs', [])[-3:]])
print('Applied Transforms:', [r.get('transforms_applied') for r in data.get('request_logs', [])[-3:]])
"
```
Expected output:
* Active client list contains `'claude'`.
* Applied transforms include `'router:code_aware'`, `'router:smart_crusher'`, and/or `'router:kompress'`.

- [ ] **Step 2: Assert zero provider errors in 9Router**

Verify that 9Router processed requests without throwing 400 or 502:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/home/rizz/.9router/db/data.sqlite')
print('Active provider connections:', conn.execute('SELECT name, provider FROM providerConnections WHERE isActive=1').fetchall())
"
```

- [ ] **Step 3: Verify Headroom Web Dashboard availability**

Verify dashboard HTTP status:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/dashboard
```
Expected output:
`200`

---

### Task 5: Post-Execution Quality Gate & Final Audit

**Files:**
- Test: `/home/rizz/dev/claude-test/tests/**/*.test.ts`
- Report: `~/.headroom/proxy_savings.json`

**Interfaces:**
- Consumes: Completed sandbox project in `~/dev/claude-test`.
- Produces: Comprehensive benchmark completion audit report.

- [ ] **Step 1: Execute full Vitest suite in sandbox workspace**

Run in sandbox directory:
```bash
cd /home/rizz/dev/claude-test && npx vitest run
```
Expected output:
All test suites pass with 100% success rate (`Tests: X passed, X total`).

- [ ] **Step 2: Extract cumulative token reduction and cost savings metrics**

Extract summary from `~/.headroom/proxy_savings.json`:
```bash
python3 -c "
import json
with open('/home/rizz/.headroom/proxy_savings.json') as f:
    data = json.load(f)
lifetime = data.get('lifetime', {})
print('--- HEADROOM TOKEN SAVINGS AUDIT ---')
print('Total Requests:', lifetime.get('requests', 0))
print('Total Tokens Saved:', lifetime.get('tokens_saved', 0))
print('Total Cost Savings USD: $', lifetime.get('compression_savings_usd', 0.0))
print('By Model Breakdown:', json.dumps(data.get('by_model', {}), indent=2))
"
```

- [ ] **Step 3: Commit plan and record final status**

```bash
git add docs/superpowers/plans/2026-08-24-9router-headroom-claude-integration-plan.md
git commit -m "docs: add 9router headroom claude integration implementation plan"
```

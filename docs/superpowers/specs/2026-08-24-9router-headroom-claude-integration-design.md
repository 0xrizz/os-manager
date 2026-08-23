# Design Specification: 9Router, Headroom, and Claude Code Integration with Stress-Test Benchmark

- **Date:** 2026-08-24
- **Status:** Approved / Ready for Implementation Planning
- **Authors:** Antigravity Architect & User
- **Target Environment:** Debian WSL2 / Bare-Metal Linux, Node.js v26+, Python 3.14+ (UV toolchain)

---

## 1. Executive Summary & Goals

Dokumen spesifikasi arsitektur ini mendefinisikan integrasi terpadu antara:
1. **Claude Code CLI:** Agen pengembang otonom (*client-facing interface*).
2. **Headroom Proxy (v0.36.5+):** Lapisan optimasi konteks lokal cerdas dengan dukungan penuh paket ekstensi `[proxy, code, ml]` (SmartCrusher untuk JSON, Tree-sitter untuk AST code compression, dan Kompress-v2 ML untuk natural prose & agent traces).
3. **9Router Gateway (v16.2.1+):** Gateway perutean AI multi-akun dengan penerjemah protokol Anthropic $\rightarrow$ Google Gemini (OAuth Antigravity).
4. **Google Gemini 3.7 Flash High:** Model LLM target backend dengan efisiensi tinggi dan context window adaptif.

### Sasaran Utama:
* Memastikan aliran data berantai (*Chained Pipeline*) beroperasi secara stabil tanpa konflik port atau kesalahan jalur routing (`double /v1`).
* Memastikan seluruh fitur ekstensi Headroom (`[proxy]`, `[code]`, `[ml]`) aktif dan mengompresi payload secara adaptif.
* Memastikan telemetri dan statistik penghematan token tercatat secara *real-time* di Dashboard Headroom (`http://127.0.0.1:8787/dashboard`).
* Menjalankan pengujian stres *heavy agentic coding* di direktori sandbox terisolasi `~/dev/claude-test` di dalam sesi `tmux` stabil menggunakan metodologi **SDD $\times$ TDD $\times$ Subagent-DD**.

---

## 2. System Architecture & Topology

### 2.1 Component Mapping & Network Ports

| Komponen | Alamat Host / Port | Format Protokol | Peran & Tanggung Jawab |
| :--- | :--- | :--- | :--- |
| **Claude Code CLI** | Client Process | Anthropic REST / SSE | Menghasilkan instruksi, membaca file, memanggil tool, dan menyusun patch kode. |
| **Headroom Proxy** | `127.0.0.1:8787` | Anthropic Messages Inbound / Outbound | Mengompresi payload tool/code/prose, mencatat metrik sesi, dan meneruskan ke upstream target. |
| **9Router Gateway** | `127.0.0.1:20128` | Anthropic Inbound $\rightarrow$ Gemini Outbound | Menerjemahkan skema Anthropic ke format Gemini, mengelola kuota, dan menangani autentikasi Antigravity OAuth. |
| **Google Gemini API** | Cloud Endpoint | Google Gemini Protocol | Mengeksekusi penalaran (*reasoning*) dan menghasilkan keluaran kode. |

### 2.2 End-to-End Data Flow Diagram

```
+-----------------------------------------------------------------------------------+
| 1. CLIENT LAYER: Claude Code CLI                                                 |
|    - Running in tmux session: "claude-benchmark"                                  |
|    - Working Directory: ~/dev/claude-test                                         |
|    - Base URL: http://127.0.0.1:8787 (Headroom)                                  |
+----------------------------------------+------------------------------------------+
                                         | POST /v1/messages
                                         v
+-----------------------------------------------------------------------------------+
| 2. OPTIMIZATION LAYER: Headroom Proxy (:8787)                                     |
|    - Layer A: SmartCrusher [proxy] -> Lossless JSON & terminal log compression    |
|    - Layer B: Tree-sitter AST [code] -> Syntax-aware TypeScript/JS compression    |
|    - Layer C: Kompress-v2 ML [ml] -> Extractive token reduction on prose/traces   |
|    - Telemetry: Real-time recording to Dashboard & proxy_savings.json             |
+----------------------------------------+------------------------------------------+
                                         | POST /v1/messages (Compressed Payload)
                                         | via ANTHROPIC_TARGET_API_URL=:20128/v1
                                         v
+-----------------------------------------------------------------------------------+
| 3. ROUTING & TRANSLATION LAYER: 9Router Gateway (:20128)                          |
|    - Model Resolution: ag/gemini-3.7-flash-high                                   |
|    - Translation: Anthropic Message Schema -> Google Gemini Content Parts         |
|    - Auth Adapter: Google Antigravity OAuth Tokens                                |
+----------------------------------------+------------------------------------------+
                                         | HTTPS / Stream
                                         v
+-----------------------------------------------------------------------------------+
| 4. INFERENCE BACKEND: Google Gemini 3.7 Flash API                                 |
+-----------------------------------------------------------------------------------+
```

---

## 3. Configuration Specifications

### 3.1 Claude Code Configuration (`~/.claude/settings.json`)
```json
{
  "hasCompletedOnboarding": true,
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8787",
    "ANTHROPIC_AUTH_TOKEN": "sk-34e7519bfd3bce7c-hfg8u9-c9935674",
    "ANTHROPIC_DEFAULT_FABLE_MODEL": "ag/gemini-3.7-flash-high",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "ag/gemini-3.7-flash-high",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "ag/gemini-3.7-flash-high",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "ag/gemini-3.7-flash-high",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "160000"
  }
}
```
*Aturan Kritis:* `ANTHROPIC_BASE_URL` tidak boleh menyertakan `/v1` agar tidak memicu error double-path `/v1/v1/messages`.

### 3.2 Headroom Service Configuration (`systemd / environment`)
```bash
export HEADROOM_HOST="127.0.0.1"
export HEADROOM_PORT="8787"
export HEADROOM_MODE="cache"
export HEADROOM_BACKEND="anthropic"
export HEADROOM_TELEMETRY="off"
export ANTHROPIC_TARGET_API_URL="http://127.0.0.1:20128/v1"
```

### 3.3 9Router Internal State Preservation
* Konfigurasi database SQLite 9Router (`~/.9router/db/data.sqlite`) dipertahankan secara utuh tanpa mengubah pemetaan model atau provider connection yang sudah ada.
* `headroomEnabled` disetel ke `true` dengan `headroomUrl="http://localhost:8787"`.

---

## 4. Headroom Compression & Dashboard Tracking Specifications

### 4.1 Compression Engine Layers
1. **`[proxy]` (SmartCrusher):**
   * Beroperasi pada payload respon tool yang berisi array JSON panjang atau output terminal `bash`.
   * Mempertahankan integritas kunci dan tipe data.
2. **`[code]` (Code-Aware AST Compression):**
   * Menggunakan *parser* Tree-sitter multi-bahasa (8 bahasa terpasang: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++).
   * Menjamin kode keluaran 100% valid secara sintaksis.
3. **`[ml]` (Kompress-v2 ML Engine):**
   * Model berbasis ModernBERT (`chopratejas/kompress-v2-base`) yang dieksekusi secara efisien untuk memangkas *redundant tokens* pada percakapan natural.

### 4.2 Dashboard Telemetry & Endpoints
* **Dashboard URL:** `http://127.0.0.1:8787/dashboard`
* **Health Endpoint:** `http://127.0.0.1:8787/health`
* **Readiness Endpoint:** `http://127.0.0.1:8787/readyz`
* **Real-time Stats:** `http://127.0.0.1:8787/stats`
* **Transformation Feed:** `http://127.0.0.1:8787/transformations/feed`

---

## 5. Benchmark Task Specification (Pure TypeScript Async Engine)

### 5.1 Project Sandbox Environment
* **Root Directory:** `~/dev/claude-test/`
* **Stack:** Node.js (v26+), TypeScript (v5+), Vitest (v3+), ts-node.

### 5.2 Required Modules to be Built by Claude Code
1. **`src/core/StreamProcessor.ts`:**
   * Generic asynchronous stream processor `<T, R>`.
   * Mendukung backpressure queueing, sliding-window buffer, dan pipeline operators (`map`, `filter`, `batch`, `retryWithBackoff`).
2. **`src/events/TypedEventPipeline.ts`:**
   * Strongly-typed event emitter dengan cancellation token dan middleware interceptors.
3. **`src/ast/ASTMetadataExtractor.ts`:**
   * Parser TypeScript AST yang mengekstrak symbol declarations, type definitions, dan docstrings.
4. **`src/mock/MockLoadGenerator.ts`:**
   * Generator stream bervolume tinggi yang mensimulasikan kegagalan jaringan acak (chaos test) dan pemulihan otomatis.
5. **`tests/**/*.test.ts`:**
   * Test suite komprehensif dengan coverage minimal 90%+ yang dijalankan dengan Vitest.

### 5.3 Methodology Workflow: SDD x TDD x Subagent-DD
1. **Phase 1 (SDD):** Claude Code menyusun `SPEC.md` arsitektur modul terlebih dahulu.
2. **Phase 2 (TDD):** Claude Code menulis unit test dan integration test sebelum menulis kode implementasi.
3. **Phase 3 (Subagent-DD / Modular Implementation):** Claude Code mengimplementasikan modul satu per satu, menjalankan validasi mandiri (*self-verification*), dan merapikan kode hingga seluruh tes lulus (*100% green*).

---

## 6. Verification Plan & Quality Gates

```
+-------------------------------------------------------------------------------+
| QUALITY GATE 1: PRE-FLIGHT VERIFICATION                                       |
| - Verify Headroom HTTP 200 on :8787/health                                    |
| - Verify 9Router HTTP 200 on :20128/api/health                               |
| - Verify Tree-sitter [code] and Kompress [ml] loaded                          |
| - Execute end-to-end ping through :8787 -> :20128 -> Gemini API               |
+---------------------------------------+---------------------------------------+
                                        | PASS
                                        v
+-------------------------------------------------------------------------------+
| QUALITY GATE 2: HARNESS & PROMPT INJECTION                                    |
| - Setup sandbox directory: ~/dev/claude-test                                  |
| - Generate structured prompt via prompt-architect: PROMPT.md                  |
| - Launch persistent tmux session: "claude-benchmark"                          |
+---------------------------------------+---------------------------------------+
                                        | PASS
                                        v
+-------------------------------------------------------------------------------+
| QUALITY GATE 3: LIVE TELEMETRY ASSERTIONS                                     |
| - Assert client=claude in Headroom Dashboard                                  |
| - Assert transforms_applied contains router:code_aware and/or smart_crusher   |
| - Assert zero HTTP 400 / 429 / 502 errors in 9Router logs                    |
+---------------------------------------+---------------------------------------+
                                        | PASS
                                        v
+-------------------------------------------------------------------------------+
| QUALITY GATE 4: POST-EXECUTION VERIFICATION                                   |
| - Run test suite in sandbox: npx vitest run -> 100% PASS                      |
| - Extract final token savings summary from ~/.headroom/proxy_savings.json    |
+-------------------------------------------------------------------------------+
```

---

## 7. Spec Self-Review Audit

1. **Placeholder Scan:** Tidak ada placeholder `TODO`, `TBD`, atau instruksi yang menggantung. Seluruh port, URL, dan path terdefinisi secara eksplisit.
2. **Internal Consistency:** Topologi *Chained Pipeline* konsisten di seluruh dokumen dengan routing port `8787` (Headroom) $\rightarrow$ `20128` (9Router).
3. **Scope Check:** Ruang lingkup terisolasi dengan baik di `~/dev/claude-test` tanpa menyentuh file produksi `os-manager`.
4. **Ambiguity Check:** Format path URL (`/v1` handling) dijelaskan secara presisi untuk menghindari duplikasi path.

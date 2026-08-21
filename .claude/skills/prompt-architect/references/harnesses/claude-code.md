# Claude Code CLI Deep Harness Reference for Prompt Architect

Panduan komprehensif integrasi native tool Claude Code CLI (berdasarkan spesifikasi resmi [Claude Code Docs: Tools Reference](https://code.claude.com/docs/en/tools-reference)) untuk mengeksekusi alur kerja `prompt-architect`.

---

## 1. Master Tool Selection Matrix untuk Claude Code

| Tahapan Prompt Architect | Aksi Teknis | Native Tool Claude Code | Deskripsi & Parameter Kunci |
|---|---|---|---|
| **1. Context & File Ingestion** | Membaca draft prompt, file kode, spesifikasi, atau dokumen | `Read` | Mendukung file teks (`offset`, `limit`), PDF (`pages: "1-5"`), Jupyter notebook (`.ipynb`), dan gambar/diagram. |
| **2. Codebase Search & Discovery** | Menemukan file prompt, rule, atau referensi di project | `Grep` / `Glob` | `Grep` (ripgrep: `content`, `files_with_matches`, `count`, `multiline`), `Glob` (`**/*.{md,txt,ts}`). |
| **3. Web Extraction & Online Docs** | Mengambil panduan API / dokumentasi web publik | `WebFetch` | Mengonversi halaman web ke Markdown, auto-upgrade HTTPS, caching respons (`CLAUDE_CODE_WEBFETCH_CACHE_TTL_MS`). |
| **4. Web Search** | Menelusuri referensi prompting atau format library | `WebSearch` | Pencarian web dengan filter domain (`allowed_domains`, `blocked_domains`). |
| **5. Language Server Insights** | Memeriksa tipe data, simbol, atau hierarki kode sumber | `LSP` | Operasi definisi simbol, referensi, dan hover type info untuk context gathering. |
| **6. Template & Technique Loading** | Memuat struktur template framework secara akurat | `Read` | Membaca langsung `assets/templates/<framework>_template.txt` dan `references/techniques/few-shot.md`. |
| **7. Interactive Clarification** | Mengajukan 3–5 pertanyaan terarah kepada user | `AskUserQuestion` | Menampilkan menu opsi terstruktur atau write-in form interaktif (`askUserQuestionTimeout`). |
| **8. File Delivery & Persistence** | Menyimpan prompt hasil rekayasa ke file project/rule | `Write` / `Edit` | `Write` (buat file baru/overwrite), `Edit` (modifikasi bedah dengan `old_string` & `new_string`). |
| **9. Empirical Benchmarking (TDD)** | Menguji performa prompt baru vs lama di lingkungan terisolasi | `Agent` (Subagent) | Spawning subagent dengan kontrol tool (`tools`, `disallowedTools`, `maxTurns`, `isolation: worktree`). |
| **10. Task Tracking & Workflow** | Mengelola checklist perbaikan prompt multi-langkah | `TaskCreate` / `TaskUpdate` / `TodoWrite` | Tracking status tugas terstruktur di seluruh sesi agent. |

---

## 2. Invariant & Aturan Operasional Claude Code

1. **Read-Before-Edit / Read-Before-Write**:
   - Claude Code memberlakukan standar pembacaan file terlebih dahulu (`Read`) sebelum menjalankan `Edit` atau `Write` pada file yang sudah ada.
2. **Exact Character Matching pada `Edit`**:
   - Parameter `old_string` harus cocok persis dengan karakter, spasi, dan indentasi pada file. `old_string` harus unik (hanya muncul satu kali), atau gunakan `replace_all: true`.
3. **Working Directory & CWD Persistence**:
   - Perintah `cd` di dalam tool `Bash` akan bertahan ke perintah berikutnya selama tetap berada di dalam direktori project atau direktori yang diizinkan (`--add-dir`).
4. **Subagent Tool Scoping (`Agent`)**:
   - Batasi tool yang dapat diakses subagent menggunakan array `tools` atau `disallowedTools` pada frontmatter subagent.
5. **Tool Permissions Rules (`settings.json` / `/permissions`)**:
   - Aturan allow/deny spesifik per tool: `Bash(npm run *)`, `Read(src/**)`, `Edit(.agents/**)`, `WebFetch(domain:github.com)`.

---

## 3. Protokol Eksekusi Tiap Tahap di Claude Code

### Tahap 1: Ingestion Konteks via `Read`, `Grep`, atau `WebFetch`
```typescript
// 1. Membaca spesifikasi atau draft prompt lokal
Read({ file_path: "/workspace/docs/spec.md", offset: 1, limit: 150 })

// 2. Mencari prompt yang tersebar di codebase
Grep({ pattern: "system_prompt", path: "src/", output_mode: "content" })

// 3. Mengambil dokumentasi eksternal
WebFetch({ url: "https://code.claude.com/docs/en/tools-reference" })
```

### Tahap 2: Interactive Probing dengan `AskUserQuestion`
Gunakan `AskUserQuestion` untuk mengklarifikasi variabel yang hilang atau memilih framework:
```typescript
AskUserQuestion({
  question: "Pilih framework yang ingin digunakan untuk menstrukturkan prompt ini:",
  options: [
    "CO-STAR (Context, Objective, Style, Tone, Audience, Response)",
    "RISEN (Role, Instructions, Steps, End goal, Narrowing)",
    "TIDD-EC (Task, Instructions, Do, Don't, Examples, Context)",
    "BAB (Before, After, Bridge - untuk transformasi)"
  ]
})
```

### Tahap 3: Loading Template via `Read`
Sebelum menyusun prompt, muat template resmi dari direktori `assets/templates/`:
```typescript
Read({ file_path: ".agents/skills/prompt-architect/assets/templates/risen_template.txt" })
```

### Tahap 4: File Delivery via `Write`
Tulis prompt bersih yang telah direkayasa ke direktori tujuan:
```typescript
Write({
  file_path: ".agents/prompts/task-planner.txt",
  content: "[Isi prompt bersih tanpa header scaffold BEFORE/BRIDGE/CONTEXT]"
})
```

### Tahap 5: Subagent Verification via `Agent` Tool
Gunakan subagent terisolasi untuk menguji keandalan prompt baru:
```typescript
Agent({
  description: "Uji performa prompt baru vs prompt lama dengan skenario evaluasi",
  prompt: "Jalankan evaluasi komparatif antara prompt lama dan prompt baru dengan input [...]. Laporkan skor Clarity, Specificity, Context, Completeness, Structure.",
  tools: ["Read", "Bash"],
  maxTurns: 5
})
```

---

## 4. Claude Code CLI Commands & Workflows Reference

- `/compact`: Meringkas riwayat percakapan untuk menghemat context window.
- `/permissions`: Mengatur hak akses tool secara interaktif (Allow / Deny / Ask).
- `EnterPlanMode` & `ExitPlanMode`: Masuk ke mode perencanaan sebelum mengeksekusi rekayasa prompt multi-tahap.
- `TodoWrite` & `TaskList`: Memantau checklist perbaikan prompt secara real-time.

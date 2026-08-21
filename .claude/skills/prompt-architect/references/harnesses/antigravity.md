# Antigravity CLI (`agy`) Deep Harness Reference for Prompt Architect

Panduan komprehensif integrasi native Antigravity CLI (`agy`), Antigravity IDE, dan ekosistem MCP untuk mengeksekusi alur kerja `prompt-architect` secara aktif, terotomatisasi, dan bebas halusinasi.

---

## 1. Master Tool Selection Matrix untuk Prompt Architect

| Tahapan Prompt Architect | Aksi Teknis | Native Tool Antigravity | Fallback / Alternatif | Parameter Kunci & Invariant |
|---|---|---|---|---|
| **1. Context & Source Ingestion** | Membaca draft prompt, file spesifikasi, atau codebase | `view_file` | `grep_search` | `AbsolutePath`, 1-indexed (`StartLine`, `EndLine`), maks 800 baris/panggilan. |
| **2. Codebase Pattern & Search** | Menemukan definisi prompt, rules, atau system prompt lama | `grep_search` | `list_dir` | Regex/literal ripgrep, `SearchPath`, maks 50 hasil. |
| **3. Web & Online Spec Ingestion** | Mengambil dokumentasi framework/API publik | `read_url_content` | `search_web` | Mengonversi HTML ke Markdown bersih tanpa browser overhead. |
| **4. Library & Framework Syntax** | Memeriksa format resmi Next.js, Prisma, React, Anthropic SDK | `context7:query-docs` | `search_web` | Prioritaskan `context7` untuk referensi pustaka resmi. |
| **5. Template & Technique Loading** | Memuat struktur template framework secara presisi | `view_file` | — | Wajib membaca `assets/templates/<framework>_template.txt` & `references/techniques/few-shot.md`. |
| **6. Interactive Probing & Interview** | Mengajukan 3–5 pertanyaan klarifikasi / reverse role | `ask_question` | Chat text | Menampilkan modal UI interaktif (pilihan ganda / write-in form). |
| **7. Persistence & Delivery** | Menyimpan prompt hasil rekayasa ke file project/rule | `write_to_file` | Brain Artifact | Tulis ke `.agents/prompts/`, `.agents/rules/`, atau path target. |
| **8. Empirical Benchmarking** | Uji performa prompt baru vs lama (Pressure Test) | `invoke_subagent` | `run_command` | Spawning subagent tipe `research` atau `self` untuk membandingkan output. |
| **9. Long-Running Test Monitoring** | Menjalankan evaluasi batch multi-prompt di background | `run_command` (async) | `schedule` | Gunakan *Reactive Wakeup* (DILARANG polling status berulang-ulang). |

---

## 2. Invariant & Guardrail Operasional Antigravity

Saat mengoperasikan Antigravity CLI, seluruh agen wajib mematuhi aturan baku berikut:

1. **Standar Jalur POSIX**: Selalu gunakan garis miring (`/`) dan path absolut (contoh: `/home/username/project/...`). Dilarang menggunakan backslash Windows (`\`).
2. **1-Based Indexing**: `view_file`, `replace_file_content`, dan `multi_replace_file_content` berbasis 1-indexed (baris 1 adalah baris pertama).
3. **Exact Whitespace Matching**: Pada pengeditan file, `TargetContent` harus persis mencakup spasi, indentasi, dan newline. Selalu panggil `view_file` sebelum mengedit.
4. **Reactive Wakeup (Anti-Spinning)**: Jangan membuat loop polling dengan `schedule` pendek atau mengecek status berulang kali. Antigravity secara otomatis membangunkan agen ketika proses background atau subagent selesai.
5. **No Native `cd`**: Jangan pernah menjalankan perintah `cd` di dalam `run_command`. Gunakan parameter `Cwd`.
6. **Zero Scaffolding Emission**: Saat menulis prompt akhir ke file via `write_to_file`, seluruh header kerangka kerja (seperti `BEFORE:`, `BRIDGE:`, `CONTEXT:`) wajib dibersihkan agar prompt siap pakai.

---

## 3. Protokol Eksekusi Tiap Tahap

### Tahap 1: Ingestion & Assessment Bebas Copy-Paste
Jika pengguna meminta merevisi prompt atau membuat prompt berdasarkan file:
```bash
# 1. Baca langsung file sumber tanpa meminta user menyalin teks
view_file(AbsolutePath="/workspace/docs/spec.md", StartLine=1, EndLine=200)

# 2. Cari prompt yang sudah ada di repo
grep_search(SearchPath="/workspace", Query="system_prompt", IsRegex=false)

# 3. Ambil referensi web jika diberikan URL
read_url_content(Url="https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering")
```

### Tahap 2: Interactive Probing dengan `ask_question`
Gunakan tool `ask_question` untuk memunculkan modal interaktif yang rapi di IDE/CLI:
```json
{
  "questions": [
    {
      "question": "Framework mana yang paling sesuai dengan intensi Anda?",
      "options": [
        "(Recommended) CO-STAR (Untuk deliverable dengan tone, audience, dan format ketat)",
        "RISEN (Untuk SOP/prosedur langkah demi langkah dengan kriteria keberhasilan)",
        "TIDD-EC (Untuk instruksi yang memerlukan aturan Do & Don't eksplisit)",
        "BAB (Untuk transformasi/refactor dari draft lama ke draft baru)"
      ],
      "is_multi_select": false
    },
    {
      "question": "Apakah prompt ini membutuhkan contoh in-context (Few-Shot)?",
      "options": [
        "Ya, sertakan 2-3 contoh input->output konkret",
        "Tidak, instruksi zero-shot sudah cukup"
      ],
      "is_multi_select": false
    }
  ],
  "toolAction": "Mengklarifikasi parameter prompt",
  "toolSummary": "Klarifikasi kebutuhan prompt"
}
```

### Tahap 3: Loading Template Presisi
Sebelum menyusun prompt, baca template asli secara langsung untuk memastikan struktur slot terpenuhi:
```bash
view_file(AbsolutePath="/workspace/.agents/skills/prompt-architect/assets/templates/co-star_template.txt")
```
Jika menggunakan teknik tambahan (few-shot):
```bash
view_file(AbsolutePath="/workspace/.agents/skills/prompt-architect/references/techniques/few-shot.md")
```

### Tahap 4: Direct File Output & Persistence
Tulis prompt bersih langsung ke repositori atau direktori prompts:
```bash
write_to_file(
  TargetFile="/workspace/.agents/prompts/code-reviewer.txt",
  CodeContent="[Prompt bersih tanpa label scaffolding]",
  Overwrite=true,
  Description="Menyimpan engineered prompt untuk code reviewer menggunakan framework TIDD-EC"
)
```

### Tahap 5: Subagent Pressure Benchmarking (TDD for Prompts)
Untuk prompt kritis (mission-critical / high-stakes), jalankan evaluasi perbandingan:
```json
{
  "TypeName": "research",
  "TaskName": "Prompt Benchmark Evaluation",
  "TaskSummary": "Menguji respons model terhadap prompt lama vs prompt baru",
  "RecordingName": "prompt_benchmark_run",
  "Task": "Uji dua prompt berikut dengan tugas yang sama: [...]. Evaluasi output masing-masing menggunakan 5 dimensi (Clarity, Specificity, Context, Completeness, Structure) dan berikan laporan perbandingan."
}
```

---

## 4. Antigravity TUI & CLI Quick Reference

- **Compact Session**: Jalankan `/compact` pada chat Antigravity jika sesi pengujian prompt mulai panjang.
- **Model Switching**: Beralih antara Gemini Flash (kecepatan & pencarian) dan Gemini Pro / Claude Sonnet (penalaran arsitektur kompleks).
- **Headless Mode**: `agy -p "Engineering prompt X" --non-interactive` untuk batch prompt generation via CI/CD script.

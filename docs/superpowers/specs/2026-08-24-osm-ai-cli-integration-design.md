# Design Specification: Unified AI Gateway Control Plane (`osm ai`)

- **Date:** 2026-08-24
- **Status:** Approved / Ready for Implementation Planning
- **Authors:** Antigravity Architect & User
- **Target Environment:** Debian GNU/Linux 13 (Trixie) Bare-Metal / WSL2, Python 3.13+, Node.js v26+

---

## 1. Executive Summary & Goals

Dokumen spesifikasi ini mendefinisikan perancangan modul kontrol terpadu **`osm ai`** di dalam CLI `os-manager` (`osm`). Modul ini mengotomatiskan manajemen siklus hidup (*lifecycle orchestration*), *health monitoring*, dan peluncuran antarmuka web untuk tumpukan AI Gateway lokal:
1. **Headroom Proxy (v0.36.5+):** Port `8787` (Optimasi kompresi AST code, SmartCrusher, dan Kompress-v2 ML).
2. **9Router Gateway (v16.2.1+):** Port `20128` (Router multi-akun Antigravity OAuth $\rightarrow$ Gemini 3.7 Flash).

### Sasaran Utama:
* **Unified Control:** Mengontrol kedua gateway (start, stop, restart, status) melalui satu perintah CLI `osm ai`.
* **Dual Dashboard Launch:** Membuka kedua web dashboard (Headroom di `:8787/dashboard` dan 9Router di `:20128/dashboard`) secara instan ke browser default menggunakan `xdg-open` / browser subprocess handler.
* **Telemetry & Health Reporting:** Menampilkan ringkasan metrik real-time (status endpoint HTTP, provider aktif, akumulasi token tersimpan, dan estimasi biaya USD yang dihemat).
* **On-Demand Launching:** Mendukung sub-opsi `osm ai claude` untuk memastikan kedua gateway berjalan sebelum mengeksekusi Claude Code CLI.

---

## 2. CLI Command Interface & Subcommands

Perintah dasar: `osm ai <action> [options]`

| Subcommand / Action | Argumen Tambahan | Deskripsi & Perilaku |
| :--- | :--- | :--- |
| **`status`** | `--json` | Memeriksa ketersediaan HTTP port `8787` dan `20128`, membaca total request, token savings dari `~/.headroom/proxy_savings.json`, dan provider aktif dari SQLite `~/.9router/db/data.sqlite`. |
| **`start`** | `--daemon` | Memastikan 9Router aktif terlebih dahulu pada port `20128`, kemudian memastikan Headroom proxy aktif pada port `8787`. Mendukung systemd user units jika tersedia, atau fallback ke background process. |
| **`stop`** | - | Menghentikan service Headroom dan 9Router secara aman (*graceful SIGTERM*). |
| **`restart`** | - | Melakukan eksekusi `stop` diikuti dengan `start` secara berurutan dengan jeda verifikasi port. |
| **`dashboard`** | `--headroom-only`, `--9router-only` | Secara default membuka **kedua** URL di web browser default:<br>1. `http://127.0.0.1:8787/dashboard`<br>2. `http://127.0.0.1:20128/dashboard` |
| **`logs`** | `-n <lines>`, `-f` / `--follow` | Menampilkan atau mengalirkan (*stream*) log gabungan dari Headroom proxy dan 9Router gateway. |
| **`claude`** | `[claude-args...]` | Memverifikasi/menjalankan gateway jika belum aktif, mengonfigurasi `ANTHROPIC_BASE_URL="http://127.0.0.1:8787"`, lalu menjalankan biner `claude`. |

---

## 3. Component Architecture & Data Flow

```
                              ┌────────────────────────────────────────┐
                              │            CLI User ('osm')            │
                              └───────────────────┬────────────────────┘
                                                  │
                                       osm ai <action>
                                                  │
                                                  ▼
                        ┌────────────────────────────────────────────────────┐
                        │              os_manager/commands/ai.py             │
                        ├────────────────────────────────────────────────────┤
                        │  - HealthChecker (port 8787 & 20128)               │
                        │  - ServiceManager (systemd user unit / process)    │
                        │  - DashboardLauncher (xdg-open dual URLs)          │
                        │  - TelemetryParser (proxy_savings.json & sqlite)   │
                        └────────┬─────────────────┬────────────────┬────────┘
                                 │                 │                │
            ┌────────────────────┘                 │                └───────────────────┐
            ▼                                      ▼                                    ▼
┌───────────────────────┐            ┌───────────────────────────┐            ┌───────────────────────┐
│     Headroom Proxy    │            │     Web Browser Launch    │            │    9Router Gateway    │
│  - Port: 8787         │            │  - :8787/dashboard        │            │  - Port: 20128        │
│  - Health: /health    │            │  - :20128/dashboard       │            │  - Health: /api/health│
│  - Stats: /stats      │            │  via xdg-open / webbrowser│            │  - DB: data.sqlite    │
└───────────────────────┘            └───────────────────────────┘            └───────────────────────┘
```

---

## 4. Technical Implementation Details

### 4.1 Modul `os_manager/commands/ai.py`
Struktur kelas dan fungsi:
- `check_gateway_health() -> dict`:
  - Query `http://127.0.0.1:8787/health` $\rightarrow$ periksa status code `200`.
  - Query `http://127.0.0.1:20128/api/health` $\rightarrow$ periksa JSON `{"ok": true}`.
- `get_telemetry_summary() -> dict`:
  - Baca `~/.headroom/proxy_savings.json` untuk mengekstrak `total_tokens_saved`, `requests`, `compression_savings_usd`.
  - Baca `~/.9router/db/data.sqlite` untuk mengekstrak provider aktif (`providerConnections`).
- `open_dashboards(headroom: bool = True, router: bool = True) -> int`:
  - Eksekusi `webbrowser.open()` atau `xdg-open` untuk `http://127.0.0.1:8787/dashboard` dan `http://127.0.0.1:20128/dashboard`.
- `manage_services(action: str) -> int`:
  - `start`: Eksekusi `systemctl --user start headroom-default` atau fallback subprocess background, serta spawn 9router daemon.
  - `stop`: Eksekusi `systemctl --user stop headroom-default` dan kill 9router process.
  - `restart`: Rangkaian stop dan start.
- `run_ai(argv: list[str]) -> int`: Entrypoint dispatcher argparse untuk perintah `osm ai`.

### 4.2 Integrasi Router CLI `os_manager/cli.py`
- Menambahkan parser `ai` ke `build_parser()`.
- Menghubungkan eksekusi `args.command == "ai"` ke `from .commands.ai import run_ai`.

---

## 5. Error Handling & Edge Cases

1. **Browser Tidak Tersedia di Headless/SSH:**
   - Deteksi apakah environment memiliki display server (`$DISPLAY` atau `$WAYLAND_DISPLAY`).
   - Jika berjalan di mode headless murni tanpa GUI, cetak tautan URL secara rapi ke terminal agar pengguna dapat mengekliknya secara manual.
2. **Port Conflict atau Gateway Down:**
   - `osm ai status` harus menampilkan pesan diagnostik yang jelas jika salah satu atau kedua gateway offline.
   - `osm ai start` harus memverifikasi bahwa port telah mendengarkan (*listening*) sebelum keluar.
3. **Persistensi Database 9Router:**
   - Dilarang memodifikasi isi SQLite 9Router saat membaca status (akses *read-only* dengan `sqlite3.connect('file:...?mode=ro', uri=True)`).

---

## 6. Testing & Quality Gates

1. **Unit Test (`tests/test_ai_command.py`):**
   - Mocking HTTP requests untuk endpoint `:8787` dan `:20128`.
   - Mocking browser launcher `webbrowser.open` / `subprocess.Popen(['xdg-open', ...])`.
   - Verifikasi output tabular dan JSON untuk `osm ai status`.
   - Verifikasi exit codes untuk semua aksi (`start`, `stop`, `restart`, `dashboard`, `logs`).
2. **Master Test Suite Verification:**
   - `pytest tests/test_ai_command.py` 100% pass.
   - `osm ai --help` dan `osm ai status` tervalidasi langsung di CLI.

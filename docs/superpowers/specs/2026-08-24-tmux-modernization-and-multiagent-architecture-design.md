# Design Spec: Modern Modular Tmux & Multi-Agent Orchestration Suite

- **Date:** 2026-08-24
- **Target Environment:** Debian WSL2 & Bare-Metal Linux (`tmux 3.5a`)
- **Status:** Draft / Approved Design
- **Author:** Antigravity AI & Human Architect

---

## 1. Overview & Objectives

Proyek ini bertujuan untuk merombak total konfigurasi dan ekosistem `tmux` di lingkungan sistem operasi `os-manager` (Debian WSL2 & Bare-Metal Linux), menggabungkan arsitektur modular XDG-compliant, fitur mutakhir `tmux 3.5a` (Floating Popups, OSC 52 Clipboard, Dynamic Statusline), ekosistem plugin lengkap TPM (*Complete Plugin Suite*), dan subsistem orkestrasi *Multi-Agent* canggih yang mendukung kolaborasi Google Antigravity (`agy`), Anthropic Claude Code (`claude`), hierarki *Boss-Worker*, dan isolasi *Git Worktrees*.

---

## 2. Arsitektur Komponen & Struktur Direktori

### 2.1 Tata Letak File Konfigurasi Modular (`~/.config/tmux/`)

Konfigurasi dipecah menjadi modul-modul terfokus di bawah standar XDG Base Directory dengan symlink kompatibilitas di `~/.tmux.conf`:

```text
~/.config/tmux/
├── tmux.conf                 # Master entrypoint (me-load conf.d/*.conf & inisialisasi TPM)
├── conf.d/
│   ├── 00-options.conf       # Pengaturan server & session (TrueColor, base-index 1, mouse, title)
│   ├── 10-keybindings.conf   # Prefix C-a, Vim-tmux navigation, splitting PWD, resize, sync
│   ├── 20-popups.conf        # Floating popups (Scratchpad, Session Switcher, Help, LazyGit)
│   ├── 30-statusline.conf    # Statusline modern (Git telemetry, CPU/RAM, Host, Window tags)
│   └── 90-plugins.conf       # Complete TPM Plugin Suite & individual plugin configurations
├── cheatsheet.txt            # Ringkasan interaktif shortcut untuk Floating Help Popup
└── plugins/                  # Direktori instalasi plugin TPM (~/.config/tmux/plugins/tpm)
```

### 2.2 Symlink Kompatibilitas Sistem
- `~/.tmux.conf` diarahkan secara simbolik ke `~/.config/tmux/tmux.conf` untuk kompatibilitas dengan tool pihak ketiga atau shell lama.

---

## 3. Detail Spesifikasi Konfigurasi

### 3.1 Server & Session Options (`00-options.conf`)
* **Terminal Emulation & True Color:**
  - `default-terminal "tmux-256color"`
  - `terminal-overrides ",*256col*:Tc,xterm-kitty:Tc,alacritty:Tc,foot:Tc,ghostty:Tc"`
  - Dukungan penuh undercurl dan styling teks 24-bit.
* **Ergonomi & Indexing:**
  - `base-index 1` dan `pane-base-index 1` (Penomoran window dan pane dimulai dari 1).
  - `renumber-windows on` (Otomatis merapikan penomoran window saat ada window yang ditutup).
  - `escape-time 0` (Zero-latency tombol `ESC` untuk Neovim/Vim).
  - `history-limit 50000` (Buffer scrollback 50k baris untuk riwayat log agent).
  - `mouse on` (Dukungan scroll mouse, pemilihan pane, dan resize visual).
  - `focus-events on` (Meneruskan event focus terminal ke editor).
  - `set-titles on` dan `set-titles-string "#S:#I:#W - #T"` (Update judul terminal otomatis).

### 3.2 Keybindings & Navigasi Ergonomis (`10-keybindings.conf`)
* **Prefix Key:**
  - `set -g prefix C-a` (Menggantikan `C-b` dengan `Ctrl+a`).
  - `bind C-a send-prefix` (Menekan `Ctrl+a` dua kali meneruskan prefix ke program CLI).
* **Reload Konfigurasi:**
  - `bind r source-file ~/.config/tmux/tmux.conf \; display-message "✨ tmux.conf reloaded successfully!"`
* **Splitting & Window Management:**
  - `bind | split-window -h -c "#{pane_current_path}"` (Split horizontal mempertahankan `$PWD`).
  - `bind - split-window -v -c "#{pane_current_path}"` (Split vertikal mempertahankan `$PWD`).
  - `bind c new-window -c "#{pane_current_path}"` (Window baru di `$PWD`).
  - `bind _ split-window -fv -c "#{pane_current_path}"` (Full-width bottom split).
  - `bind \ split-window -fh -c "#{pane_current_path}"` (Full-height right split).
* **Vim-Tmux Seamless Navigation (Tanpa Prefix):**
  - Terintegrasi dengan plugin `christoomey/vim-tmux-navigator`: `Ctrl+h`, `Ctrl+j`, `Ctrl+k`, `Ctrl+l`.
* **Pane Resizing & Zoom:**
  - `bind -r H resize-pane -L 5`
  - `bind -r J resize-pane -D 5`
  - `bind -r K resize-pane -U 5`
  - `bind -r L resize-pane -R 5`
  - `bind m resize-pane -Z` (Toggle zoom pane).
* **Window Navigation:**
  - `bind -r [ previous-window` dan `bind -r ] next-window`
  - `bind -r < swap-window -d -t -1` dan `bind -r > swap-window -d -t +1`
* **Vi-Mode Copy & Clipboard OSC 52:**
  - `setw -g mode-keys vi`
  - `bind-key -T copy-mode-vi v send-keys -X begin-selection`
  - `bind-key -T copy-mode-vi C-v send-keys -X rectangle-toggle`
  - `bind-key -T copy-mode-vi y send-keys -X copy-pipe-and-cancel` (OSC 52 clipboard native).
* **Pane Synchronization Toggle:**
  - `bind y setw synchronize-panes \; display-message "🔁 Synchronize Panes: #{?pane_synchronized,ON,OFF}"`

### 3.3 Floating Popups Suite (`20-popups.conf`)
Memanfaatkan fitur native `display-popup` pada `tmux 3.5a`:
1. **Floating Scratchpad Shell (`Alt + t` / `prefix + Tab`):**
   - Modal melayang 85% lebar dan 80% tinggi di direktori aktif.
   - Menggunakan sesi persisten `scratchpad` (`tmux new-session -A -s scratchpad`).
2. **Fuzzy Session Switcher (`prefix + s` / `Ctrl + j`):**
   - Modal popup 70% lebar dan 60% tinggi menjalankan `fzf` interaktif untuk berpindah sesi dalam 1 detik.
3. **Interactive LazyGit / Git TUI (`prefix + g` / `Alt + g`):**
   - Modal popup 90% x 85% menjalankan `lazygit` atau fallback ke `git status`.
4. **Instant Cheatsheet Popup (`prefix + ?`):**
   - Modal popup 80% x 75% menampilkan file `~/.config/tmux/cheatsheet.txt` menggunakan `less -R`.

### 3.4 Modern Statusline Theme (`30-statusline.conf`)
* Tema gelap modern kontras tinggi (*Dark Modern Mocha*):
  - `status-position bottom`
  - `status-interval 5` (Efisien CPU).
  - `status-style "bg=#1e1e2e,fg=#cdd6f4"`
* **Status-Left:**
  - Badge sesi aktif: `#[fg=#11111b,bg=#a6e3a1,bold] #S #[default]`
  - Indikator prefix & copy mode: `#{prefix_highlight}`
* **Window Format (Center):**
  - Non-aktif: `#[fg=#6c7086,bg=#1e1e2e] #I:#W `
  - Aktif: `#[fg=#11111b,bg=#89b4fa,bold] #I:#W#{?window_zoomed_flag, 🔍,} #[default]`
* **Status-Right:**
  - Git Branch: `#[fg=#f38ba8] #(cd #{pane_current_path}; git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "-") #[default]`
  - Current Dir: `#[fg=#cba6f7]📂 #{b:pane_current_path} #[default]`
  - System CPU/RAM: `#[fg=#fab387]#{cpu_percentage} #[default]`
  - Clock & Date: `#[fg=#94e2d5]%H:%M #[fg=#f9e2af]%d-%b-%y`

### 3.5 Complete TPM Plugin Suite (`90-plugins.conf`)
Daftar plugin yang diintegrasikan dan dikonfigurasi:
1. `tmux-plugins/tpm` (Plugin manager engine).
2. `tmux-plugins/tmux-sensible` (Baseline standar industri).
3. `tmux-plugins/tmux-resurrect` (Restore session/windows/panes & editor state).
4. `tmux-plugins/tmux-continuum` (Auto-save tiap 15m & auto-restore on boot).
5. `tmux-plugins/tmux-sessionist` (Manipulasi sesi via shortcut).
6. `christoomey/vim-tmux-navigator` (Integrasi navigasi seamless Neovim/Vim).
7. `tmux-plugins/tmux-pain-control` (Kontrol pane & splitting).
8. `tmux-plugins/tmux-yank` (Integrasi clipboard).
9. `tmux-plugins/tmux-copycat` (Regex searching).
10. `tmux-plugins/tmux-open` (Membuka URL/file highlighted).
11. `wfxr/tmux-fzf-url` (Popup picker untuk link di buffer).
12. `sainnhe/tmux-fzf` (FZF tmux controller).
13. `tmux-plugins/tmux-logging` (Logging riwayat terminal pane).
14. `tmux-plugins/tmux-prefix-highlight` (Statusbar prefix visual indicator).
15. `tmux-plugins/tmux-cpu` (Monitor utilisasi CPU/RAM).

---

## 4. Subsistem Multi-Agent & Worktree Orchestration

### 4.1 Orchestrator Script (`scripts/tmux_agents.sh`)
Skrip orkestrasi di-upgrade secara menyeluruh dengan fitur sub-perintah:

| Sub-perintah | Argumen | Fungsi |
| :--- | :--- | :--- |
| `start` / `pair` | `[session_name]` | Meluncurkan sesi dual-agent 3-pane (`agy` kiri, `claude` kanan atas, `htop` kanan bawah). |
| `company` | `[n_workers]` | Meluncurkan layout Boss-Worker matrix (1 Boss pane + N Worker panes). |
| `worktree add` | `<branch_name>` | Otomatis membuat branch terisolasi, checkout ke `.worktrees/<branch>`, dan spawn pane baru di folder tersebut. |
| `worktree list` | *(none)* | Menampilkan daftar worktree aktif beserta status agent di dalamnya. |
| `worktree clean`| `<branch_name>` | Menghapus folder worktree dan branch secara aman setelah tugas selesai. |
| `capture` | `<pane_target>` `[lines]` | Mengambil log snapshot dari buffer agent tertentu tanpa interupsi. |
| `clear-all` | `[session_name]` | Mengirimkan perintah `/clear` ke semua pane worker secara paralel untuk mereset context window. |
| `kill` | `[session_name]` | Menghentikan sesi workspace secara anggun (*graceful termination*). |

### 4.2 Floating Agent Menu Popup (`prefix + A`)
Menyediakan antarmuka interaktif instan di dalam tmux untuk meluncurkan mode pairing, spawn worker baru, atau broadcast context reset.

### 4.3 Skill Synchronization (`.agents/skills/tmux-agents/SKILL.md`)
Dokumentasi skill diperbarui untuk memuat seluruh sub-perintah baru, alur kerja worktree, dan panduan manajemen multi-agent.

---

## 5. Rencana Pengujian & Verifikasi (Verification Criteria)

1. **Syntax & Config Verification:**
   - Memastikan `tmux source-file ~/.config/tmux/tmux.conf` berjalan tanpa error (`exit code 0`).
2. **TPM Auto-Bootstrap Test:**
   - Menguji instalasi otomatis TPM saat folder plugin kosong.
3. **Popup & Keybinding Test:**
   - Menguji spawn floating scratchpad (`Alt+t`), session switcher (`prefix + s`), dan cheatsheet (`prefix + ?`).
4. **Multi-Agent Script Execution Test:**
   - Menjalankan `scripts/tmux_agents.sh pair` dan memverifikasi ketiga pane (`agy`, `claude`, `monitoring`) terinisialisasi dengan benar.
   - Menjalankan `scripts/tmux_agents.sh worktree add test-branch` dan memverifikasi pembuatan worktree terisolasi.
   - Menjalankan `scripts/tmux_agents.sh capture` dan memverifikasi pembacaan buffer pane.
5. **Session Persistence Test:**
   - Menguji `tmux-resurrect` save (`prefix + Ctrl-s`) dan restore (`prefix + Ctrl-r`).

---

## 6. Self-Review Kualitas Desain

- [x] **Placeholder scan:** Tidak ada TODO/TBD yang belum terselesaikan.
- [x] **Internal consistency:** Semua modul konfigurasi di `conf.d/` selaras dengan master `tmux.conf` dan script orkestrasi.
- [x] **Scope check:** Desain terfokus pada perombakan tmux, ekosistem plugin, dan multi-agent suite tanpa mengubah komponen OS di luar scope.
- [x] **Ambiguity check:** Seluruh keybinding, struktur direktori, dan sub-perintah CLI didefinisikan secara eksplisit.

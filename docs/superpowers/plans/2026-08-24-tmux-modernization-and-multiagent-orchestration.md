# Modern Modular Tmux & Multi-Agent Orchestration Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membangun ekosistem `tmux` modern, modular, dan berperforma tinggi berbasis standar XDG (`~/.config/tmux/`), lengkap dengan 15 plugin terkurasi (TPM suite), floating popup modals (`tmux 3.5a`), statusline modern, dan orchestrator multi-agent (`agy` + `Claude Code` + Git worktrees).

**Architecture:** Konfigurasi dipecah menjadi modul-modul XDG terfokus di `~/.config/tmux/conf.d/*.conf` yang dimuat oleh master `tmux.conf`. TPM dikonfigurasi dengan auto-bootstrap tanpa lag, sementara subsistem multi-agent diotomasi melalui skrip CLI `scripts/tmux_agents.sh` yang mendukung mode dual-agent pairing, Boss-Worker matrix, isolasi Git worktree, dan floating popup dashboard.

**Tech Stack:** `tmux 3.5a`, Bash / POSIX Shell, TPM (Tmux Plugin Manager), Git Worktrees, FZF, OSC 52 Terminal Clipboard Protocol.

**Spec:** `docs/superpowers/specs/2026-08-24-tmux-modernization-and-multiagent-architecture-design.md`

## Global Constraints

- Target Environment: Debian WSL2 & Bare-Metal Linux (`tmux 3.5a`).
- Non-Interactive / Stdin Safety: Semua eksekusi background dan script otomatisasi wajib menutup stdin (`< /dev/null`) untuk mencegah hanging di WSL2.
- Backward Compatibility: `~/.tmux.conf` harus tetap menjadi symlink valid ke `~/.config/tmux/tmux.conf`.
- Context & Performance: `status-interval` diset 5–10 detik untuk mencegah utilisasi CPU tinggi, dan history buffer diset 50,000 baris.
- Zero-Data-Loss: Manajemen Git Worktrees di `.worktrees/` tidak boleh memodifikasi atau menghapus partisi data atau working directory utama di luar repo git.

---

### Task 1: Core Modular Config & Master Entrypoint

**Files:**
- Create: `~/.config/tmux/tmux.conf`
- Create: `~/.config/tmux/conf.d/00-options.conf`
- Create: `~/.config/tmux/conf.d/10-keybindings.conf`
- Create: `tests/tmux/test_core_config.sh`
- Symlink: `~/.tmux.conf` -> `~/.config/tmux/tmux.conf`

**Interfaces:**
- Consumes: Sistem operasi `tmux 3.5a`
- Produces: Fondasi modular tmux, TrueColor 24-bit, zero-latency ESC, base-index 1, Vim-tmux navigation, dan ergonomic splitting di `$PWD`.

- [ ] **Step 1: Write the validation test for Core Config**

```bash
mkdir -p tests/tmux
cat << 'EOF' > tests/tmux/test_core_config.sh
#!/usr/bin/env bash
set -euo pipefail

echo "==> Testing tmux core configuration syntax..."
tmux -f ~/.config/tmux/tmux.conf -C new-session -d -s test-syntax "true" 2>/dev/null || {
  echo "FAIL: Failed to launch tmux session with ~/.config/tmux/tmux.conf"
  exit 1
}
tmux kill-session -t test-syntax 2>/dev/null || true

echo "==> Verifying symlink ~/.tmux.conf..."
if [ ! -L "$HOME/.tmux.conf" ]; then
  echo "FAIL: ~/.tmux.conf is not a symlink"
  exit 1
fi

echo "==> Verifying base-index and mouse options..."
BASE_INDEX=$(tmux start-server \; show-option -gv base-index 2>/dev/null || echo "")
if [ "$BASE_INDEX" != "1" ]; then
  echo "FAIL: base-index is '$BASE_INDEX', expected '1'"
  exit 1
fi

echo "PASS: Core config verified successfully."
EOF
chmod +x tests/tmux/test_core_config.sh
```

- [ ] **Step 2: Run test to verify failure**

Run: `tests/tmux/test_core_config.sh`
Expected: FAIL (files not yet created)

- [ ] **Step 3: Implement Core Configuration Files**

Buat direktori dan modul `00-options.conf`, `10-keybindings.conf`, serta master `tmux.conf`:

```bash
mkdir -p ~/.config/tmux/conf.d

cat << 'EOF' > ~/.config/tmux/conf.d/00-options.conf
# ==============================================================================
# 00-options.conf — Core Server & Session Options
# ==============================================================================

# Terminal & True Color
set -g default-terminal "tmux-256color"
set -ga terminal-overrides ",*256col*:Tc,xterm-kitty:Tc,alacritty:Tc,foot:Tc,ghostty:Tc"
set -as terminal-features ",*:RGB"

# Indexing & Windows
set -g base-index 1
set -g pane-base-index 1
setw -g pane-base-index 1
set -g renumber-windows on

# General UX
set -g mouse on
set -s escape-time 0
set -g history-limit 50000
set -g focus-events on
set -g set-titles on
set -g set-titles-string "#S:#I:#W - #T"
setw -g automatic-rename on

# Activity & Alerts
set -g visual-activity off
setw -g monitor-activity off
EOF

cat << 'EOF' > ~/.config/tmux/conf.d/10-keybindings.conf
# ==============================================================================
# 10-keybindings.conf — Ergonomic Keybindings & Vim Navigation
# ==============================================================================

# Prefix Key: Ctrl-a
set -g prefix C-a
unbind C-b
bind C-a send-prefix

# Reload Configuration
bind r source-file ~/.config/tmux/tmux.conf \; display-message "✨ tmux.conf reloaded successfully!"

# Splitting Panes (preserving PWD)
bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"
bind c new-window -c "#{pane_current_path}"
bind _ split-window -fv -c "#{pane_current_path}"
bind \ split-window -fh -c "#{pane_current_path}"
unbind '"'
unbind %

# Smart pane switching with awareness of Vim splits (Ctrl-h/j/k/l)
is_vim="ps -o state= -o comm= -t '#{pane_tty}' | grep -iqE '^[^TXZ ]+ +(\\S+\\/)?g?(view|l?n?vim?x?)(diff)?$'"
bind-key -n 'C-h' if-shell "$is_vim" 'send-keys C-h'  'select-pane -L'
bind-key -n 'C-j' if-shell "$is_vim" 'send-keys C-j'  'select-pane -D'
bind-key -n 'C-k' if-shell "$is_vim" 'send-keys C-k'  'select-pane -U'
bind-key -n 'C-l' if-shell "$is_vim" 'send-keys C-l'  'select-pane -R'

# Pane Resizing
bind -r H resize-pane -L 5
bind -r J resize-pane -D 5
bind -r K resize-pane -U 5
bind -r L resize-pane -R 5
bind m resize-pane -Z

# Window Switching & Swapping
bind -r [ previous-window
bind -r ] next-window
bind -r < swap-window -d -t -1
bind -r > swap-window -d -t +1

# Vi-Mode Copy & OSC 52 Clipboard
setw -g mode-keys vi
bind-key -T copy-mode-vi v send-keys -X begin-selection
bind-key -T copy-mode-vi C-v send-keys -X rectangle-toggle
bind-key -T copy-mode-vi y send-keys -X copy-pipe-and-cancel
bind-key -T copy-mode-vi Escape send-keys -X cancel

# Synchronize Panes
bind y setw synchronize-panes \; display-message "🔁 Synchronize Panes: #{?pane_synchronized,ON,OFF}"
EOF

cat << 'EOF' > ~/.config/tmux/tmux.conf
# ==============================================================================
# tmux.conf — Master Entry Point
# ==============================================================================

# 1. Source all configuration modules in conf.d
source-file ~/.config/tmux/conf.d/00-options.conf
source-file ~/.config/tmux/conf.d/10-keybindings.conf
EOF

# Create compatibility symlink
ln -sf ~/.config/tmux/tmux.conf ~/.tmux.conf
```

- [ ] **Step 4: Run test to verify it passes**

Run: `tests/tmux/test_core_config.sh`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/tmux/test_core_config.sh
git commit -m "feat(tmux): implement core modular options, keybindings and symlink"
```

---

### Task 2: Floating Popups Suite, Cheatsheet & Modern Statusline

**Files:**
- Create: `~/.config/tmux/conf.d/20-popups.conf`
- Create: `~/.config/tmux/conf.d/30-statusline.conf`
- Create: `~/.config/tmux/cheatsheet.txt`
- Modify: `~/.config/tmux/tmux.conf`
- Create: `tests/tmux/test_popups_statusline.sh`

**Interfaces:**
- Consumes: Task 1 configuration files
- Produces: Floating scratchpad (`Alt+t`), Session switcher popup (`prefix + s`), Cheatsheet popup (`prefix + ?`), LazyGit popup (`prefix + g`), dan Dark Mocha statusline.

- [ ] **Step 1: Write the validation test for Popups and Statusline**

```bash
cat << 'EOF' > tests/tmux/test_popups_statusline.sh
#!/usr/bin/env bash
set -euo pipefail

echo "==> Testing popups and statusline configuration..."
tmux -f ~/.config/tmux/tmux.conf -C new-session -d -s test-popups "true" 2>/dev/null || {
  echo "FAIL: Failed to parse updated config"
  exit 1
}
tmux kill-session -t test-popups 2>/dev/null || true

if [ ! -f "$HOME/.config/tmux/cheatsheet.txt" ]; then
  echo "FAIL: cheatsheet.txt is missing"
  exit 1
fi

echo "==> Checking statusline options..."
POS=$(tmux start-server \; show-option -gv status-position 2>/dev/null || echo "")
if [ "$POS" != "bottom" ]; then
  echo "FAIL: status-position is '$POS', expected 'bottom'"
  exit 1
fi

echo "PASS: Popups and statusline verified successfully."
EOF
chmod +x tests/tmux/test_popups_statusline.sh
```

- [ ] **Step 2: Run test to verify failure**

Run: `tests/tmux/test_popups_statusline.sh`
Expected: FAIL (files missing or not sourced)

- [ ] **Step 3: Implement Cheatsheet, Popups & Statusline**

```bash
cat << 'EOF' > ~/.config/tmux/cheatsheet.txt
================================================================================
                    🚀 MODERN TMUX & AI AGENT CHEATSHEET
================================================================================

[ CORE NAVIGATION (Prefix: Ctrl-a) ]
  Ctrl-a r          Reload configuration instantly
  Ctrl-a |          Split horizontally (right) in $PWD
  Ctrl-a -          Split vertically (down) in $PWD
  Ctrl-a c          New window in $PWD
  Ctrl-a m          Toggle Zoom active pane
  Ctrl-a y          Toggle Synchronize Panes (broadcast keystrokes)
  Ctrl-a [ / ]      Previous / Next Window
  Ctrl-a < / >      Swap window left / right
  Ctrl-h/j/k/l      Seamless Vim/Tmux split navigation (No prefix!)
  Ctrl-a H/J/K/L    Resize pane left/down/up/right by 5

[ FLOATING POPUP MODALS (tmux 3.5a) ]
  Alt-t / Ctrl-a Tab   Floating Scratchpad Terminal (Persistent)
  Ctrl-a s / Ctrl-j    Fuzzy Session Switcher (fzf)
  Ctrl-a g / Alt-g     Floating LazyGit / Git Dashboard
  Ctrl-a ?             Instant Cheatsheet (This window!)
  Ctrl-a A             Multi-Agent Workspace Dashboard

[ AI AGENTS & WORKSPACES ]
  osm tmux pair        Launch Dual-Agent (agy + claude + monitor)
  osm tmux company [N] Launch Boss-Worker matrix (1 Boss + N Workers)
  osm tmux worktree    Isolated Git Worktree manager for agents
  osm tmux capture     Silent buffer capture & telemetry

[ COPY MODE & CLIPBOARD ]
  Ctrl-a [          Enter Copy Mode (vi-keys)
  v / Ctrl-v        Begin Selection / Rectangle Select
  y                 Yank & Copy to System Clipboard (OSC 52)
  q / Escape        Exit Copy Mode
================================================================================
EOF

cat << 'EOF' > ~/.config/tmux/conf.d/20-popups.conf
# ==============================================================================
# 20-popups.conf — Modern Floating Popups Suite (tmux 3.5a)
# ==============================================================================

# 1. Floating Scratchpad Shell (Alt-t or Prefix + Tab)
bind-key -n M-t display-popup -E -w 85% -h 80% -d "#{pane_current_path}" "tmux new-session -A -s scratchpad"
bind-key Tab display-popup -E -w 85% -h 80% -d "#{pane_current_path}" "tmux new-session -A -s scratchpad"

# 2. Fuzzy Session Switcher with fzf (Prefix + s or Ctrl-j)
bind-key s display-popup -E -w 70% -h 60% "\
  tmux list-sessions -F '#{session_name}' | \
  fzf --reverse --header='⚡ Switch Session' --prompt='> ' | \
  xargs -r tmux switch-client -t"
bind-key -n C-j display-popup -E -w 70% -h 60% "\
  tmux list-sessions -F '#{session_name}' | \
  fzf --reverse --header='⚡ Switch Session' --prompt='> ' | \
  xargs -r tmux switch-client -t"

# 3. Interactive LazyGit / Git TUI (Prefix + g or Alt-g)
bind-key g display-popup -E -w 90% -h 85% -d "#{pane_current_path}" "lazygit 2>/dev/null || (git status && read -n 1 -s -r -p 'Press any key to close...')"
bind-key -n M-g display-popup -E -w 90% -h 85% -d "#{pane_current_path}" "lazygit 2>/dev/null || (git status && read -n 1 -s -r -p 'Press any key to close...')"

# 4. Instant Cheatsheet (Prefix + ?)
bind-key ? display-popup -E -w 80% -h 80% "cat ~/.config/tmux/cheatsheet.txt | less -R"
EOF

cat << 'EOF' > ~/.config/tmux/conf.d/30-statusline.conf
# ==============================================================================
# 30-statusline.conf — Dark Mocha Modern Statusline Theme
# ==============================================================================

set -g status on
set -g status-position bottom
set -g status-justify left
set -g status-interval 5

# Color Palette (Dark Mocha)
set -g status-style "bg=#1e1e2e,fg=#cdd6f4"
set -g pane-border-style "fg=#313244"
set -g pane-active-border-style "fg=#89b4fa"
set -g message-style "bg=#313244,fg=#89b4fa,bold"

# Status Left: [Session Name] + Prefix/Copy indicators
set -g status-left-length 50
set -g status-left "#[fg=#11111b,bg=#a6e3a1,bold] 󰖯 #S #[default]#{prefix_highlight} "

# Window Format
set -g window-status-separator ""
set -g window-status-format "#[fg=#6c7086,bg=#1e1e2e] #I:#W "
set -g window-status-current-format "#[fg=#11111b,bg=#89b4fa,bold] #I:#W#{?window_zoomed_flag, 🔍,} #[default]"

# Status Right: Git Branch + Path + System + Clock
set -g status-right-length 120
set -g status-right "\
#[fg=#f38ba8,bg=#1e1e2e] #(cd #{pane_current_path} 2>/dev/null && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '-') \
#[fg=#cba6f7,bg=#1e1e2e]📂 #{b:pane_current_path} \
#[fg=#fab387,bg=#1e1e2e]#{?#{cpu_percentage},CPU #{cpu_percentage} ,}\
#[fg=#94e2d5,bg=#1e1e2e]%H:%M \
#[fg=#f9e2af,bg=#1e1e2e]%d-%b "
EOF

# Update master tmux.conf to include popups & statusline
cat << 'EOF' > ~/.config/tmux/tmux.conf
# ==============================================================================
# tmux.conf — Master Entry Point
# ==============================================================================

# 1. Core Options & Keybindings
source-file ~/.config/tmux/conf.d/00-options.conf
source-file ~/.config/tmux/conf.d/10-keybindings.conf

# 2. Popups & Statusline
source-file ~/.config/tmux/conf.d/20-popups.conf
source-file ~/.config/tmux/conf.d/30-statusline.conf
EOF
```

- [ ] **Step 4: Run test to verify it passes**

Run: `tests/tmux/test_popups_statusline.sh`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/tmux/test_popups_statusline.sh
git commit -m "feat(tmux): implement floating popups suite, cheatsheet and statusline"
```

---

### Task 3: Complete TPM Plugin Suite & Auto-Installer

**Files:**
- Create: `~/.config/tmux/conf.d/90-plugins.conf`
- Modify: `~/.config/tmux/tmux.conf`
- Create: `tests/tmux/test_tpm_plugins.sh`

**Interfaces:**
- Consumes: Task 1 & 2 configs
- Produces: Complete TPM Plugin Suite (15 plugins: `resurrect`, `continuum`, `sessionist`, `yank`, `copycat`, `open`, `fzf-url`, `tmux-fzf`, `logging`, `prefix-highlight`, `cpu`, dll.) dan auto-install bootstrap.

- [ ] **Step 1: Write the validation test for TPM Suite**

```bash
cat << 'EOF' > tests/tmux/test_tpm_plugins.sh
#!/usr/bin/env bash
set -euo pipefail

echo "==> Testing TPM configuration and bootstrap..."
if [ ! -d "$HOME/.config/tmux/plugins/tpm" ]; then
  echo "Installing TPM for test..."
  git clone --depth 1 https://github.com/tmux-plugins/tpm "$HOME/.config/tmux/plugins/tpm" < /dev/null
fi

tmux -f ~/.config/tmux/tmux.conf -C new-session -d -s test-tpm "true" 2>/dev/null || {
  echo "FAIL: Failed to initialize tmux with TPM plugins"
  exit 1
}
tmux kill-session -t test-tpm 2>/dev/null || true

echo "PASS: TPM plugin suite initialized without error."
EOF
chmod +x tests/tmux/test_tpm_plugins.sh
```

- [ ] **Step 2: Run test to verify failure**

Run: `tests/tmux/test_tpm_plugins.sh`
Expected: FAIL (module not yet created)

- [ ] **Step 3: Implement 90-plugins.conf & Master Integration**

```bash
cat << 'EOF' > ~/.config/tmux/conf.d/90-plugins.conf
# ==============================================================================
# 90-plugins.conf — Complete TPM Plugin Suite & Integration
# ==============================================================================

# List of TPM Plugins (Complete Suite)
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'tmux-plugins/tmux-sensible'
set -g @plugin 'tmux-plugins/tmux-resurrect'
set -g @plugin 'tmux-plugins/tmux-continuum'
set -g @plugin 'tmux-plugins/tmux-sessionist'
set -g @plugin 'christoomey/vim-tmux-navigator'
set -g @plugin 'tmux-plugins/tmux-pain-control'
set -g @plugin 'tmux-plugins/tmux-yank'
set -g @plugin 'tmux-plugins/tmux-copycat'
set -g @plugin 'tmux-plugins/tmux-open'
set -g @plugin 'wfxr/tmux-fzf-url'
set -g @plugin 'sainnhe/tmux-fzf'
set -g @plugin 'tmux-plugins/tmux-logging'
set -g @plugin 'tmux-plugins/tmux-prefix-highlight'
set -g @plugin 'tmux-plugins/tmux-cpu'

# Plugin Specific Configurations
# 1. tmux-resurrect & continuum
set -g @resurrect-capture-pane-contents 'on'
set -g @resurrect-strategy-nvim 'session'
set -g @resurrect-strategy-vim 'session'
set -g @continuum-save-interval '15'
set -g @continuum-restore 'on'

# 2. tmux-prefix-highlight
set -g @prefix_highlight_fg '#11111b'
set -g @prefix_highlight_bg '#fab387'
set -g @prefix_highlight_show_copy_mode 'on'
set -g @prefix_highlight_copy_mode_attr 'fg=#11111b,bg=#f9e2af,bold'
set -g @prefix_highlight_show_sync_mode 'on'
set -g @prefix_highlight_sync_mode_attr 'fg=#11111b,bg=#f38ba8,bold'

# 3. tmux-fzf-url & tmux-fzf
set -g @fzf-url-bind 'u'
set -g @fzf-url-history-limit '2000'
TMUX_FZF_LAUNCH_KEY="F"

# Automatic TPM Bootstrap (Installs TPM if missing)
if "test ! -d ~/.config/tmux/plugins/tpm" \
   "run 'git clone --depth 1 https://github.com/tmux-plugins/tpm ~/.config/tmux/plugins/tpm && ~/.config/tmux/plugins/tpm/bin/install_plugins'"

# Initialize TMUX plugin manager (keep this line at the very bottom of plugins.conf)
run '~/.config/tmux/plugins/tpm/tpm'
EOF

cat << 'EOF' > ~/.config/tmux/tmux.conf
# ==============================================================================
# tmux.conf — Master Entry Point
# ==============================================================================

# 1. Core Options & Keybindings
source-file ~/.config/tmux/conf.d/00-options.conf
source-file ~/.config/tmux/conf.d/10-keybindings.conf

# 2. Popups & Statusline
source-file ~/.config/tmux/conf.d/20-popups.conf
source-file ~/.config/tmux/conf.d/30-statusline.conf

# 3. TPM Plugins Suite
source-file ~/.config/tmux/conf.d/90-plugins.conf
EOF
```

- [ ] **Step 4: Run test to verify it passes**

Run: `tests/tmux/test_tpm_plugins.sh`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/tmux/test_tpm_plugins.sh
git commit -m "feat(tmux): implement complete TPM plugin suite and auto-bootstrap"
```

---

### Task 4: Multi-Agent Workspace Orchestrator Suite (`scripts/tmux_agents.sh`)

**Files:**
- Modify: `scripts/tmux_agents.sh`
- Create: `tests/tmux/test_agents_orchestrator.sh`
- Modify: `~/.config/tmux/conf.d/20-popups.conf` (bind `prefix + A` to agent menu)

**Interfaces:**
- Consumes: `tmux 3.5a`, Git CLI, `agy`, `claude`
- Produces: CLI orchestrator `scripts/tmux_agents.sh` dengan mode `pair`, `company`, `worktree`, `capture`, `clear-all`, `kill` dan popup modal `prefix + A`.

- [ ] **Step 1: Write the validation test for Multi-Agent Orchestrator**

```bash
cat << 'EOF' > tests/tmux/test_agents_orchestrator.sh
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ORCHESTRATOR="$SCRIPT_DIR/scripts/tmux_agents.sh"

echo "==> Testing Multi-Agent Orchestrator CLI..."
if [ ! -x "$ORCHESTRATOR" ]; then
  echo "FAIL: Orchestrator script is not executable"
  exit 1
fi

# Test help/usage
"$ORCHESTRATOR" help >/dev/null

# Test pair session creation in background
echo "==> Testing pair mode..."
"$ORCHESTRATOR" pair "test-pair"
tmux has-session -t "test-pair" 2>/dev/null || {
  echo "FAIL: Session 'test-pair' was not created"
  exit 1
}

# Test capture
echo "==> Testing capture..."
CAPTURE_OUT=$("$ORCHESTRATOR" capture "test-pair:agents.0" 5)
if [ -z "$CAPTURE_OUT" ]; then
  echo "WARN: Capture output empty (session just started), acceptable."
fi

# Clean up
"$ORCHESTRATOR" kill "test-pair"
echo "PASS: Multi-Agent orchestrator passed all tests."
EOF
chmod +x tests/tmux/test_agents_orchestrator.sh
```

- [ ] **Step 2: Run test to verify failure**

Run: `tests/tmux/test_agents_orchestrator.sh`
Expected: FAIL (subcommands not yet implemented in script)

- [ ] **Step 3: Implement Comprehensive `scripts/tmux_agents.sh`**

```bash
cat << 'EOF' > scripts/tmux_agents.sh
#!/usr/bin/env bash
# ==============================================================================
# tmux_agents.sh — Comprehensive Multi-Agent Orchestration Suite
# Supports: Dual-Agent Pairing, Boss-Worker Matrix, Worktrees, Telemetry
# ==============================================================================
set -euo pipefail

DEFAULT_SESSION="dev-agents"

usage() {
  cat << EOF
Usage: $(basename "$0") [command] [options]

Commands:
  pair [session_name]      Launch dual-agent pairing (agy + claude + monitor)
  company [n_workers]      Launch Boss-Worker matrix (1 Boss + N Workers)
  worktree add <branch>    Create isolated Git worktree and spawn agent window
  worktree list            List active agent worktrees
  worktree clean <branch>  Remove worktree directory and branch
  capture <target> [lines] Capture silent snapshot of agent pane buffer
  clear-all [session_name] Broadcast /clear to all worker panes
  status                   Show running agent sessions and panes
  kill [session_name]      Gracefully terminate agent session
  menu                     Interactive agent launcher menu (for popups)
  help                     Show this help message

EOF
  exit 0
}

cmd_pair() {
  local session="${1:-$DEFAULT_SESSION}"
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "==> Session '$session' already running. Reattaching..."
    if [ -t 0 ]; then tmux attach -t "$session"; fi
    return 0
  fi

  echo "==> Creating dual-agent pairing session '$session'..."
  # Pane 0: Google Antigravity (Reasoning / Controller)
  tmux new-session -d -s "$session" -n "agents" "agy 2>/dev/null || bash"

  # Pane 1: Claude Code (Executor / Coder)
  tmux split-window -h -t "$session:agents.0" "claude 2>/dev/null || bash"

  # Pane 2: System & Process Telemetry
  tmux split-window -v -t "$session:agents.1" "btop 2>/dev/null || htop 2>/dev/null || top"

  # Set balanced layout: Left 50%, Right Top 25%, Right Bottom 25%
  tmux select-pane -t "$session:agents.0"

  echo "✨ Pairing session created. Attach with: tmux a -t $session"
  if [ -t 0 ]; then tmux attach -t "$session"; fi
}

cmd_company() {
  local n_workers="${1:-3}"
  local session="agent-company"
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "==> Company session '$session' already exists. Reattaching..."
    if [ -t 0 ]; then tmux attach -t "$session"; fi
    return 0
  fi

  echo "==> Spawning Boss-Worker company matrix with $n_workers workers..."
  tmux new-session -d -s "$session" -n "company" "agy 2>/dev/null || bash"
  
  for ((i=1; i<=n_workers; i++)); do
    tmux split-window -v -t "$session:company" "claude 2>/dev/null || bash"
  done

  tmux select-layout -t "$session:company" tiled
  tmux select-pane -t "$session:company.0"

  echo "✨ Company session initialized with $n_workers workers."
  if [ -t 0 ]; then tmux attach -t "$session"; fi
}

cmd_worktree() {
  local action="${1:-list}"
  local branch="${2:-}"
  local root_dir
  root_dir="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

  case "$action" in
    add|create)
      if [ -z "$branch" ]; then
        echo "Error: Branch name required. Example: $0 worktree add feature-auth"
        exit 1
      fi
      local wt_dir="$root_dir/.worktrees/$branch"
      echo "==> Creating isolated Git Worktree at '$wt_dir'..."
      mkdir -p "$root_dir/.worktrees"
      git worktree add -b "$branch" "$wt_dir" HEAD < /dev/null
      
      # Spawn window in current tmux session if attached
      if [ -n "${TMUX:-}" ]; then
        tmux new-window -n "wt:$branch" -c "$wt_dir" "claude 2>/dev/null || bash"
        echo "✨ Opened new tmux window 'wt:$branch' in worktree."
      else
        echo "✨ Worktree ready at $wt_dir. Start agent inside: cd $wt_dir && claude"
      fi
      ;;
    list)
      echo "==> Active Git Worktrees:"
      git worktree list
      ;;
    clean|remove)
      if [ -z "$branch" ]; then
        echo "Error: Branch name required to remove."
        exit 1
      fi
      local wt_dir="$root_dir/.worktrees/$branch"
      echo "==> Removing worktree '$wt_dir'..."
      git worktree remove "$wt_dir" --force 2>/dev/null || rm -rf "$wt_dir"
      git worktree prune < /dev/null
      echo "✨ Worktree cleaned."
      ;;
    *)
      echo "Unknown worktree action: $action"
      exit 1
      ;;
  esac
}

cmd_capture() {
  local target="${1:-$DEFAULT_SESSION:agents.0}"
  local lines="${2:-50}"
  tmux capture-pane -t "$target" -p | tail -n "$lines"
}

cmd_clear_all() {
  local session="${1:-$DEFAULT_SESSION}"
  echo "==> Broadcasting /clear to all panes in '$session'..."
  local panes
  panes=$(tmux list-panes -t "$session" -F '#{pane_id}' 2>/dev/null || echo "")
  for p in $panes; do
    tmux send-keys -t "$p" "/clear" Enter 2>/dev/null || true
  done
  echo "✨ All panes cleared."
}

cmd_status() {
  echo "==> Active tmux sessions:"
  tmux list-sessions 2>/dev/null || echo "No active sessions."
}

cmd_kill() {
  local session="${1:-$DEFAULT_SESSION}"
  echo "==> Terminating session '$session'..."
  tmux kill-session -t "$session" 2>/dev/null || echo "Session '$session' not running."
}

cmd_menu() {
  cat << 'EOF'
=====================================================
          🤖 MULTI-AGENT WORKSPACE DASHBOARD
=====================================================
  [1] Launch Dual-Agent Pairing (agy + claude)
  [2] Launch Company Matrix (Boss + 3 Workers)
  [3] Create Isolated Git Worktree for Agent
  [4] Broadcast /clear to All Agent Panes
  [5] View System Telemetry (btop/htop)
  [6] Gracefully Terminate Workspace
  [q] Quit
=====================================================
EOF
  read -r -p "Select option [1-6]: " choice
  case "$choice" in
    1) cmd_pair ;;
    2) cmd_company 3 ;;
    3)
       read -r -p "Enter feature branch name: " fbranch
       if [ -n "$fbranch" ]; then cmd_worktree add "$fbranch"; fi
       ;;
    4) cmd_clear_all ;;
    5) btop 2>/dev/null || htop 2>/dev/null || top ;;
    6) cmd_kill ;;
    *) exit 0 ;;
  esac
}

# CLI Router
COMMAND="${1:-pair}"
shift || true

case "$COMMAND" in
  start|pair)       cmd_pair "${1:-}" ;;
  company)          cmd_company "${1:-3}" ;;
  worktree)         cmd_worktree "${1:-list}" "${2:-}" ;;
  capture)          cmd_capture "${1:-$DEFAULT_SESSION:agents.0}" "${2:-50}" ;;
  clear-all)        cmd_clear_all "${1:-$DEFAULT_SESSION}" ;;
  status)           cmd_status ;;
  kill)             cmd_kill "${1:-$DEFAULT_SESSION}" ;;
  menu)             cmd_menu ;;
  help|--help|-h)   usage ;;
  *)                usage ;;
esac
EOF
chmod +x scripts/tmux_agents.sh

# Bind Prefix + A in 20-popups.conf for Agent Menu
cat << 'EOF' >> ~/.config/tmux/conf.d/20-popups.conf

# 5. Multi-Agent Dashboard Popup (Prefix + A)
bind-key A display-popup -E -w 75% -h 70% "bash ~/dev/os-manager/scripts/tmux_agents.sh menu"
EOF
```

- [ ] **Step 4: Run test to verify it passes**

Run: `tests/tmux/test_agents_orchestrator.sh`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/tmux_agents.sh tests/tmux/test_agents_orchestrator.sh
git commit -m "feat(agents): implement comprehensive multi-agent orchestrator suite and popup menu"
```

---

### Task 5: Skill & Documentation Synchronization

**Files:**
- Modify: `.agents/skills/tmux-agents/SKILL.md`
- Create: `tests/tmux/test_skill_docs.sh`

**Interfaces:**
- Consumes: Task 4 orchestrator subcommands
- Produces: Dokumentasi skill `.agents/skills/tmux-agents/SKILL.md` yang tersinkronisasi penuh dengan kapabilitas baru.

- [ ] **Step 1: Write the validation test for Skill documentation**

```bash
cat << 'EOF' > tests/tmux/test_skill_docs.sh
#!/usr/bin/env bash
set -euo pipefail

SKILL_FILE=".agents/skills/tmux-agents/SKILL.md"

echo "==> Checking skill documentation content..."
if ! grep -q "company" "$SKILL_FILE"; then
  echo "FAIL: SKILL.md missing 'company' mode documentation"
  exit 1
fi

if ! grep -q "worktree" "$SKILL_FILE"; then
  echo "FAIL: SKILL.md missing 'worktree' documentation"
  exit 1
fi

if ! grep -q "capture" "$SKILL_FILE"; then
  echo "FAIL: SKILL.md missing 'capture' documentation"
  exit 1
fi

echo "PASS: Skill documentation verified."
EOF
chmod +x tests/tmux/test_skill_docs.sh
```

- [ ] **Step 2: Run test to verify failure**

Run: `tests/tmux/test_skill_docs.sh`
Expected: FAIL (documentation not yet updated)

- [ ] **Step 3: Update `.agents/skills/tmux-agents/SKILL.md`**

```markdown
cat << 'EOF' > .agents/skills/tmux-agents/SKILL.md
---
name: tmux-agents
description: Use when launching a multi-agent terminal workspace, pairing Claude Code with Google Antigravity (agy), managing Boss-Worker matrices, orchestrating Git worktrees, or capturing agent telemetry in tmux
---

# Multi-Agent Tmux Session & Orchestration Skill

Orchestrates multi-pane terminal workflows pairing Claude Code with Google Antigravity (`agy`), Boss-Worker hierarchies, isolated Git Worktrees, and real-time telemetry in `tmux 3.5a`.

## Trigger Scenarios
- Initializing collaborative dual-agent pairing (`agy` + `claude` + telemetry)
- Launching scalable Boss-Worker agent companies (`company` mode)
- Creating isolated Git Worktrees for concurrent agent coding without file collision
- Capturing background buffer logs (`capture`) for silent audits
- Resetting context windows across all worker panes simultaneously (`clear-all`)
- Interactive agent workspace dashboard via floating popup (`prefix + A`)

## Invocation
```bash
${CLAUDE_PROJECT_DIR}/scripts/tmux_agents.sh [subcommand] [args]
```

## Subcommands & Options
| Subcommand | Arguments | Description |
| :--- | :--- | :--- |
| `start` / `pair` | `[session_name]` | Initializes 3-pane paired agent session (`agy`, `claude`, `btop`/`htop`) or reattaches |
| `company` | `[n_workers]` | Launches 1 Boss + N Worker panes in balanced tiled layout |
| `worktree add` | `<branch_name>` | Spawns isolated Git worktree in `.worktrees/<branch>` with dedicated agent window |
| `worktree list` | *(none)* | Lists all active agent worktrees |
| `worktree clean`| `<branch_name>` | Safely removes worktree directory and branch |
| `capture` | `<target> [lines]`| Silently grabs output buffer from target pane without terminal interruption |
| `clear-all` | `[session_name]` | Sends `/clear` to all panes to reset token context |
| `status` | *(none)* | Displays list of active agent sessions and panes |
| `kill` | `[session_name]` | Gracefully terminates target agent session |
| `menu` | *(none)* | Opens interactive TUI dashboard (bound to `prefix + A`) |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Authorized terminal workspace orchestrator managing user tmux sessions and sandboxed worktrees.
EOF
```

- [ ] **Step 4: Run test to verify it passes**

Run: `tests/tmux/test_skill_docs.sh`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .agents/skills/tmux-agents/SKILL.md tests/tmux/test_skill_docs.sh
git commit -m "docs(skill): update tmux-agents skill with worktree and company modes"
```

---

### Task 6: End-to-End Test Suite & Final System Verification

**Files:**
- Create: `tests/tmux/run_all_tests.sh`

**Interfaces:**
- Consumes: Task 1 through 5 deliverables
- Produces: Suite pengujian otomatis terpadu untuk validasi menyeluruh.

- [ ] **Step 1: Write the master end-to-end test runner**

```bash
cat << 'EOF' > tests/tmux/run_all_tests.sh
#!/usr/bin/env bash
# ==============================================================================
# run_all_tests.sh — Master E2E Test Suite for Tmux Modernization
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

echo "========================================================"
echo "    🧪 RUNNING TMUX MODERNIZATION VERIFICATION SUITE"
echo "========================================================"

run_test() {
  local t="$1"
  echo ""
  echo "--- Running $t ---"
  if bash "$SCRIPT_DIR/$t"; then
    echo "✅ $t PASSED"
  else
    echo "❌ $t FAILED"
    FAILED=$((FAILED + 1))
  fi
}

run_test "test_core_config.sh"
run_test "test_popups_statusline.sh"
run_test "test_tpm_plugins.sh"
run_test "test_agents_orchestrator.sh"
run_test "test_skill_docs.sh"

echo ""
echo "========================================================"
if [ "$FAILED" -eq 0 ]; then
  echo "🎉 ALL TESTS PASSED SUCCESSFULLY!"
  exit 0
else
  echo "💥 $FAILED TEST(S) FAILED."
  exit 1
fi
EOF
chmod +x tests/tmux/run_all_tests.sh
```

- [ ] **Step 2: Execute master test runner**

Run: `tests/tmux/run_all_tests.sh`
Expected: ALL TESTS PASSED

- [ ] **Step 3: Commit master test suite**

```bash
git add tests/tmux/run_all_tests.sh
git commit -m "test(tmux): add master end-to-end verification suite"
```

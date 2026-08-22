#!/usr/bin/env bash
# scripts/setup_terminal_env.sh - Starship Prompt, Modern CLI Tools, FZF Previews, Bash & Tmux
set -euo pipefail

STARSHIP_CONFIG_PATH="${HOME}/.config/starship.toml"
TMUX_CONFIG_PATH="${HOME}/.tmux.conf"
BASHRC_PATH="${HOME}/.bashrc"
HOOK_MARKER="# --- os-manager Terminal Power-Up Hooks ---"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

setup_starship() {
    log_info "Configuring Starship prompt template at ${STARSHIP_CONFIG_PATH}..."
    mkdir -p "$(dirname "${STARSHIP_CONFIG_PATH}")"
    cat <<'EOF' > "${STARSHIP_CONFIG_PATH}"
# Starship Prompt Configuration for os-manager
add_newline = false

format = """
$directory\
$git_branch\
$git_status\
$python\
$nodejs\
$rust\
$docker_context\
$cmd_duration\
$line_break\
$character"""

[directory]
truncation_length = 3
truncate_to_repo = true
style = "bold cyan"

[git_branch]
style = "bold purple"
symbol = " "

[git_status]
style = "bold red"
ahead = "⇡${count}"
behind = "⇣${count}"
diverged = "⇕⇡${ahead_count}⇣${behind_count}"

[cmd_duration]
min_time = 2_000
style = "bold yellow"

[character]
success_symbol = "[❯](bold green)"
error_symbol = "[❯](bold red)"
EOF
    log_pass "Starship prompt configuration deployed."
}

setup_tmux() {
    log_info "Configuring Tmux developer starter profile at ${TMUX_CONFIG_PATH}..."
    cat <<'EOF' > "${TMUX_CONFIG_PATH}"
# Tmux Developer Profile for os-manager
set -g mouse on
set -g default-terminal "xterm-256color"
set -ga terminal-overrides ",*256col*:Tc"

bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"

setw -g mode-keys vi
set -g status-style bg=black,fg=white
set -g status-interval 5
set -g status-left "#[fg=green][#S] "
set -g status-right "#[fg=cyan]%H:%M #[fg=yellow]%d-%b-%y"
EOF
    log_pass "Tmux developer configuration deployed."
}

inject_bashrc() {
    log_info "Injecting terminal power-up hooks into ${BASHRC_PATH}..."
    touch "${BASHRC_PATH}"

    if grep -qF "${HOOK_MARKER}" "${BASHRC_PATH}"; then
        log_info "Bash hooks already present in ${BASHRC_PATH}. Skipping duplicate injection."
        return 0
    fi

    cat <<'EOF' >> "${BASHRC_PATH}"

# --- os-manager Terminal Power-Up Hooks ---
export HISTSIZE=100000
export HISTFILESIZE=200000
export HISTCONTROL=ignoreboth:erasedups
export HISTTIMEFORMAT="%F %T "

shopt -s histappend 2>/dev/null || true
shopt -s checkwinsize 2>/dev/null || true
shopt -s globstar 2>/dev/null || true
shopt -s cdspell 2>/dev/null || true

# Modern CLI Aliases
alias ls="eza --icons" 2>/dev/null || true
alias ll="eza -lh --icons --git" 2>/dev/null || true
alias la="eza -lah --icons --git" 2>/dev/null || true
alias lt="eza --tree --level=2 --icons" 2>/dev/null || true
alias cat="bat --paging=never" 2>/dev/null || true
alias grep="rg" 2>/dev/null || true
alias find="fd" 2>/dev/null || true
alias df="duf" 2>/dev/null || true
alias top="btop" 2>/dev/null || true
alias cd="z" 2>/dev/null || true

# Git Power Aliases
alias gst="git status"
alias gdiff="git diff"
alias glog="git log --oneline --graph --decorate"
alias gco="git checkout"
alias gbr="git branch"
alias gadd="git add"
alias gcm="git commit -m"

# FZF Live Previews
export FZF_DEFAULT_COMMAND='fd --type f --strip-cwd-prefix --hidden --exclude .git' 2>/dev/null || true
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND" 2>/dev/null || true
export FZF_ALT_C_COMMAND='fd --type d --strip-cwd-prefix --hidden --exclude .git' 2>/dev/null || true
export FZF_CTRL_T_OPTS="--preview 'bat --style=numbers --color=always --line-range :500 {}' --preview-window=right:60%:wrap" 2>/dev/null || true
export FZF_ALT_C_OPTS="--preview 'eza --tree --level=2 --color=always {}' --preview-window=right:50%" 2>/dev/null || true
export FZF_CTRL_R_OPTS="--preview 'echo {}' --preview-window=down:3:wrap --sort" 2>/dev/null || true

# Starship & Zoxide Init
if command -v starship >/dev/null 2>&1; then
    eval "$(starship init bash)"
fi
if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init bash)"
fi
# --- End os-manager Terminal Power-Up Hooks ---
EOF
    log_pass "Bashrc hooks injected successfully."
}

audit_terminal() {
    log_info "Auditing terminal developer environment..."
    local ok=0
    local warn=0

    for cmd in starship tmux fzf bat eza rg fd btop duf zoxide; do
        if command -v "$cmd" >/dev/null 2>&1; then
            log_pass "CLI tool '$cmd' is available ($(command -v "$cmd"))."
            ok=$((ok + 1))
        else
            log_warn "CLI tool '$cmd' not found in PATH."
            warn=$((warn + 1))
        fi
    done

    if [[ -f "${STARSHIP_CONFIG_PATH}" ]]; then
        log_pass "Starship config present at ${STARSHIP_CONFIG_PATH}."
        ok=$((ok + 1))
    else
        log_warn "Starship config missing at ${STARSHIP_CONFIG_PATH}."
        warn=$((warn + 1))
    fi

    if [[ -f "${TMUX_CONFIG_PATH}" ]]; then
        log_pass "Tmux config present at ${TMUX_CONFIG_PATH}."
        ok=$((ok + 1))
    else
        log_warn "Tmux config missing at ${TMUX_CONFIG_PATH}."
        warn=$((warn + 1))
    fi

    if grep -qF "${HOOK_MARKER}" "${BASHRC_PATH}" 2>/dev/null; then
        log_pass "Bashrc hooks present in ${BASHRC_PATH}."
        ok=$((ok + 1))
    else
        log_warn "Bashrc hooks not found in ${BASHRC_PATH}."
        warn=$((warn + 1))
    fi

    log_info "Audit complete: ${ok} passed, ${warn} warnings."
}

main() {
    local action="${1:---setup}"
    case "${action}" in
        --setup)
            setup_starship
            setup_tmux
            inject_bashrc
            ;;
        --audit)
            audit_terminal
            ;;
        --starship)
            setup_starship
            ;;
        --tmux)
            setup_tmux
            ;;
        --bashrc)
            inject_bashrc
            ;;
        *)
            echo "Usage: $(basename "$0") [--setup|--audit|--starship|--tmux|--bashrc]"
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

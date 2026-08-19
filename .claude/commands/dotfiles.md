# /dotfiles: Dotfiles State Sync & Diff Command

Inspects, backs up, and safely restores user configuration dotfiles (`.bashrc`, `.tmux.conf`, `.gitconfig`).

## Invocation
```bash
${CLAUDE_PROJECT_DIR}/scripts/dotfiles_sync.sh "$@"
```

## Description
Provides non-destructive dotfile management and drift detection:
- `backup`: Copies current dotfiles from `$HOME` into repository backup storage (`backups/dotfiles/`)
- `diff`: Non-destructive unified diff comparison between repository backups and active `$HOME` dotfiles
- `restore`: Interactively restores repository backup dotfiles to `$HOME` (`cp -iv`)

## Usage
```bash
/dotfiles backup
/dotfiles diff
/dotfiles restore
```

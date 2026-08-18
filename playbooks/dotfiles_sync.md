# Playbook: Dotfiles Synchronization and Drift Management

Operational runbook for managing configuration drift, backing up dotfiles, and safely restoring user settings.

## Overview

`os-manager` tracks critical user environment configurations:
- `~/.bashrc` (Shell environment and aliases)
- `~/.tmux.conf` (Terminal multiplexer layout)
- `~/.gitconfig` (Git identity and preferences)

Backups reside in `backups/dotfiles/` within the repository.

---

## Standard Workflows

### 1. Pre-Modification Backup
Run backup before modifying active shell or tmux configurations:

```bash
/home/rizz/dev/os-manager/scripts/dotfiles_sync.sh backup
```

Verify that files are copied to `backups/dotfiles/`:
```bash
git status backups/dotfiles/
```

### 2. Inspecting Configuration Drift
Check differences between active home directory dotfiles and repository copies:

```bash
/home/rizz/dev/os-manager/scripts/dotfiles_sync.sh diff
```

### 3. Restoring Configurations After Environment Reset
Overwriting active dotfiles requires explicit confirmation:

```bash
/home/rizz/dev/os-manager/scripts/dotfiles_sync.sh restore
```

Review the prompted confirmation, confirm with `y`, and reload shell configuration:
```bash
source ~/.bashrc
```

---

## Troubleshooting

### Unintended Overwrites
If you mistakenly overwrite a dotfile, recover previous versions using git history:
```bash
git checkout HEAD -- backups/dotfiles/.bashrc
cp backups/dotfiles/.bashrc ~/.bashrc
```

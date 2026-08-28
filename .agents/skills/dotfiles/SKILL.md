---
name: dotfiles
description: Use when backing up, comparing, or restoring user shell configuration dotfiles (~/.bashrc, ~/.tmux.conf, ~/.gitconfig) against versioned backups
---

# Dotfiles State Synchronization Skill

Provides state protection, drift detection, and controlled restoration for critical shell configuration dotfiles between the active user home directory (`$HOME`) and the repository backup store (`backups/dotfiles/`).

## Trigger Scenarios
- Backing up active dotfiles before testing configuration modifications
- Inspecting configuration drift between active `$HOME` dotfiles and repository baselines
- Restoring version-controlled dotfile configurations following an environment reset or migration

## Invocation
```bash
${PROJECT_DIR:-.}/scripts/dotfiles_sync.sh <subcommand>
```

## Tracked Files
The skill manages the following configuration files:

| Active Path | Repository Backup Path | Description |
| :--- | :--- | :--- |
| `~/.bashrc` | `backups/dotfiles/.bashrc` | User interactive bash shell configuration and aliases |
| `~/.tmux.conf` | `backups/dotfiles/.tmux.conf` | Tmux terminal multiplexer session configuration |
| `~/.gitconfig` | `backups/dotfiles/.gitconfig` | User Git global configuration and credentials helper |

## Subcommands
| Subcommand | Description | Safety Gate |
| :--- | :--- | :--- |
| `backup` | Copies active dotfiles from `$HOME` into `backups/dotfiles/` | Autonomous (Tier 1) |
| `diff` | Performs non-destructive unified diff between repository backups and `$HOME` | Autonomous Read-Only (Tier 0) |
| `restore` | Copies repository backups back into `$HOME` (`cp -iv`) | **Explicit confirmation required** before overwriting `$HOME` configurations |

## Safety Classification & Confirmation Protocol
- **Tier 0 (Diff)** / **Tier 1 (Backup)**: Safe, low-risk state inspections and workspace-contained backups.
- **Restore Confirmation Gate**: Restoring dotfiles overwrites active shell configuration in `$HOME`. Always run `${PROJECT_DIR:-.}/scripts/dotfiles_sync.sh diff` first, present the diff to the user, and obtain explicit confirmation before running `restore`.

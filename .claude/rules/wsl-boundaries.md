# WSL2 Filesystem Boundaries & Storage Invariants

Storage discipline and cross-OS interoperability rules for the Debian 13 WSL2 environment on Windows 11.

## 1. Native EXT4 Performance Domain (`${HOME}/`)

The native Linux ext4 partition is the designated primary domain for all development workloads.

- **High-Throughput Workloads**:
  - Keep all Git repositories, Node.js packages (`node_modules`), Python virtual environments (`.venv`), Cargo target directories, build artifacts, and package stores on `${HOME}/`.
  - Avoid initializing developer workspaces across 9P filesystem mounts (`/mnt/c/`, `/mnt/d/`) to prevent severe I/O virtualization latency, inotify event loss, and POSIX permission churn.
- **File System Hygiene**:
  - Maintain Unix LF line endings across all workspace files.
  - Preserve executable permissions (`chmod +x`) on all shell scripts.

## 2. Windows NTFS Host Mounts (`/mnt/c/`, `/mnt/d/`)

Interactions with Windows filesystem mounts are restricted to specialized operational workflows.

- **Windows C: Drive (`/mnt/c/`) Read-Only Host Inspection**:
  - Inspect Windows host paths in a strictly read-only manner.
  - Never write, edit, or delete files inside `/mnt/c/Windows`, `Program Files`, `Program Files (x86)`, or `AppData`.
  - Avoid creating developer projects or heavy file trees under `/mnt/c/Users/`.
- **Windows D: Drive (`/mnt/d/`) Disaster Recovery Target**:
  - Use `/mnt/d/wsl_backup/` exclusively as the destination for compressed point-in-time distro snapshots (`.tar.gz`).
  - Do not use `/mnt/d/` for live repository execution or daily development tasks.

## 3. Host Binary Interoperability (`.exe`)

- **Windows Binary Invocations**:
  - Invoke Windows CLI binaries (`cmd.exe`, `powershell.exe`, `explorer.exe`) only when non-interactive and explicitly necessary for host diagnostics.
  - Never run destructive lifecycle commands via host binaries (e.g., `wsl.exe --unregister`, `wsl.exe --shutdown`).

# WSL2 Filesystem Boundaries & Storage Invariants

1. **Native ext4 Performance Domain (`/home/rizz/`)**:
   - All Git repositories, Node `node_modules`, Python virtualenvs (`.venv`), temporary build artifacts, and package stores MUST reside on the native ext4 Linux partition (`/home/rizz/`).
   - Never initialize high I/O developer workspaces on Windows mounts (`/mnt/c/`, `/mnt/d/`) due to 9P file system virtualization latency.

2. **NTFS Mount Access Rules (`/mnt/c/`, `/mnt/d/`)**:
   - `/mnt/d/`: Designated solely for compressed WSL point-in-time snapshots and offsite archival.
   - `/mnt/c/`: Read-only host inspection. Direct writes or edits to `/mnt/c/Windows`, `Program Files`, or `AppData` are strictly forbidden.

# SESSION HANDOFF: Debian Native Migration & Admin Execution

Dokumen serah terima (*handoff*) untuk sesi Antigravity di Terminal **Administrator** Windows (`D:\dev\os-manager` atau elevated WSL `/home/rizz/dev/os-manager`).

---

## 1. Ringkasan Keputusan Hasil Interview (/grill-me)
* **Distro Target:** **Debian GNU/Linux (GNOME Live with non-free firmware)**.
* **Tampilan Desktop:** **GNOME (Wayland)**.
* **Root Filesystem:** **ext4** (dengan dynamic Swapfile).
* **Partisi Data Drive D: (244 GB NTFS):** **100% UNTOUCHED (Dilarang format)**, di-mount ke `/mnt/data`.
* **Migrasi Environment WSL:** Menjalankan ekspor konfigurasi `~/*` (dotfiles, .ssh, git config, dev) ke `D:\wsl_backup\wsl_home_backup.tar.gz` sebelum partisi Windows dihapus.

---

## 2. Status Hardware & Disk Fisik (Disk 0 - NVMe 512 GB)
* **Partisi 1:** EFI System Partition (100 MB, FAT32) $\rightarrow$ Mount ke `/boot/efi`
* **Partisi 2:** Windows C: (226 GB, NTFS) $\rightarrow$ Di-shrink untuk installer (8 GB FAT32) & Debian Root (~112 GB)
* **Partisi 3:** Windows Recovery (5.7 GB)
* **Partisi 4:** Data D: (244 GB, NTFS, 201 GB used) $\rightarrow$ Diberi label `DATA_STORE` di DiskGenius

---

## 3. Tugas Prioritas yang Harus Dieksekusi di Terminal Admin
1. **Verifikasi Hak Admin:** Uji hak akses administratif.
2. **Cek BitLocker:** Jalankan `manage-bde.exe -status` untuk memastikan proteksi C: dan D: adalah OFF (Decrypted).
3. **Nonaktifkan Fast Startup:** Jalankan `powercfg.exe /h off`.
4. **Perbaiki File System Drive D:** Jalankan `chkdsk.exe D: /f /r` untuk menyelesaikan status *repair needed*.
5. **Ekspor Data & Dotfiles WSL:**
   ```bash
   mkdir -p /mnt/d/wsl_backup
   tar -czvf /mnt/d/wsl_backup/wsl_home_backup.tar.gz -C /home/rizz .bashrc .profile .ssh .gitconfig .agents dev
   ```
6. **Perbarui Blueprint:** Perbarui `docs/LINUX_MIGRATION_BLUEPRINT.md` dengan konfirmasi hasil eksekusi admin.

---

## 4. Referensi Dokumen
* Blueprint Lengkap: [docs/LINUX_MIGRATION_BLUEPRINT.md](file:///home/rizz/dev/os-manager/docs/LINUX_MIGRATION_BLUEPRINT.md)

# AGENTS.md

Panduan operasional dan standar eksekusi agen AI (Antigravity `agy`, Claude Code, dan subagent) di lingkungan `os-manager` (Debian WSL2 & Bare-Metal Linux).

---

## 1. Aturan Keamanan Mutlak (Zero-Data-Loss Guardrails)

* **Partisi Data (Drive D: / `DATA_STORE`):**
  * DILARANG menjalankan perintah `format`, `mkfs`, `wipefs`, `fdisk d`, `rm -rf` skala luas, atau penghapusan partisi pada `/dev/nvme0n1p4` (Drive D:).
  * Data di Drive D: (~201 GB) harus selalu diperlakukan sebagai **in-place persistent storage**.
* **Operasi Disk Destruktif:**
  * Wajib meminta konfirmasi eksplisit sebelum menjalankan modifikasi partisi fisik yang tidak dapat dibatalkan.

---

## 2. Standar Interoperabilitas Windows dari WSL (Windows Interop Rules)

*Berdasarkan audit evaluasi sesi `4f7b4fa7-e919-4058-ade7-9d4da54f4391`*:

1. **Wajib Menutup `stdin` pada Eksekusi Biner Windows:**
   * Di dalam WSL, biner Windows (`powershell.exe`, `cmd.exe`, `manage-bde.exe`, `chkdsk.exe`, `fsutil.exe`) yang dijalankan tanpa input terminal interaktif **akan hang/beku** menunggu input.
   * **Aturan Baku:** Selalu tambahkan `< /dev/null` dan flag non-interaktif:
     ```bash
     # Benar (PowerShell):
     /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -NonInteractive -Command "Get-BitLockerVolume" < /dev/null

     # Benar (CMD):
     /mnt/c/Windows/System32/cmd.exe /c "powercfg /h off" < /dev/null
     
     # Salah (Akan hang):
     powershell.exe "Get-BitLockerVolume"
     ```
2. **Pencegahan Error UNC Path pada CMD.EXE:**
   * `cmd.exe` tidak mendukung path WSL UNC (`\\wsl.localhost\...`). Jika menjalankan `cmd.exe`, jalankan dengan direktori Windows atau alihkan stdin/stdout dengan benar.

---

## 3. Efisiensi Eksekusi & Larangan Polling Loop (Anti-Spinning Rules)

*Berdasarkan temuan 800+ langkah redundan pada sesi evaluasi:*

1. **Manfaatkan Reactive Wakeup Antigravity:**
   * Antigravity secara otomatis membangunkan (*wake up*) agen ketika proses background (`task-xxx`) selesai.
   * **DILARANG KERAS** membuat loop polling dengan kombinasi `schedule` (timer 10s–15s), `manage_task status`, dan `view_file` secara berulang-ulang saat menunggu perintah panjang (seperti `chkdsk`, `tar`, atau `apt-get`).
2. **Pola Menjalankan Perintah Asinkron:**
   * Cukup luncurkan perintah dengan `run_command` (berikan `WaitMsBeforeAsync` secukupnya, mis. 5000–10000 ms).
   * Jika perintah berlanjut di background, berikan pesan status singkat kepada pengguna dan **hentikan pemanggilan tool** untuk mengakhiri turn. Tunggu notifikasi otomatis dari sistem.

---

## 4. Standar Modifikasi & Penulisan File

1. **Overwriting File Proyek:**
   * Untuk memperbarui atau menimpa file dokumentasi/kode yang besar secara menyeluruh, gunakan `write_to_file` dengan `Overwrite: true`.
   * **JANGAN** menggunakan `replace_file_content` dengan blok tunggal 100+ baris yang mencoba mengganti seluruh isi file (akan terpotong limit argumen).
2. **Penggunaan `ArtifactMetadata`:**
   * Parameter `ArtifactMetadata` HANYA digunakan ketika membuat file dokumen artefak di direktori brain (`<appDataDir>/brain/<conversation-id>`). Jangan sertakan pada file kode/proyek standar.
3. **Sinkronisasi Repositori Lintas Mount:**
   * Setiap kali memperbarui `docs/LINUX_MIGRATION_BLUEPRINT.md`, `AGENTS.md`, atau `.agents/prompt.txt` di WSL (`/home/rizz/dev/os-manager/`), selalu sinkronkan ke mount Windows di `/mnt/d/dev/os-manager/`.

---

## 5. Quality Gate Pra & Pasca Migrasi

Sebelum menghapus partisi sementara (`DEBIAN_SET` 8 GB) atau partisi lama:
1. Pastikan sistem bare-metal telah reboot sukses minimal 2–3 kali.
2. Verifikasi Wi-Fi Intel AC 9560 (`iwlwifi`), Audio, Bluetooth, dan Suspend/Resume berjalan normal.
3. Gunakan urutan ekspansi partisi online yang aman:
   ```bash
   sudo growpart /dev/nvme0n1 <nomor_partisi>
   sudo resize2fs /dev/nvme0n1p<nomor_partisi>
   ```

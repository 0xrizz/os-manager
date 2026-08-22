# AGENTS.md

Panduan operasional dan standar eksekusi agen AI (Antigravity `agy`, Claude Code, dan subagent) di lingkungan `os-manager` (Debian WSL2 & Bare-Metal Linux).

---

## 1. Aturan Keamanan Mutlak (Zero-Data-Loss & Zero-USB Guardrails)

* **Partisi Data (Drive D: / `DATA_STORE`):**
  * DILARANG menjalankan perintah `format`, `mkfs`, `wipefs`, `fdisk d`, `rm -rf` skala luas, atau penghapusan partisi pada `/dev/nvme0n1p4` (Drive D: / `/mnt/data`).
  * Data di Drive D: (~201 GB) harus selalu diperlakukan sebagai **in-place persistent storage**.
* **Operasi Disk Destruktif:**
  * Wajib meminta konfirmasi eksplisit sebelum menjalankan modifikasi partisi fisik yang tidak dapat dibatalkan.
* **Invarian Arsitektur Zero-USB:**
  * Seluruh prosedur instalasi, partisi ulang, pemeliharaan kernel/bootloader, dan recovery sistem harus 100% Zero-USB (in-place kernel kexec / loopback ISO / staging partition).
  * Dilarang mengasumsikan atau mensyaratkan tersedianya media USB eksternal.

---

## 2. Standar Interoperabilitas & Eksekusi Perintah

*Berdasarkan audit evaluasi sesi `4f7b4fa7-e919-4058-ade7-9d4da54f4391` & audit riwayat sesi bare-metal*:

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
3. **Standar Elevasi Sudo Non-Interaktif (.env Integration):**
   * Pada bare-metal Linux di mana `sudo` memerlukan password, eksekusi perintah `sudo` tanpa terminal/stdin interaktif akan gagal (*sudo: a terminal is required to read the password*).
   * **Aturan Baku:**
     - Selalu uji akses passwordless terlebih dahulu (`sudo -n true 2>/dev/null`).
     - Jika memerlukan password, baca nilai password dari file `.env` di root repository (`/home/rizz/dev/os-manager/.env`) dan alirkan secara aman melalui `sudo -S`:
       ```bash
       # Pola Eksekusi Sudo Aman:
       PASS=$(grep -E '^SUDO_PASSWORD=' .env | cut -d '=' -f2- || cat .env | tr -d '\r\n')
       echo "$PASS" | sudo -S <perintah>
       ```
     - Dilarang mencetak (*echo/log*) isi file `.env` atau password ke stdout/stderr atau laporan review.
4. **Resiliensi Eksekusi CLI (`osm` & Runtimes):**
   * Pastikan biner lokal di `~/.local/bin` dapat ditemukan oleh subshell non-interaktif.
   * Dalam instruksi kepada pengguna atau skrip otomatisasi, sediakan export path atau fallback path absolut:
     ```bash
     export PATH="$HOME/.local/bin:$PATH"
     osm tune all --audit
     # atau fallback langsung:
     ~/.local/bin/osm tune all --audit
     ```

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
   * Setiap kali memperbarui `docs/LINUX_MIGRATION_BLUEPRINT.md`, `AGENTS.md`, atau `.agents/prompt.txt` di WSL (`/home/rizz/dev/os-manager/`), selalu sinkronkan ke mount Windows di `/mnt/d/dev/os-manager/` (jika mount tersedia).

---

## 5. Quality Gate Pra & Pasca Migrasi

Sebelum menghapus partisi sementara (`DEBIAN_SET` 8–25 GB) atau partisi lama:
1. Pastikan sistem bare-metal telah reboot sukses minimal 2–3 kali.
2. Verifikasi Wi-Fi Intel AC 9560 (`iwlwifi`), Audio, Bluetooth, dan Suspend/Resume berjalan normal.
3. Gunakan urutan ekspansi partisi online yang aman:
   ```bash
   sudo growpart /dev/nvme0n1 <nomor_partisi>
   sudo resize2fs /dev/nvme0n1p<nomor_partisi>
   ```

---

## 6. Manajemen Siklus Hidup Sesi & Context Hygiene (Anti-Bloat Rules)

*Berdasarkan audit pemutusan stream pada sesi `4f7b4fa7-e919-4058-ade7-9d4da54f4391` (1.130+ steps)*:

1. **Batas Langkah & Checkpoint Rutin:**
   * Sesi percakapan yang mendekati **300+ langkah** memiliki risiko tinggi mengalami *stream interruption* dan latensi tinggi akibat context bloat.
   * Setiap kali menyelesaikan fase besar (misal: seluruh rangkaian SDD selesai diuji dan di-*review*), agen wajib menyusun ringkasan status di `.agents/HANDOFF.md`.
   * Sarankan kepada pengguna untuk memulai percakapan baru jika akan memulai topik atau fase implementasi baru yang besar.
2. **Subagent Output Hygiene:**
   * Subagent implementer dan reviewer wajib menulis seluruh log dan diff ke file laporan (`task-N-report.md` / `review-report.md`).
   * Respons langsung ke parent controller dibatasi hanya ringkasan ringkas (status VERDICT, commit hash, ringkasan tes 1 baris).
3. **Fleksibilitas Parameter Konfigurasi:**
   * Hindari penulisan validasi ukuran yang *hardcoded* kaku jika arsitektur mengizinkan rentang yang fleksibel (contoh: partisi staging FAT32 `DEBIAN_SET` fleksibel antara 7 GB s/d 25 GB).
4. **Manajemen Template & Siklus Transisi Sesi (`prompt.txt` & `HANDOFF.md`):**
   * Master template disimpan secara permanen di `.agents/templates/`:
     - `.agents/templates/prompt.template.txt`
     - `.agents/templates/HANDOFF.template.md`
   * **Setiap Kali Tugas / Fase Selesai:**
     - Agen mengompilasi laporan hasil dan checkpoint ke `.agents/HANDOFF.md` (mengikuti format `HANDOFF.template.md`).
     - Agen me-reset / mempersiapkan `.agents/prompt.txt` (dari `prompt.template.txt`) dengan konteks tugas baru untuk sesi berikutnya.
   * **Ketika Memulai Sesi Baru:**
     - Agen membaca `.agents/HANDOFF.md` dan `.agents/prompt.txt` sebagai status awal langsung tanpa perlu membaca ulang seluruh riwayat sesi lama.

---

## 7. Python Runtime & System Boundary Guardrail

1. **Integritas Python Sistem Debian (`/usr/bin/python3`):**
   * DILARANG mengganti, menimpa, atau menghapus symlink `/usr/bin/python3` bawaan Debian (Debian 13 Trixie menggunakan Python 3.13 untuk GNOME dan utilitas sistem).
   * DILARANG menjalankan `pip install` langsung pada sistem tanpa flag virtualenv/PEP 668.
2. **Isolasi Lingkungan Pengembangan:**
   * Semua dependensi proyek `os-manager` harus diisolasi di `/home/rizz/dev/os-manager/.venv`.
   * Pengembangan runtime Python versi kustom wajib menggunakan `uv` atau `pyenv` di user-space (`~/.local/`).

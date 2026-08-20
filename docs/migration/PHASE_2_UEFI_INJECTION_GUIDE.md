# Panduan Fase 2: Pementasan ISO & Injeksi Entri Boot UEFI NVRAM via DiskGenius

Panduan langkah-demi-langkah ini memandu proses pementasan (*staging*) isi ISO Debian Live ke partisi FAT32 `DEBIAN_SET` (8.0 GB) serta registrasi entri bootloader EFI (`\EFI\BOOT\BOOTX64.EFI`) langsung ke NVRAM motherboard melalui **DiskGenius** untuk booting bare-metal tanpa media USB eksternal.

---

## 1. Konsep & Alur Kerja Zero-USB Boot

Pada firmware UEFI modern x86_64, motherboard dapat mem-boot file biner EFI (`.efi`) dari partisi bertipe FAT32 mana pun pada disk internal NVMe GPT asalkan path EFI tersebut terdaftar di tabel entri boot NVRAM atau diletakkan pada lokasi fallback standar (`\EFI\BOOT\BOOTX64.EFI`).

```
┌────────────────────────────────────────────────────────────────────────┐
│ UEFI NVRAM Firmware Boot Priority Sequence                            │
├────────────────────────────────────────────────────────────────────────┤
│ [1] Debian Live Installer (Disk 0, Partisi "DEBIAN_SET", \EFI\BOOT\...)│ ──▶ Booting ke Debian Live
│ [2] Windows Boot Manager  (Disk 0, Partisi 1 EFI ESP,    \EFI\Micro...)│ ──▶ Fallback OS Windows
└────────────────────────────────────────────────────────────────────────┘
```

Dengan mendaftarkan partisi `DEBIAN_SET` sebagai prioritas boot pertama (#1), komputer akan langsung memuat kernel Debian Live dan desktop installer Calamares saat restart, sementara instalasi Windows tetap aman dan utuh sebagai prioritas kedua (#2).

---

## 2. Prasyarat (*Prerequisites*)

Sebelum melakukan injeksi boot entry di DiskGenius:
1. **Partisi Staging Siap (Fase 1):**
   Partisi 8.0 GB FAT32 dengan label `DEBIAN_SET` telah dibuat dan memiliki *Drive Letter* di Windows (misalnya `E:`).
2. **Ekstraksi ISO Selesai (Fase 2):**
   Seluruh isi ISO Debian Live (`EFI/`, `live/filesystem.squashfs`, `vmlinuz`, `initrd`) telah diekstrak ke dalam partisi `DEBIAN_SET`.

---

## 3. Ekstraksi Payload ISO Otomatis via WSL

Jalankan script pementasan payload dari terminal WSL:

```bash
# 1. Ekstrak payload ISO Debian Live ke partisi DEBIAN_SET
./scripts/migration/stage_iso_contents.sh

# 2. Verifikasi ketersediaan bootloader EFI pada partisi staging
bash tests/test_uefi_staging.sh
```

### Output yang Diharapkan:
```
==================================================
Phase 2: Debian Live ISO Staging
==================================================
Source ISO: /mnt/d/download/debian-live-12.8.0-amd64-gnome.iso (3.22 GB)
Querying Windows for DEBIAN_SET staging volume...
Staging drive resolved: E: -> /mnt/e
Mounting ISO image loopback (read-only)...
Copying ISO filesystem tree to staging volume (/mnt/e)...
Flushing disk write buffers (sync)...
Verifying staged payload components on /mnt/e:
  [OK] UEFI Bootloader: EFI/boot/bootx64.efi
  [OK] SquashFS Root: live/filesystem.squashfs (2.72 GB)
  [OK] Kernel & Initrd: live/vmlinuz* and live/initrd*
==================================================
SUCCESS: Debian Live ISO payload staged successfully!
==================================================
Checking for Staged Debian EFI Bootloader...
==================================================
PASS: UEFI bootloader \EFI\BOOT\BOOTX64.EFI verified on DEBIAN_SET.
```

---

## 4. Panduan Injeksi Entri Boot UEFI NVRAM di DiskGenius

### Langkah 1: Buka Pengaturan UEFI Boot di DiskGenius
1. Buka aplikasi **DiskGenius** di Windows (Run as administrator).
2. Pada menu bar bagian atas, klik menu **Tools** -> pilih **Set UEFI BIOS boot entries** (atau tekan shortcut jika tersedia).
3. Jendela dialog daftar entri boot NVRAM UEFI saat ini akan muncul.

---

### Langkah 2: Tambahkan Entri Boot Baru (*Add Boot Entry*)
1. Pada jendela dialog *Set UEFI BIOS boot entries*, klik tombol **Add** (atau tombol `+`).
2. Konfigurasikan properti entri boot sebagai berikut:
   * **Disk**: Pilih **Disk 0** (SSD NVMe internal: `SSSTC CL1-4D512` atau sejenisnya).
   * **Partition**: Pilih partisi **`DEBIAN_SET` (FAT32, ~8.0 GB)**.
   * **Boot File Path**: Ketik atau browse ke path:
     ```
     \EFI\BOOT\BOOTX64.EFI
     ```
     *(Catatan: Jika tombol Browse diklik, navigasikan ke folder `EFI` -> `boot` -> pilih `bootx64.efi`)*.
   * **Entry Name / Boot Description**: Masukkan nama yang jelas:
     ```
     Debian Live Installer
     ```

---

### Langkah 3: Atur Prioritas Boot ke Posisi Teratas (#1)
1. Pilih entri **`Debian Live Installer`** yang baru saja ditambahkan di daftar entri boot.
2. Klik tombol **Move Up** (atau tombol panah ke atas) berulang kali hingga entri `Debian Live Installer` berada di **baris paling atas (Urutan Pertama / Priority #1)**.
3. Pastikan urutan boot terlihat seperti berikut:
   - **1:** `Debian Live Installer` (menunjuk ke `DEBIAN_SET:\EFI\BOOT\BOOTX64.EFI`)
   - **2:** `Windows Boot Manager` (menunjuk ke `ESP:\EFI\Microsoft\Boot\bootmgfw.efi`)
4. Centang opsi **Enable this entry** (jika ada checkbox status aktif).
5. Klik tombol **Save Current Boot Entry** (atau **Save / Apply**) di bagian bawah jendela dialog.
6. Klik **Close** untuk menutup dialog.

---

## 5. Alternatif & Verifikasi Tambahan

### A. Verifikasi Entri Firmware di Windows (Opsional)
Anda dapat memverifikasi bahwa entri boot telah terdaftar di firmware dengan menjalankan PowerShell/CMD sebagai administrator:

```cmd
bcdedit /enum firmware
```
Cari entri dengan deskripsi `Debian Live Installer` di bagian atas daftar boot manager.

### B. Menu Boot Manual BIOS/UEFI (One-Time Boot Menu)
Jika komputer Anda mendukung tombol pintas One-Time Boot Menu saat pertama kali dinyalakan:
* **Lenovo / Legion / ThinkPad:** Tekan **`F12`** atau **`Fn + F12`** berulang kali saat logo PC muncul.
* **HP:** Tekan **`F9`** atau **`Esc` -> `F9`**.
* **Dell:** Tekan **`F12`**.
* **ASUS / Acer / MSI:** Tekan **`F8`**, **`F11`**, atau **`F12`**.

Dari menu boot tersebut, pilih `Debian Live Installer` atau partisi `DEBIAN_SET`.

---

## 6. Prosedur Keselamatan & Rencana Pemulihan (*Rollback Guardrails*)

> [!NOTE]
> **Windows Tetap Dapat Diakses Kapan Saja:**
> * Entri `Windows Boot Manager` tidak dihapus, hanya berada di urutan kedua.
> * Jika instalasi Debian dibatalkan atau ingin kembali ke Windows sebelum install, Anda cukup masuk ke BIOS Setup (tekan `F2` atau `Del` saat boot) dan pindahkan `Windows Boot Manager` kembali ke urutan #1, atau pilih Windows dari menu boot F12.
> * Partisi data `DATA_STORE` (Drive D: 201 GB) tetap aman dan tidak disentuh sama sekali oleh proses bootloader.

---

## 7. Langkah Selanjutnya (Transisi ke Fase 3)

Setelah pementasan ISO dan registrasi entri boot selesai:
1. Tutup semua aplikasi yang sedang berjalan di Windows.
2. Restart komputer (*Start Menu -> Restart*).
3. Komputer akan boot langsung ke desktop **Debian 12 Live GNOME**.
4. Di dalam lingkungan Live, buka panduan Fase 3 untuk memandu instalasi Calamares:
   - Target Partisi Root: Ruang kosong **~112 GB Unallocated Space**.
   - Target EFI System Partition: Partisi 1 ESP 100 MB (`/dev/nvme0n1p1`), mount ke `/boot/efi` **TANPA FORMAT**.
   - Partisi Data: `/dev/nvme0n1p4` (`DATA_STORE`) **JANGAN DIUBAH/DIFORMAT**.

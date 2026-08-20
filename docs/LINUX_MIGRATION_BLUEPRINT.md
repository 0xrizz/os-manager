# Blueprint Migrasi Penuh ke Debian Native (Zero USB & Zero External Backup)

Dokumen ini berisi cetak biru (*blueprint*) arsitektur teknis dan prosedur komprehensif untuk memigrasikan sistem dari Windows ke **Debian GNU/Linux (GNOME)** secara penuh pada perangkat Lenovo IdeaPad 3 (81WD) tanpa menggunakan media USB eksternal dan tanpa memindahkan/mem-backup data Drive D ke cloud/media luar.

---

## 1. Keputusan Desain Terverifikasi (Design Alignment)

| Parameter | Keputusan Terpilih | Rationale / Justifikasi |
| :--- | :--- | :--- |
| **Distro Target** | **Debian GNU/Linux** *(Official Live GNOME with non-free firmware)* | Sesuai lingkungan WSL saat ini (`Debian Trixie`), kestabilan jangka panjang, paket dependency teruji. |
| **Desktop Environment** | **GNOME** (Wayland) | Integrasi touchpad/gesture laptop sangat mulus, modern, default Debian. |
| **Root Filesystem** | **ext4** (dengan dynamic Swapfile) | Kompatibilitas dan reliabilitas maksimal, zero maintenance overhead. |
| **Partisi Data (D:)** | **NTFS (244 GB)** $\rightarrow$ Mount ke `/mnt/data` | Tetap utuh (*in-place*), tidak diformat, data 201 GB aman. |
| **Migrasi Konfigurasi WSL** | Backup `~/*` ke `D:\wsl_backup\` | Dotfiles, SSH keys, git config, dan project runtime langsung di-restore di bare-metal Debian. |

---

## 2. Profil Perangkat & Spesifikasi Hardware

| Komponen | Spesifikasi Terdeteksi | Driver & Modul Kernel Debian |
| :--- | :--- | :--- |
| **Model Laptop** | Lenovo IdeaPad 3 (Type `81WD`) | Kernel ACPI / `ideapad-laptop` |
| **Prosesor (CPU)** | Intel Core i5-1035G1 @ 1.00GHz (4 Core / 8 Thread) | `x86_64` (Intel Ice Lake) |
| **Grafis (GPU)** | Intel UHD Graphics (Ice Lake G1) | Driver kernel `i915` (Mesa 3D) |
| **Konektivitas Nirkabel** | Intel Wireless-AC 9560 (Wi-Fi 5 + BT 5.1) | `iwlwifi` (`firmware-iwlwifi`) |
| **Penyimpanan Utama** | NVMe SSD `SSSTC CL1-4D512` (512 GB) | Driver kernel `nvme` |
| **Tabel Partisi** | GPT (GUID Partition Table) | Native EFI / UEFI Boot Mode |
| **Memori (RAM)** | 8.00 GB DDR4 | Native Linux Memory Management |

---

## 3. Data Diagnostik Administratif & Geometri Partisi Terverifikasi

### Hasil Verifikasi Pra-Migrasi Windows (Status: SELESAI / OK)

| Parameter Diagnostik | Nilai / Status Terverifikasi | Perintah Verifikasi | Catatan Keamanan |
| :--- | :--- | :--- | :--- |
| **Hak Akses Admin** | `True` (Elevated Administrator) | `[WindowsPrincipal]::GetCurrent().IsInRole(...)` | Izin disk raw & BCD granted. |
| **BitLocker Drive C:** | `Fully Decrypted`, `Protection Off` | `manage-bde -status C:` | Siap di-shrink tanpa enkripsi lock. |
| **BitLocker Drive D:** | `Fully Decrypted`, `Protection Off` | `manage-bde -status D:` | Partisi data aman & terbaca Linux. |
| **Fast Startup / Hiber** | `Disabled` (`hiberfil.sys` removed) | `powercfg /h off` | Mencegah NTFS dirty flag / read-only lock. |
| **Integritas NTFS Drive D:** | `Clean` (`NoErrorsFound`) | `Repair-Volume -DriveLetter D -SpotFix` | Index corrupt diperbaiki, boot check dijadwalkan. |
| **Secure Boot UEFI** | `True` (Enabled) | `Confirm-SecureBootUEFI` | Didukung penuh oleh signed shim Debian. |
| **Arsip Backup WSL** | `753 MB` (Verifikasi: `TAR_INTEGRITY_OK`) | `tar -tzf ...` & `sha256sum` | Disimpan di `/mnt/d/wsl_backup/`. |
| **SHA256 Backup WSL** | `0c36b038b3f469b75c7594cab025618399c186d6923274bed3beff23cc8c4daf` | `sha256sum wsl_home_backup.tar.gz` | Checksum valid, tercatat di `wsl_home_backup.sha256`. |

---

### Geometri Partisi Fisik Eksisting (Disk 0: `SSSTC CL1-4D512`)

| Nomor Partisi | Offset Sektor (Bytes) | Ukuran Fisik | File System | Label / Type | Status Aksi Migrasi |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **Partisi 1** | `1,048,576` (1 MB) | `100 MB` | FAT32 | System (EFI ESP) | **PERTahankan** (Mount ke `/boot/efi`, JANGAN FORMAT) |
| **Partisi 2 (C:)** | `105,906,176` (~100 MB) | `226.01 GB` | NTFS | Basic Data (`OS`) | **SHRINK 120 GB** $\rightarrow$ Buat 8 GB FAT32 Installer & ~112 GB Unallocated |
| **Partisi 3** | `242,786,385,920` (~226.1 GB) | `5.71 GB` | NTFS | Recovery (WinRE) | **PERTahankan / Biarkan** (Tidak disentuh) |
| **Partisi 4 (D:)** | `248,917,262,336` (~231.8 GB) | `244.14 GB` | NTFS | Basic Data (`DATA_STORE`) | **ZONA AMAN: JANGAN FORMAT / JANGAN HAPUS (201 GB Data)** |

---

## 4. Struktur Partisi: Eksisting vs Target Akhir

### Kondisi Partisi Fisik Saat Ini (Disk 0)
```
Total Storage: 512 GB (NVMe SSD: SSSTC CL1-4D512)
┌─────────────────┬──────────────────────┬────────────────────┬──────────────────────┐
│ Part 1: EFI ESP │ Part 2: Drive C:     │ Part 3: Recovery   │ Part 4: Drive D:     │
│ 100 MB (FAT32)  │ 226.0 GB (NTFS)      │ 5.71 GB (NTFS)     │ 244.14 GB (NTFS)     │
│ Bootloader      │ Windows OS (105G Used│ Windows Recovery   │ DATA_STORE           │
│                 │ / 121G Free)         │                    │ (201G Used / 44G Free│
└─────────────────┴──────────────────────┴────────────────────┴──────────────────────┘
```

---

### Kondisi Sementara (Staging Installer Debian via DiskGenius)
```
┌─────────┬──────────────────────┬─────────────┬─────────────┬──────────────────────┐
│ Part 1  │ Ruang Kosong (Baru)  │ Part Baru   │ Part 3      │ Part 4: Drive D:     │
│ 100 MB  │ ~112 - 118 GB        │ 8.0 GB      │ 5.71 GB     │ 244.14 GB (NTFS)     │
│ EFI ESP │ (Unallocated Space)  │ FAT32       │ Recovery    │ Label: "DATA_STORE"  │
│         │ Calon Root Debian /  │ "DEBIAN_SET"│             │ TETAP UTUH (201GB)   │
└─────────┴──────────────────────┴─────────────┴─────────────┴──────────────────────┘
```

---

### Kondisi Target Akhir (Setelah Debian Native Terpasang & Partisi Installer Dihapus)
```
┌─────────────────┬───────────────────────────────────────────┬──────────────────────┐
│ Partisi 1       │ Partisi Debian Utama (Eks C: + Installer) │ Partisi Data (Eks D:)│
│ 100 MB (FAT32)  │ ~230 - 235 GB (ext4)                      │ 244.14 GB (NTFS)     │
│ Mount:          │ Mount:                                    │ Mount:               │
│ /boot/efi       │ / (Root Debian GNOME + /swapfile)         │ /mnt/data            │
└─────────────────┴───────────────────────────────────────────┴──────────────────────┘
```

---

## 5. Alur Prosedur Eksekusi Terstruktur

```mermaid
flowchart TD
    A[Fase 0: Diagnostik & Backup WSL - SELESAI] --> B[Fase 1: Rekonfigurasi Partisi via DiskGenius]
    B --> C[Fase 2: Staging Debian Live ISO & Injeksi Boot Entry UEFI]
    C --> D[Fase 3: Reboot & Eksekusi Calamares / Debian Installer]
    D --> E[Fase 4: Auto-Mount Data & Restore Dotfiles WSL]
```

---

### FASE 0: Persiapan Sistem di Windows (STATUS: SELESAI / OK)

1. **Backup Konfigurasi WSL:**
   * File arsip: `/mnt/d/wsl_backup/wsl_home_backup.tar.gz` (Ukuran: `753 MB`).
   * Checksum: `0c36b038b3f469b75c7594cab025618399c186d6923274bed3beff23cc8c4daf`.
   * Integritas: Validasi via `tar -tzf` sukses tanpa error (`TAR_INTEGRITY_OK`).
2. **Perbaikan File System Drive D:**
   * Diperbaiki via `Repair-Volume -DriveLetter D -SpotFix` (Status: `NoErrorsFound`).
   * Boot-time check dijadwalkan via `chkntfs /c D:`.
3. **Nonaktifkan Fast Startup & Hibernasi:**
   * Dieksekusi via `powercfg /h off` (`hiberfil.sys` dihapus).
4. **Verifikasi BitLocker:**
   * Konversi: `Fully Decrypted`, Proteksi: `Protection Off` pada C: dan D:.

---

### FASE 1: Manajemen Partisi dengan DiskGenius (Panduan Pengguna)

1. **Beri Label Partisi Data (Keamanan Visual):**
   * Buka DiskGenius (WinPE / Windows).
   * Klik kanan Partisi 4 (Drive D:) $\rightarrow$ **Set Volume Label** $\rightarrow$ Isi: `DATA_STORE`.
2. **Backup Tabel Partisi GPT:**
   * Klik menu **Disk** $\rightarrow$ **Backup Partition Table** $\rightarrow$ Simpan file di `D:\ptf_backup.ptf`.
3. **Resize Partisi C:**
   * Klik kanan Partisi 2 (Drive C:) $\rightarrow$ **Resize Partition**.
   * Perkecil Drive C: sebesar **120 GB**.
   * Dari ruang bebas hasil shrink:
     * Alokasikan 1 partisi baru ukuran **8.0 GB**, Tipe: **Primary**, Format: **FAT32**, Volume Label: `DEBIAN_SET`.
     * Sisakan ruang sisanya (~112 GB) sebagai **Unallocated Space** (ruang kosong tanpa partisi).
4. Klik **Save All** di pojok kiri atas untuk mengeksekusi operasi.

---

### FASE 2: Staging Debian Live GNOME ISO & Injeksi Boot UEFI

1. **Ekstrak Debian Live GNOME ISO:**
   * Buka file ISO Debian Live GNOME (`debian-live-*-amd64-gnome+nonfree.iso`) via File Explorer / DiskGenius.
   * Salin / ekstrak seluruh folder dan file di dalam ISO (`.disk`, `boot`, `d-i`, `dists`, `efi`, `install`, `isolinux`, `live`, `pool`) langsung ke root partisi `DEBIAN_SET` (FAT32 8 GB).
2. **Daftarkan Boot Entry ke UEFI NVRAM via DiskGenius:**
   * Di DiskGenius, buka menu **Tools** $\rightarrow$ **Set UEFI BIOS boot entries**.
   * Klik tombol **Add**.
   * Pilih Disk: `Disk 0 (NVMe)`.
   * Pilih Partisi: `DEBIAN_SET (FAT32)`.
   * File path loader: `\EFI\BOOT\BOOTX64.EFI`.
   * Beri nama label boot entry: `Debian Live Installer`.
   * Klik tombol **Move Up** agar entri ini berada di urutan paling atas.
   * Klik **Save Current Boot Entry** lalu tutup.

---

### FASE 3: Proses Instalasi Debian Native (Manual Partitioning)

1. **Restart Komputer:**
   * Laptop akan booting langsung ke Live Environment Debian GNOME dari partisi `DEBIAN_SET`.
2. **Buka Installer (Calamares / Debian Installer):**
   * Buka icon **Install Debian** di desktop GNOME Live.
   * Pilih bahasa, zona waktu (mis. `Asia/Jakarta`), dan keyboard layout.
3. **Atur Partisi Manual (Manual Partitioning):**
   * Pilih opsi **Manual Partitioning**.
   * **Partisi 1 (100 MB EFI ESP):**
     * Edit $\rightarrow$ Mount point: `/boot/efi` $\rightarrow$ **JANGAN CENTANG FORMAT**.
   * **Ruang Kosong (Unallocated Space ~112 GB):**
     * Klik Create $\rightarrow$ Filesystem: `ext4` $\rightarrow$ Mount point: `/` (Root) $\rightarrow$ Format: `Yes`.
   * **Partisi 4 (`DATA_STORE` 244 GB NTFS):**
     * **JANGAN DISENTUH / JANGAN FORMAT**.
   * **Lokasi Bootloader:** Pilih `/dev/nvme0n1`.
4. Selesaikan instalasi akun pengguna (`rizz`), password, lalu jalankan instalasi hingga selesai (100%).
5. Reboot sistem ke Debian Bare-Metal.

---

### FASE 4: Konfigurasi Pasca-Instalasi di Debian Native

1. **Konfigurasi Auto-Mount Partisi Data NTFS di `/etc/fstab`:**
   Buka terminal di Debian:
   ```bash
   sudo mkdir -p /mnt/data
   UUID_DATA=$(sudo blkid -s UUID -o value /dev/nvme0n1p4)
   echo "UUID=${UUID_DATA}  /mnt/data  ntfs-3g  defaults,uid=1000,gid=1000,umask=022,nofail  0  0" | sudo tee -a /etc/fstab
   sudo mount -a
   ls -la /mnt/data
   ```
2. **Restore Konfigurasi & Lingkungan Kerja WSL:**
   ```bash
   tar -xzvf /mnt/data/wsl_backup/wsl_home_backup.tar.gz -C ~/
   ```
3. **Setup Swapfile Dinamis (Opsional / Rekomendasi 8 GB):**
   ```bash
   sudo fallocate -l 8G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```
4. **Pembersihan Partisi Installer Sementara:**
   * Buka GNOME Disks (`gnome-disks`) atau `sudo gdisk /dev/nvme0n1`.
   * Hapus partisi sementara 8 GB (`DEBIAN_SET`) dan partisi eks-C / WinRE yang sudah tidak terpakai.
   * Perluas (*expand*) partisi root `/` (ext4) hingga mengisi seluruh ruang sisa SSD.

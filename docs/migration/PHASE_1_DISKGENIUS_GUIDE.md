# Panduan Fase 1: Rekonfigurasi Partisi & Pembuatan Staging FAT32 via DiskGenius

Panduan langkah-demi-langkah ini memandu proses rekonfigurasi partisi SSD NVMe (Disk 0: `SSSTC CL1-4D512` 512 GB) menggunakan aplikasi **DiskGenius** pada Windows/WinPE untuk mempersiapkan partisi installer Debian Live GNOME tanpa media USB eksternal.

---

## 1. Ringkasan & Pilihan Layout Partisi

Tersedia dua opsi konfigurasi partisi yang **100% aman dan didukung penuh** oleh seluruh toolchain otomasi migrasi:

| Parameter | Kondisi Awal | Opsi A (Default Minimal Layout) | Opsi B (Pilihan User / Generous Headroom) |
| :--- | :--- | :--- | :--- |
| **Partisi 1 (EFI ESP)** | `100 MB` FAT32 | `100 MB` FAT32 *(Utuh)* | `100 MB` FAT32 *(Utuh)* |
| **Partisi 2 (Drive C:)** | `226.0 GB` NTFS | `~106.0 GB` NTFS *(Shrink 120 GB)* | `~140.0 GB` NTFS *(Shrink 86 GB)* |
| **Partisi Staging (`DEBIAN_SET`)** | *Belum ada* | `8.0 GB` FAT32 | `15.0 GB` FAT32 |
| **Ruang Unallocated (Calon Root Debian)** | *Belum ada* | `~112.0 GB` Unallocated Space | `~71.0 GB` Unallocated Space |
| **Partisi 3 (Recovery)** | `5.71 GB` NTFS | `5.71 GB` NTFS *(Utuh)* | `5.71 GB` NTFS *(Utuh)* |
| **Partisi 4 (Drive D: `DATA_STORE`)** | `244.1 GB` NTFS | `244.1 GB` NTFS (**AMAN / UTUH 201 GB**) | `244.1 GB` NTFS (**AMAN / UTUH 201 GB**) |

---

## 2. Mengapa Kedua Opsi 100% Aman?

1. **Perlindungan Mutlak Partisi 4 (`DATA_STORE`):**
   * Partisi 4 (Drive D: ~244.14 GB berisi 201 GB data) terletak di sektor akhir SSD (Offset `~248.9 GB` s/d `512 GB`).
   * Seluruh operasi resize hanya terjadi pada Partisi 2 (Drive C: di awal disk). Partisi 4 **sama sekali tidak disentuh atau digeser**.
2. **Fleksibilitas Toolchain Otomasi (7 GB – 25 GB):**
   * Skrip verifikasi (`verify_staging_partition.sh`), checklist pra-instalasi (`pre_install_checklist.sh`), dan unit test (`test_staging_partition.sh`) telah dirancang fleksibel untuk mendeteksi partisi FAT32 berlabel `DEBIAN_SET` dengan rentang kapasitas antara **7 GB s/d 25 GB**.
   * Baik ukuran 8.0 GB maupun 15.0 GB akan terdeteksi dan tervalidasi secara otomatis.
3. **Kompatibilitas File System FAT32 & SquashFS:**
   * Batasan ukuran file tunggal pada FAT32 adalah `4 GiB` (4.294.967.295 bytes).
   * File payload instalasi Debian Live (`live/filesystem.squashfs`) berukuran `~2.8 GB`, sehingga aman tersimpan di partisi FAT32 8 GB maupun 15 GB tanpa risiko error fragmentasi.
4. **Kapasitas Root Debian yang Memadai:**
   * Instalasi Debian 12 (GNOME + Wayland) hanya membutuhkan ruang minimal `~15–20 GB`.
   * Baik ruang `~112 GB` (Opsi A) maupun `~71 GB` (Opsi B) memberikan ruang penyimpanan yang jauh lebih dari cukup untuk sistem operasi, runtime, dan aplikasi inti.
5. **Ekspansi Online Pasca-Instalasi (Fase 4):**
   * Setelah sistem bare-metal Debian beroperasi dan lolos Quality Gate, partisi staging `DEBIAN_SET` (8 GB atau 15 GB) dapat dihapus dan digabungkan kembali ke partisi root secara online tanpa reboot menggunakan `expand_root_partition.sh` (menjadikan kapasitas root bertambah menjadi ~120 GB atau ~86 GB).

---

## 3. Diagram Geometri Disk

### Geometri Disk 0 Saat Ini (SSD Fisik 512 GB)
```
┌─────────────────┬──────────────────────────────────────┬────────────────────┬──────────────────────┐
│ Part 1: EFI ESP │ Part 2: Drive C: (Windows OS)        │ Part 3: Recovery   │ Part 4: Drive D:     │
│ 100 MB (FAT32)  │ 226.0 GB (NTFS)                      │ 5.71 GB (NTFS)     │ 244.14 GB (NTFS)     │
│ Bootloader      │ (105 GB Terpakai / 121 GB Kosong)    │ Windows Recovery   │ (201 GB Terpakai)    │
└─────────────────┴──────────────────────────────────────┴────────────────────┴──────────────────────┘
```

### Opsi A: Layout Default (Staging 8 GB / Unallocated ~112 GB)
```
┌─────────┬──────────────────┬──────────────────────┬─────────────┬─────────────┬──────────────────────┐
│ Part 1  │ Part 2: C: (OS)  │ Unallocated Space    │ Part Baru   │ Part 3      │ Part 4: Drive D:     │
│ 100 MB  │ ~106 GB (NTFS)   │ ~112 GB              │ 8.0 GB      │ 5.71 GB     │ 244.14 GB (NTFS)     │
│ EFI ESP │ Windows OS       │ (Calon Root Debian   │ FAT32       │ Recovery    │ Label: "DATA_STORE"  │
│         │                  │  ext4 di Fase 3)     │"DEBIAN_SET" │             │ TETAP UTUH (201 GB)  │
└─────────┴──────────────────┴──────────────────────┴─────────────┴─────────────┴──────────────────────┘
```

### Opsi B: Layout Pilihan User (Drive C: 140 GB / Staging 15 GB / Unallocated ~71 GB)
```
┌─────────┬──────────────────┬──────────────────────┬─────────────┬─────────────┬──────────────────────┐
│ Part 1  │ Part 2: C: (OS)  │ Unallocated Space    │ Part Baru   │ Part 3      │ Part 4: Drive D:     │
│ 100 MB  │ ~140 GB (NTFS)   │ ~71 GB               │ 15.0 GB     │ 5.71 GB     │ 244.14 GB (NTFS)     │
│ EFI ESP │ Windows OS       │ (Calon Root Debian   │ FAT32       │ Recovery    │ Label: "DATA_STORE"  │
│         │ (35 GB Free)     │  ext4 di Fase 3)     │"DEBIAN_SET" │             │ TETAP UTUH (201 GB)  │
└─────────┴──────────────────┴──────────────────────┴─────────────┴─────────────┴──────────────────────┘
```

---

## 4. Peringatan Keamanan Mutlak (Zero-Data-Loss Guardrail)

> [!CAUTION]
> **ZONA AMAN DRIVE D: (`DATA_STORE` - 244 GB):**
> * **DILARANG** memilih opsi *Format*, *Delete Partition*, atau *Wipe Partition* pada **Partisi 4 (Drive D:)**.
> * Partisi 4 menampung **201 GB data berharga** serta file cadangan konfigurasi WSL (`D:\wsl_backup\wsl_home_backup.tar.gz`) dan backup konfigurasi BCD (`D:\bcd_backup.bcd`).
> * Pastikan Anda telah melabeli partisi 4 sebagai `DATA_STORE` agar terlihat jelas secara visual di DiskGenius.

---

## 5. Panduan Langkah-Demi-Langkah di DiskGenius

### Langkah 1: Jalankan DiskGenius & Beri Label Visual Partisi Data
1. Buka aplikasi **DiskGenius** (klik kanan shortcut DiskGenius -> *Run as administrator*).
2. Di panel kiri atau diagram partisi, klik kanan pada **Partisi 4** (Drive `D:` / kapasitas ~244 GB).
3. Pilih menu **Set Volume Label**.
4. Masukkan nama label: `DATA_STORE` lalu klik **OK**.
5. Klik menu **Disk** pada toolbar atas -> pilih **Backup Partition Table To File**.
6. Simpan file cadangan dengan nama `D:\ptf_backup.ptf`.

---

### Langkah 2: Shrink Partisi 2 (Drive C:)

Pilih salah satu nilai berikut sesuai preferensi Anda:

* **Jika Memilih Opsi B (Pilihan User - Rekomendasi):**
  1. Klik kanan pada **Partisi 2** (Drive `C:` / `OS` Windows) -> pilih **Resize Partition**.
  2. Pada kolom **Shrink Space** (atau *Unallocated Space After*), masukkan nilai: **`86.0 GB`** (atau `88064 MB`).
  3. Pastikan sisa ukuran Drive C: menjadi sekitar **~140.0 GB** (memberikan ruang bebas ~35 GB untuk Windows).

* **Jika Memilih Opsi A (Default Minimal Layout):**
  1. Klik kanan pada **Partisi 2** (Drive `C:` / `OS` Windows) -> pilih **Resize Partition**.
  2. Pada kolom **Shrink Space** (atau *Unallocated Space After*), masukkan nilai: **`120.0 GB`** (atau `122880 MB`).
  3. Pastikan sisa ukuran Drive C: menjadi sekitar **~106.0 GB**.

---

### Langkah 3: Buat Partisi Staging FAT32 (`DEBIAN_SET`)

1. Pada area ruang kosong (*Unallocated Space*) yang baru terbentuk setelah mengecilkan Drive C:
   * **Untuk Opsi B:** Buat partisi baru berukuran **`15.0 GB`** (atau `15360 MB`).
   * **Untuk Opsi A:** Buat partisi baru berukuran **`8.0 GB`** (atau `8192 MB`).
2. Konfigurasikan parameter partisi baru sebagai berikut:
   * **File System / File System Type**: Pilih **`FAT32`** *(Wajib FAT32 untuk kompatibilitas native boot UEFI x86_64)*.
   * **Volume Label**: Masukkan **`DEBIAN_SET`**.
   * **Partition Type**: Pilih **`Primary Partition`**.
   * **Drive Letter**: Biarkan otomatis dialokasikan (misalnya drive `E:`).
3. **Sisa Ruang Bebas (*Unallocated Space*):**
   * Untuk Opsi B: Sisa ruang kosong sekitar **~71 GB** dibiarkan sebagai **Unallocated Space** (ruang kosong tanpa partisi).
   * Untuk Opsi A: Sisa ruang kosong sekitar **~112 GB** dibiarkan sebagai **Unallocated Space**.
   * *Ruang unallocated ini nantinya akan dipilih pada installer Calamares/Debian Live di Fase 3 untuk partisi root (`/`) ext4*.

---

### Langkah 4: Terapkan Perubahan (*Save All*)

1. Periksa kembali ringkasan diagram di DiskGenius:
   - Partisi 1: EFI System Partition (100 MB FAT32)
   - Partisi 2: Drive C: (~140 GB atau ~106 GB NTFS)
   - Ruang Bebas: Unallocated Space (~71 GB atau ~112 GB)
   - Partisi Staging: `DEBIAN_SET` (15.0 GB atau 8.0 GB FAT32)
   - Partisi 3: Recovery (5.71 GB NTFS)
   - Partisi 4: `DATA_STORE` (244.1 GB NTFS - **Utuh 201 GB**)
2. Klik tombol **Save All** di toolbar DiskGenius (atau klik **Start** pada dialog Resize).
3. Jika DiskGenius menampilkan dialog konfirmasi penguncian volume atau meminta restart sementara ke WinPE/DOS environment untuk memindahkan file sistem Windows yang terkunci:
   * Klik **Yes** / **OK** untuk mengizinkan DiskGenius mengeksekusi operasi.
   * Tunggu proses resize dan pembuatan partisi FAT32 selesai (biasanya memakan waktu 1–3 menit).

---

## 6. Verifikasi Otomatis Pasca Pembuatan Partisi

Setelah operasi DiskGenius selesai dan Windows kembali aktif, jalankan script verifikasi di terminal WSL:

```bash
# Jalankan test validasi deteksi partisi staging
bash tests/test_staging_partition.sh

# Jalankan script inspeksi layout partisi lengkap
bash scripts/migration/verify_staging_partition.sh
```

### Contoh Output yang Diharapkan (Opsi B - 15 GB):
```
==================================================
Checking for DEBIAN_SET Volume / FAT32 Staging...
==================================================
PASS: Staging partition detected: {"DriveLetter":"E","FileSystemLabel":"DEBIAN_SET","FileSystem":"FAT32","Size":16106127360}

Querying Disk 0 layout from Windows...
PartitionNumber DriveLetter     Offset          Size Type
--------------- -----------     ------          ---- ----
              1              1048576     104857600 System
              2 C          105906176  150323855360 Basic
              5 E       226778480640   16106127360 Basic
              3         242786385920    6130872320 Recovery
              4 D       248917262336  262142947328 Basic

SUCCESS: DEBIAN_SET detected at Drive E: (FAT32, 15.00 GB, Label: DEBIAN_SET)
```

---

## 7. Penanganan Masalah (Troubleshooting)

### Q1: Drive Letter untuk `DEBIAN_SET` tidak muncul otomatis di Windows Explorer
* **Solusi**: Buka DiskGenius atau `diskmgmt.msc` di Windows, klik kanan partisi `DEBIAN_SET` -> pilih **Assign New Drive Letter** (misalnya `E:`).

### Q2: Volume terformat sebagai NTFS / exFAT, bukan FAT32
* **Solusi**: Di DiskGenius, klik kanan partisi `DEBIAN_SET` -> **Format Current Partition** -> pilih **FAT32** -> Cluster size `4096` -> Label `DEBIAN_SET` -> Klik **Format**.

### Q3: Tidak sengaja mengalokasikan seluruh sisa ruang ke `DEBIAN_SET` tanpa menyisakan Unallocated Space
* **Solusi**: Di DiskGenius, klik kanan `DEBIAN_SET` -> **Resize Partition** -> kecilkan menjadi **15.0 GB** (atau **8.0 GB**) sehingga sisa ruang kembali menjadi *Unallocated Space*.

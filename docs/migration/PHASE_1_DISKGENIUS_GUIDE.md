# Panduan Fase 1: Rekonfigurasi Partisi & Pembuatan Staging FAT32 via DiskGenius

Panduan langkah-demi-langkah ini memandu proses rekonfigurasi partisi SSD NVMe (Disk 0: `SSSTC CL1-4D512` 512 GB) menggunakan aplikasi **DiskGenius** pada Windows/WinPE untuk mempersiapkan partisi installer Debian Live GNOME tanpa media USB eksternal.

---

## 1. Ringkasan & Tujuan Operasi Partisi

| Parameter | Kondisi Saat Ini | Aksi DiskGenius | Kondisi Target Pasca Fase 1 |
| :--- | :--- | :--- | :--- |
| **Partisi 1 (EFI ESP)** | `100 MB` FAT32 | **Pertahankan** (Jangan diubah) | `100 MB` FAT32 (`\EFI\Microsoft\Boot`) |
| **Partisi 2 (Drive C:)** | `226.0 GB` NTFS (`OS`) | **Shrink 120.0 GB** | `~106.0 GB` NTFS (`OS` Windows) |
| **Partisi Baru (Staging)** | *Belum ada* | **Buat Partisi 8.0 GB FAT32** | `8.0 GB` FAT32 (Label: `DEBIAN_SET`) |
| **Ruang Kosong (Baru)** | *Belum ada* | **Sisakan sebagai Unallocated** | `~112.0 GB` Unallocated Space |
| **Partisi 3 (Recovery)** | `5.71 GB` NTFS | **Pertahankan** (Jangan diubah) | `5.71 GB` NTFS (WinRE) |
| **Partisi 4 (Drive D:)** | `244.1 GB` NTFS | **Beri Label `DATA_STORE`** | `244.1 GB` NTFS (**AMAN / UTUH 201 GB**) |

---

## 2. Diagram Geometri Disk (Sebelum vs Sesudah Fase 1)

### Geometri Disk 0 Saat Ini (Disk Fisik: 512 GB)
```
┌─────────────────┬──────────────────────────────────────┬────────────────────┬──────────────────────┐
│ Part 1: EFI ESP │ Part 2: Drive C: (Windows OS)        │ Part 3: Recovery   │ Part 4: Drive D:     │
│ 100 MB (FAT32)  │ 226.0 GB (NTFS)                      │ 5.71 GB (NTFS)     │ 244.14 GB (NTFS)     │
│ Bootloader      │ (105 GB Terpakai / 121 GB Kosong)    │ Windows Recovery   │ (201 GB Terpakai)    │
└─────────────────┴──────────────────────────────────────┴────────────────────┴──────────────────────┘
```

### Geometri Disk 0 Target Pasca Fase 1
```
┌─────────┬──────────────────┬──────────────────────┬─────────────┬─────────────┬──────────────────────┐
│ Part 1  │ Part 2: C: (OS)  │ Unallocated Space    │ Part Baru   │ Part 3      │ Part 4: Drive D:     │
│ 100 MB  │ ~106 GB (NTFS)   │ ~112 GB              │ 8.0 GB      │ 5.71 GB     │ 244.14 GB (NTFS)     │
│ EFI ESP │ Windows OS       │ (Calon Root Debian   │ FAT32       │ Recovery    │ Label: "DATA_STORE"  │
│         │                  │  ext4 di Fase 3)     │"DEBIAN_SET" │             │ TETAP UTUH (201 GB)  │
└─────────┴──────────────────┴──────────────────────┴─────────────┴─────────────┴──────────────────────┘
```

---

## 3. Peringatan Keamanan Mutlak (Zero-Data-Loss Guardrail)

> [!CAUTION]
> **ZONA AMAN DRIVE D: (`DATA_STORE` - 244 GB):**
> * **DILARANG** memilih opsi *Format*, *Delete Partition*, atau *Wipe Partition* pada **Partisi 4 (Drive D:)**.
> * Partisi 4 menampung **201 GB data berharga** serta file cadangan konfigurasi WSL (`D:\wsl_backup\wsl_home_backup.tar.gz`) dan backup konfigurasi BCD (`D:\bcd_backup.bcd`).
> * Pastikan Anda telah melabeli partisi 4 sebagai `DATA_STORE` agar terlihat jelas secara visual di DiskGenius.

---

## 4. Panduan Langkah-Demi-Langkah di DiskGenius

### Langkah 1: Jalankan DiskGenius & Beri Label Visual Partisi Data
1. Buka aplikasi **DiskGenius** (klik kanan icon DiskGenius -> *Run as administrator*).
2. Di panel kiri atau grafik partisi, klik kanan pada **Partisi 4** (Drive `D:` / kapasitas ~244 GB).
3. Pilih menu **Set Volume Label** (atau tekan tombol pintas jika tersedia).
4. Masukkan nama label: `DATA_STORE` lalu klik **OK**.
5. Klik menu **Disk** pada toolbar atas -> pilih **Backup Partition Table To File**.
6. Simpan file cadangan dengan nama `D:\ptf_backup.ptf`.

---

### Langkah 2: Shrink Partisi 2 (Drive C:) Sebesar 120.0 GB
1. Klik kanan pada **Partisi 2** (Drive `C:` / `OS` Windows).
2. Pilih menu **Resize Partition** (atau klik tombol **Resize** pada toolbar).
3. Pada jendela dialog *Resize Partition*:
   * Perhatikan baris **Space of front part** atau **Space of rear part**.
   * Di kolom **Shrink Space** (atau *Unallocated Space After*), masukkan nilai: **`120.0 GB`** (atau `122880 MB`).
   * Pastikan sisa ukuran Drive C: masih sekitar **~106 GB** (lebih dari cukup untuk Windows dan pagefile).
4. Jangan langsung klik Start — lanjutkan ke pengaturan pembuatan partisi di bawah.

---

### Langkah 3: Buat Partisi Staging FAT32 (8.0 GB - `DEBIAN_SET`)
1. Di dalam jendela resize/partisi baru pada area unallocated:
   * Buat satu partisi baru berukuran: **`8.0 GB`** (atau `8192 MB`).
   * **File System / File System Type**: Pilih **`FAT32`** *(Wajib FAT32 untuk kompatibilitas native boot UEFI x86_64)*.
   * **Volume Label**: Masukkan **`DEBIAN_SET`**.
   * **Partition Type**: Pilih **`Primary Partition`**.
   * **Drive Letter**: Biarkan otomatis dialokasikan (misalnya drive `E:`).
2. **Sisa Ruang Bebas (~112 GB):**
   * Pastikan sisa ruang kosong sekitar **112 GB** dibiarkan sebagai **Unallocated Space** (ruang kosong tanpa partisi).
   * *Ruang unallocated ini nantinya akan dipilih pada installer Calamares/Debian Live di Fase 3 untuk partisi root (`/`) ext4*.

---

### Langkah 4: Terapkan Perubahan (*Save All*)
1. Periksa kembali diagram visual di DiskGenius:
   - Partisi 1: EFI System Partition (100 MB FAT32)
   - Partisi 2: Drive C: (~106 GB NTFS)
   - Unallocated Space: (~112 GB)
   - Partisi Staging: `DEBIAN_SET` (8.0 GB FAT32)
   - Partisi 3: Recovery (5.71 GB NTFS)
   - Partisi 4: `DATA_STORE` (244.1 GB NTFS - **Utuh**)
2. Klik tombol **Save All** di pojok kiri atas toolbar DiskGenius (atau klik **Start** pada dialog Resize).
3. Jika DiskGenius menampilkan dialog konfirmasi penguncian volume atau meminta restart sementara ke WinPE/DOS environment untuk memindahkan file sistem Windows yang terkunci:
   * Klik **Yes** / **OK** untuk mengizinkan DiskGenius mengeksekusi operasi.
   * Tunggu proses resize dan format partisi FAT32 selesai (biasanya memakan waktu 1–3 menit).

---

## 5. Verifikasi Otomatis Pasca Pembuatan Partisi

Setelah operasi DiskGenius selesai dan Windows kembali aktif, jalankan script verifikasi di terminal WSL:

```bash
# Jalankan test validasi deteksi partisi staging
bash tests/test_staging_partition.sh

# Jalankan script inspeksi layout partisi lengkap
bash scripts/migration/verify_staging_partition.sh
```

### Output yang Diharapkan:
```
==================================================
Checking for DEBIAN_SET Volume / FAT32 Staging...
==================================================
PASS: Staging partition detected: {"DriveLetter":"E","FileSystemLabel":"DEBIAN_SET","FileSystem":"FAT32","Size":8589934592}

Querying Disk 0 layout from Windows...
PartitionNumber DriveLetter     Offset          Size Type
--------------- -----------     ------          ---- ----
              1              1048576     104857600 System
              2 C          105906176  113825972224 Basic
              5 E       234399727616    8589934592 Basic
              3         242786385920    6130872320 Recovery
              4 D       248917262336  262142947328 Basic

SUCCESS: DEBIAN_SET mounted at Drive E (FAT32, 8.00 GB)
```

---

## 6. Penanganan Masalah (Troubleshooting)

### Q1: Drive Letter untuk `DEBIAN_SET` tidak muncul otomatis di Windows Explorer
* **Solusi**: Buka DiskGenius atau `diskmgmt.msc` di Windows, klik kanan partisi `DEBIAN_SET` -> pilih **Assign New Drive Letter** (misalnya `E:`).

### Q2: Volume terformat sebagai NTFS / exFAT, bukan FAT32
* **Solusi**: Di DiskGenius, klik kanan partisi `DEBIAN_SET` -> **Format Current Partition** -> pilih **FAT32** -> Cluster size `4096` -> Label `DEBIAN_SET` -> Klik **Format**.

### Q3: Tidak sengaja mengalokasikan seluruh 120 GB ke `DEBIAN_SET`
* **Solusi**: Di DiskGenius, klik kanan `DEBIAN_SET` -> **Resize Partition** -> kecilkan menjadi **8.0 GB** sehingga sisa ~112 GB kembali menjadi *Unallocated Space*.

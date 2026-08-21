# Panduan Lengkap: Offline Root Partition Expansion via GParted Live

Panduan ini menjelaskan prosedur grafis langkah-demi-langkah untuk memperluas partisi root Debian (`/dev/nvme0n1p6`) dari 71 GB menjadi **~235 GB ext4 utuh** menggunakan media Live GParted setelah partisi transisi (2: Windows C:, 5: DEBIAN_SET, 3: Windows Recovery) berhasil dihapus menggunakan skrip reklamasi.

---

## 1. Ringkasan Arsitektur & Peta Partisi

### Sebelum Ekspansi (Pasca Eksekusi `reclaim_transition_partitions.sh`):
```text
[ /dev/nvme0n1 (512 GB SSD) ]
├── p1: EFI System Partition (100 MB FAT32) [/boot/efi]
├── [UNALLOCATED SPACE ~155 GB] (Eks Windows C: & Debian Installer)
├── p6: Debian Root System (71 GB ext4) [/]
├── [UNALLOCATED SPACE ~5.7 GB] (Eks Windows Recovery)
└── p4: DATA_STORE (244.1 GB NTFS) [/mnt/data] -> DILARANG DISENTUH (Zero-Data-Loss)
```

### Target Akhir Setelah Ekspansi GParted:
```text
[ /dev/nvme0n1 (512 GB SSD) ]
├── p1: EFI System Partition (100 MB FAT32) [/boot/efi]
├── p6: Debian Root System (~235 GB ext4) [/] -> MERGED DENGAN SPACE KIRI & KANAN
└── p4: DATA_STORE (244.1 GB NTFS) [/mnt/data] -> TETAP UTUH DAN PRESERVED
```

---

## 2. Persiapan Media Live & Booting

1. **Siapkan Media USB Live:**
   - Gunakan USB Live Linux yang menyediakan utility **GParted GUI** (misalnya: USB Installer Debian Live GNOME, Ubuntu Live Desktop, atau GParted Live ISO).
2. **Koneksikan USB ke Laptop:**
   - Tancapkan USB flashdrive ke port USB laptop Lenovo IdeaPad 3.
3. **Restart dan Masuk ke Boot Menu:**
   - Restart sistem atau nyalakan laptop.
   - Saat logo Lenovo muncul di layar, segera tekan tombol **F12** secara berulang-ulang (atau tekan tombol Novo dengan jarum SIM ejector pada sisi kanan bodi laptop) untuk membuka **Lenovo Boot Manager**.
4. **Pilih Boot Device:**
   - Pilih nama USB Flashdrive Anda dari daftar UEFI Boot Devices, lalu tekan **Enter**.
5. **Masuk ke Mode Live Desktop:**
   - Pilih *Try Debian / Try Ubuntu without installing* atau *GParted Live (Default settings)* hingga tampilan grafis Desktop siap digunakan.

---

## 3. Prosedur Grafis di GParted GUI

1. **Buka Aplikasi GParted:**
   - Buka menu aplikasi (Applications) dan jalankan **GParted**.
   - Jika diminta password root, gunakan default distro (biasanya kosong atau ketik `sudo gparted` via terminal Live).
   - Di pojok kanan atas jendela GParted, pastikan dropdown memilih drive:  
     **`/dev/nvme0n1 (512.00 GiB)`**

2. **Verifikasi Layout Partisi:**
   Pastikan daftar partisi yang ditampilkan sesuai dengan skema:
   - `/dev/nvme0n1p1` (`fat32`, 100.00 MiB)
   - `unallocated` (~155.00 GiB)
   - `/dev/nvme0n1p6` (`ext4`, 71.00 GiB)
   - `unallocated` (~5.70 GiB)
   - `/dev/nvme0n1p4` (`ntfs`, 244.14 GiB, Label: `DATA_STORE`)

   > [!CAUTION]
   > **PERINGATAN ZERO-DATA-LOSS:**  
   > Partisi **`/dev/nvme0n1p4`** berisi seluruh data penting user (`DATA_STORE` 201 GB). **JANGAN PERNAH** melakukan klik kanan Resize/Move/Delete pada partisi `p4`.

3. **Geser dan Perluas Partisi Root (`/dev/nvme0n1p6`):**
   - Klik kanan pada baris partisi **`/dev/nvme0n1p6`** (ext4) $\rightarrow$ pilih **Resize/Move**.
   - Pada jendela modal interaktif yang muncul:
     - **Tarik slider / panah sebelah kiri** ke ujung paling kiri sampai kolom **Free space preceding (MiB)** bernilai `0`.
     - **Tarik slider / panah sebelah kanan** ke ujung kanan sampai kolom **Free space following (MiB)** bernilai `0` (tepat berbatasan dengan awal partisi `nvme0n1p4`).
     - Kolom **New size (MiB)** akan otomatis terisi nilai total sekitar **`~235000 MiB`** (sekitar 230–235 GiB).
   - Klik tombol **Resize/Move** di pojok kanan bawah modal.
   - Operasi akan masuk ke dalam antrean pending di bagian bawah jendela (*Operations Pending*).

4. **Eksekusi Operasi (Apply All Operations):**
   - Klik tombol ikon centang hijau (**Apply All Operations**) pada toolbar atas GParted.
   - Muncul dialog konfirmasi: *"Are you sure you want to apply the pending operations?"*
   - Klik tombol **Apply**.
   - GParted akan melakukan:
     1. *Move partition `/dev/nvme0n1p6` to the left* (Memindahkan sektor blok data ext4).
     2. *Grow filesystem on `/dev/nvme0n1p6` to fill the partition* (Memperluas sistem berkas ext4 secara online/offline).
     3. *e2fsck / filesystem sanity check*.
   - Tunggu proses hingga selesai (status: *All operations successfully completed*).
   - Klik tombol **Close**.

5. **Tutup GParted:**
   - Tutup aplikasi GParted.

---

## 4. Reboot & Verifikasi Kapasitas Baru

1. **Reboot Sistem:**
   - Di terminal Live atau menu sistem, jalankan:
     ```bash
     sudo reboot
     ```
   - Cabut USB Flashdrive saat diminta / saat layar mati.

2. **Login ke Debian GNU/Linux:**
   - Masuk kembali ke sesi Debian GNOME desktop seperti biasa.

3. **Verifikasi Storage & Filesystem via Terminal:**
   Jalankan perintah berikut:
   ```bash
   df -hT /
   ```
   **Output yang diharapkan:**
   ```text
   Filesystem     Type  Size  Used Avail Use% Mounted on
   /dev/nvme0n1p6 ext4  231G   15G  205G   7% /
   ```

4. **Jalankan Skrip Audit Geometri:**
   ```bash
   ./scripts/migration/verify_reclaimed_geometry.sh
   ```
   Periksa bahwa seluruh mount point aktif (`/`, `/mnt/data`, `/boot/efi`) berfungsi optimal tanpa kendala UUID atau corrupted blocks.

---

## 5. Troubleshooting & FAQ

- **Q: Apakah UUID partisi root (`/dev/nvme0n1p6`) berubah setelah Resize/Move?**  
  *A:* Tidak. GParted mempertahankan UUID ext4 asli (`e2fsprogs`), sehingga `/etc/fstab` dan entri GRUB tetap valid tanpa perlu rekonfigurasi.
- **Q: Apa yang harus dilakukan jika GRUB tidak menemukan kernel setelah resize?**  
  *A:* Masuk via Live USB, lakukan `chroot` sederhana ke `/dev/nvme0n1p6`, lalu jalankan `update-grub` dan `grub-install /dev/nvme0n1`. Namun pada skema UEFI Debian 12 standar, GRUB memuat kernel via UUID filesystem yang tidak berubah.
- **Q: Bagaimana status integritas `/dev/nvme0n1p4` (`DATA_STORE`)?**  
  *A:* Karena partisi `p4` berada di sektor paling akhir dan tidak disentuh sama sekali oleh operasi resize `p6`, integritas data NTFS tetap 100% aman.

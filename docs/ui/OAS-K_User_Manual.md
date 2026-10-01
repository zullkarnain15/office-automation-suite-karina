# OAS-K User Manual

## Cara Membuka Aplikasi

Jalankan dari project root:

```powershell
py main.py
```

## Konsep Penting

OAS-K tidak membuat database atau Data Root otomatis saat aplikasi dibuka. Ini
disengaja supaya aplikasi tidak menulis data kantor tanpa konfirmasi user.

Fitur utama baru aktif setelah Data Root dan database OAS-K disiapkan melalui:

Settings -> Storage & Database -> Initialize Data Location

## Urutan Setup Pertama Kali

1. Buka `Settings`.
2. Masuk tab `Storage & Database`.
3. Klik `Initialize Data Location`.
4. Pilih folder Data Root yang akan dipakai.
5. Konfirmasi pembuatan struktur:
   `database`, `recorder_profiles/hris`, `backup`, `output`, `logs`, `diagnostics`.
6. Saat diminta Registry, pilih simpan jika Data Root ini ingin menjadi default.
7. Klik `Refresh Status`.
8. Pastikan:
   - Database Exists: `True`
   - Database Valid: `True`
   - Schema: `1`

## Setelah Database Aktif

1. Masuk `Settings -> Import / Export`.
2. Import workbook konfigurasi resmi bila database masih kosong.
3. Cek `Settings -> Module Configuration`.
4. Pastikan konfigurasi Attendance, Outlook Revisi, HRIS, dan Utilities terbaca.
5. Kembali ke Dashboard atau module yang ingin dites.

## Fungsi Menu

### Dashboard

Ringkasan status database, Data Root, backup, health, dan aktivitas terakhir.
Gunakan tombol `Buka Settings` pada panduan cepat bila database belum aktif.

### Attendance

Untuk ekstraksi data absensi menjadi HRIS TXT dan Excel Report.

Alur:

1. Pastikan konfigurasi aktif terbaca.
2. Atur periode dan workflow.
3. Klik `Periksa Data`.
4. Klik `Jalankan Attendance`.
5. Cek Process Log dan result.

### Outlook Revisi

Untuk memproses revisi email Outlook dan attachment.

Alur:

1. Gunakan `Safe Preview / Dry Run` untuk testing awal.
2. Klik `Periksa Konfigurasi`.
3. Klik `Periksa Mailbox`.
4. Klik `Jalankan Outlook`.
5. Mode SEND tetap butuh checklist dan typed confirmation `SEND`.

### HRIS

Untuk assisted upload TXT ke HRIS.

Alur:

1. Pilih folder TXT source.
2. Pastikan periode, workflow, dan recorder profile benar.
3. Centang `Upload manual dipahami`.
4. Klik `Periksa Data`.
5. Klik `Mulai HRIS Upload`.
6. Login dan Upload tetap manual; OAS-K hanya menunggu konfirmasi lanjut.

### Utilities

Hanya dua fitur aktif:

- Comparison Result
- Attachment Consolidation

Alur umum:

1. Pilih fitur.
2. Pilih source folder.
3. Atur periode/output/options.
4. Klik `Periksa Data`.
5. Klik `Jalankan`.

### History

Melihat riwayat job dan membuka artifact yang benar-benar ada.

### Settings

Pusat konfigurasi:

- General
- Module Configuration
- Import / Export
- Storage & Database
- Backup & Recovery
- HRIS Recorder Profiles

### System Health

Klik `Run Checks` untuk mengecek kesiapan database, storage, module config,
write access, dan recovery. Halaman ini tidak menjalankan engine.

## Troubleshooting

### Database belum ada atau fitur terlihat belum aktif

Penyebab paling umum: Data Root belum diinisialisasi.

Solusi:

1. Buka `Settings -> Storage & Database`.
2. Klik `Initialize Data Location`.
3. Pilih folder Data Root.
4. Setelah selesai, klik `Refresh Status`.
5. Jika database valid, lanjut import konfigurasi.

### Module mengatakan belum dikonfigurasi

Database bisa valid tetapi tabel konfigurasi module masih kosong.

Solusi:

1. Buka `Settings -> Import / Export`.
2. Import workbook konfigurasi resmi.
3. Cek `Settings -> Module Configuration`.

### Outlook SEND tidak jalan

Mode live SEND memang dilindungi. User harus:

1. Tidak memakai dry run.
2. Centang acknowledgement.
3. Ketik `SEND` pada confirmation dialog.

### HRIS tidak otomatis upload

Ini benar. Upload HRIS wajib manual. OAS-K hanya membantu workflow, pause, log,
dan resume.

## Testing Fitur Yang Disarankan

1. Setup database dan import konfigurasi.
2. Run `System Health`.
3. Test Attendance dengan data sample/non-production.
4. Test Outlook Revisi di dry run dulu.
5. Test HRIS dengan TXT sample dan environment aman.
6. Test Utilities Comparison Result.
7. Test Utilities Attachment Consolidation.
8. Cek History dan artifact actions.

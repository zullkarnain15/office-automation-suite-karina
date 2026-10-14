# Verifikasi rilis OAS-K 1.0.10

Tanggal: 16 September 2026. Rebuild versi tetap 1.0.10 dengan filter recall.
Paket ini menggantikan build 1.0.10 sebelumnya; gunakan checksum di bawah.

- ZIP: `dist/release/v1.0.10/OAS-K_Update_v1.0.10.zip`.
- EXE: `dist/release/v1.0.10/application/OAS-K.exe`.
- Laporan mesin: `dist/release/v1.0.10/verification.json`.
- Verifier: `tools/verify_release_1_0_10.py` (menjalankan updater dan EXE dalam direktori terisolasi).

Production terakhir dinyatakan pengguna sebagai versi 1.0.9. Manifest paket
1.0.9 yang diarsipkan menetapkan schema 4; checksum EXE lama cocok dengan
catatan verifikasi rilis 1.0.9 dan EXE dalam ZIP lama.

Manifest baru secara eksplisit menetapkan minimum_current_version 1.0.9,
database_schema_from 4, database_schema_to 4, migration_required false.
Tidak ada perubahan schema atau kebutuhan mengganti database.

Validasi:

- Suite updater, startup migration dan Outlook: 168 passed.
  Warning ZIP duplikat berasal dari fixture penolakan entri duplikat.
- Suite mencakup backup schema lama dan migrasi berurutan; paket ini sendiri
  menerima schema 4 dan tidak menjalankan migrasi ke schema baru.
- Validator dari commit 3ec6d45 (source versi 1.0.9) menerima ZIP baru.
- ApplicationUpdateService.prepare_update() memvalidasi paket, membuat backup
  schema 4, dan menyiapkan transaksi update pada Data Root uji.
- EXE 1.0.9 arsip disalin ke Application Root uji, lalu diganti oleh updater
  yang diekstrak dari EXE 1.0.10. Updater selesai dengan exit code 0.
- Post-update health check EXE 1.0.10: SUCCESS, schema 4, seluruh checks true.
  Jendela Tk teramati dan ditutup setelah pemeriksaan.
- Seluruh SQL dump database sebelum update, backup, dan setelah update sama.
  Fixture berisi pengaturan global, Outlook, dan sender master.
- File output dan recorder profiles uji tetap sama; backup EXE lama tersedia.
- ZIP hanya memuat application/OAS-K.exe, manifest.json, release_notes.txt,
  checksums.sha256, serta entri direktori application/.
- Filter recall diperiksa langsung dalam modul outlook.downloader di arsip EXE.
- Tes recall mencakup normal-recall-normal, recall report/subclass, inbox hanya
  recall, batch 250/500, SMTP BCC, dan kegagalan filter tanpa fallback berbahaya.
- Arsip EXE tidak memuat database, output, logs, backup, recorder profiles,
  atau workbook tambahan Templatexx.

Pengujian memakai database sintetis schema 4, bukan database production.
Tidak mengakses mailbox atau menerapkan update ke instalasi production.
Batch Outlook 5/100/250/500 diuji dengan objek simulasi; perilaku COM dan SMB
production tetap perlu dipantau melalui Process.log yang baru.

SHA-256 ZIP:
`f0b4efb07765a021500afeae303aad8915f799e541c2115a69fcdba6ba153eb5`

SHA-256 EXE:
`c36fc9be15befab82ca57200b78db15e7fbb1cb27bab6f66c963edaf1360ad89`

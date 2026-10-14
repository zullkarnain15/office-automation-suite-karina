# Verifikasi rilis OAS-K 1.0.9

Tanggal: 9 September 2026.

Paket: `dist/release/v1.0.9/OAS-K_Update_v1.0.9.zip`.
EXE: `dist/release/v1.0.9/application/OAS-K.exe`.

Manifest menetapkan versi minimum aplikasi 1.0.0, schema sumber 4,
schema tujuan 4, dan `migration_required: false`. Schema production 4
didasarkan pada informasi pengguna; paket ini tidak mengubah schema.

Validasi yang selesai:

- Suite updater dan startup migration: 57 passed. Peringatan ZIP duplikat
  berasal dari fixture yang sengaja menguji penolakan entri duplikat.
- Regresi UI, HRIS, dan Utilities: 451 passed, 1 skipped. Pengujian ulang
  file tes Tk attendance terkait selesai dengan 3 passed.
- Tes khusus versi 1.0.0/schema 4 membandingkan seluruh SQL dump sebelum
  update, pada backup, dan sesudah health check; hasil identik.
- ZIP final divalidasi, checksum internal dan eksternal diperiksa,
  lalu diproses oleh ApplicationUpdateService.prepare_update().
- EXE updater yang diekstrak dari EXE rilis menjalankan penggantian aplikasi
  di Application Root terisolasi dan selesai dengan exit code 0.
- EXE 1.0.9 hasil penggantian menghasilkan health check SUCCESS/schema 4;
  jendela Tk sebenarnya terdeteksi dan ditutup setelah pemeriksaan.
- Backup aplikasi lama tersedia. Seluruh isi database uji serta file output
  dan recorder profiles uji tetap sama setelah update.
- Validator lama dari commit 1664234 menerima ZIP final dengan parameter
  current_version 1.0.0 dan active_schema_version 4.
- ZIP berisi manifest, catatan rilis, checksum, dan application/OAS-K.exe.
  Pemeriksaan arsip EXE tidak menemukan database, log, output, backup,
  recorder profiles, atau template tambahan pengguna.

Pengujian memakai database dan aplikasi lama pengganti yang terisolasi.
Binary production 1.0.0 tidak diberikan sehingga tidak dijalankan langsung.
Pengujian tidak menerapkan update ke instalasi production pengguna.
Laporan mesin tersedia di `dist/release/v1.0.9/verification.json`.

SHA-256 ZIP:
`be4726119e2e78729d4f7d33a8bb05d5aa8dedb516e87081442fc7722b648e37`

SHA-256 EXE:
`47eb36ddf20eb0818741b60c3adf937ee8e2171362bc131b57b61c261bf5d90c`

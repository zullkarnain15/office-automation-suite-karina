# OAS-K UI6 — HRIS Safe Manual Acceptance

## Batas lingkungan

Acceptance dilakukan dengan Fake Registry, temporary Data Root, dan mock engine/local
fixture. Production HRIS, mailbox, credential, dan production Registry tidak dipakai.

Source launcher:

```powershell
py tools/ui_test/run_unified_ui.py --test-data-root <temporary-path-yang-belum-ada>
```

## Checklist

- [x] HRIS page terbuka dan memakai visual card UI5B.
- [x] Browser tidak terbuka saat page dibuat/dibuka.
- [x] Active Configuration menampilkan source OAS-K Database.
- [x] TXT discovery hanya berjalan setelah Browse/Refresh; non-TXT diabaikan.
- [x] HO dan BRANCH request terpisah per job.
- [x] Global period dan manual ISO period bekerja.
- [x] Adapter mengubah tanggal ke MM/DD/YYYY untuk HRIS.
- [x] Run Control leading zero dipertahankan.
- [x] Recorder profile relative path dan JSON validation bekerja read-only.
- [x] Validation-only tidak membuat engine/browser/job/output.
- [x] Confirmation menjelaskan Upload manual per file.
- [x] Mock engine memasuki WAITING_FOR_LOGIN.
- [x] Login Selesai — Lanjutkan membuka gate worker.
- [x] Hook attachment memasuki WAITING_FOR_USER_UPLOAD.
- [x] Automatic `_click_upload` tidak dipanggil pada jalur UI6.
- [x] Upload Selesai — Lanjutkan membuka gate dan melanjutkan Run → OK contract.
- [x] Upload Gagal menghentikan item secara aman.
- [x] Failed file tidak dipindahkan pada mode UI6.
- [x] Existing batch tetap memproses file berurutan.
- [x] Progress file count dan dark process log tersedia.
- [x] Cancel saat login/upload melepas wait dan berhenti di safe checkpoint.
- [x] Navigation diblokir ketika job aktif dan pulih saat terminal.
- [x] Dashboard/History dapat membaca module code HRIS dari job tables existing.
- [x] Utilities tetap placeholder/tidak terhubung.
- [x] Tidak ada credential pada model/log/history.

## Smoke result

Source launcher bertahan setelah enam detik:

- `ProcessAlive=True`
- `TestRootCreated=False`
- `DatabaseFiles=0`

HRIS construction smoke pada 1000×640 dan 1180×720, scaling 100%, 125%, dan
150%, menghasilkan zero Fake Registry write/delete dan zero Data Root creation.
1000×640 masuk mode satu kolom; 1180×720 masuk mode dua kolom.

Mock lifecycle menjalankan login callback dan post-attachment Upload callback,
memberi confirmation dari UI side, memverifikasi tanggal `07/01/2026`, dan memastikan
`move_failed_files=False`. Tidak ada Edge atau production HRIS yang dipakai.

Real Edge/PeopleSoft visual certification tetap memerlukan local mock HRIS page yang
mereplikasi iframe/popup atau staging HRIS dengan izin eksplisit. Hal itu dicatat
sebagai technical debt, bukan dijalankan terhadap production.

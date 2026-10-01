# OAS-K UI5B — Manual Visual Checklist

## Lingkungan aman

Launcher:

```powershell
py tools/ui_test/run_unified_ui.py --test-data-root <temporary-path-yang-belum-ada>
```

Fake Registry digunakan. Jangan menginisialisasi `D:\OAS-K\Data`, memakai Registry
production, menjalankan mailbox production, membuat EXE, build, atau dist.

## Hasil acceptance

- [x] Card modern terlihat jelas tanpa blur, gradient, atau shadow berat.
- [x] Typography terpusat dan tetap terbaca tanpa dynamic font shrinking.
- [x] Primary hijau menonjol; secondary dan danger mempunyai style terpisah.
- [x] Input dan readonly state konsisten; tanggal memakai MM/DD/YYYY + kalender.
- [x] Attendance mengikuti susunan tiga row yang ditetapkan.
- [x] Outlook mengikuti susunan empat row dan warning SEND tetap eksplisit.
- [x] Konfigurasi Aktif lebih lebar; panel kanan lebih compact.
- [x] Settings memiliki enam section final dan section dapat discroll.
- [x] Module Configuration maksimal dua card per baris.
- [x] Import/Export terpisah dan step Pilih → Periksa → Terapkan terlihat.
- [x] Process Log berkontras tinggi, monospace, scrollable, dengan tiga action header.
- [x] Progress tidak menampilkan percentage palsu.
- [x] 1180×720 memakai dua kolom; 1000×640 fallback satu kolom dengan scroll.
- [x] Scaling 100%, 125%, dan 150% dapat membangun/navigasi semua target page.
- [x] Tidak ada label/control overlap exception saat resize/scaling smoke.
- [x] Tidak ada dependency runtime atau framework baru.
- [x] Tidak ada engine berjalan hanya karena halaman dibuka.

## Bukti smoke

Source launcher bertahan hidup setelah 6 detik dengan hasil:

- `ExistedBefore=False`
- `ProcessAliveAfter6s=True`
- `RootCreated=False`
- `DatabaseFiles=0`

Construction smoke pada enam kombinasi ukuran/scaling membuka Settings, Attendance,
dan Outlook Revisi. Semua kombinasi menghasilkan `registry_writes=0`,
`registry_deletes=0`, dan `root_created=False`. Pada 1000×640 kedua operational page
masuk mode narrow; pada 1180×720 keduanya masuk mode dua kolom.

Native Windows screenshot sementara diambil dan diperiksa untuk Attendance/Outlook.
Screenshot bukan asset project dan tidak ditambahkan ke repository. Pengukuran widget
dipakai untuk memverifikasi card berada dalam viewport; wrapping Result Summary
dibatasi sesuai card sempit agar teks tidak memaksa lebar layout.

Automated real-Tk smoke juga membuktikan membuka Settings tidak memanggil initialize,
relocate, preview, commit, export, backup, restore, import database, atau reset; tidak
membuat folder/database dan tidak menulis Fake Registry.

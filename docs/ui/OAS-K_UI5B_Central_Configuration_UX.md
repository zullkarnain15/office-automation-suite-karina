# OAS-K UI5B — Central Configuration and Visual Foundation

## Interpretasi referensi visual

Referensi digunakan sebagai arah, bukan disalin. UI5B mengambil hierarki navy/teal,
background abu-biru muda, card putih berbatas lembut, tombol aksi utama hijau,
input konsisten, progress faktual, dan process log slate gelap. Efek blur, acrylic,
gradient kompleks, shadow berat, animasi, custom canvas dekoratif, framework GUI,
dan dependency runtime baru sengaja tidak digunakan.

Palet, font, dan spacing terpusat di `ui/constants.py`; konfigurasi ttk berada di
`ui/style_manager.py`. Keterbatasan rounded corner dan shadow native ttk diterima:
separasi visual dibangun dengan border, accent tipis, padding 16 px, dan whitespace.

## Komponen visual reusable

- `ModernCard`: card putih, border lembut, title, optional teal accent, dan body.
- `ResponsiveCardGrid`: grid 80/20 dua kolom, vertical scroll, dan fallback satu
  kolom saat content width di bawah breakpoint.
- `StepIndicator`: presentasi Pilih File → Periksa → Terapkan tanpa business logic.
- `DateEntry`: MM/DD/YYYY dengan tombol kalender; nilai internal tetap ISO.
- `ProgressPanel`: stage, status message, dan indeterminate bar tanpa persen palsu.
- `ResultSummary`: wrapping dapat disesuaikan agar card sempit tetap terbaca.

Style terpusat mencakup primary/secondary/danger action, modern/readonly entry,
dark log panel, ready/warning/error/info status, serta active/completed/pending step.
Badge selalu memiliki teks; warna bukan satu-satunya pembeda.

## Struktur halaman

Attendance:

1. Konfigurasi Aktif | Output Options
2. Period & Workflow | Validation & Run
3. Process Log | Result Summary

Outlook Revisi:

1. Konfigurasi Aktif | Mailbox & Outbound Safety
2. Period & Workflow | Processing Options
3. Validation & Run | Result Summary
4. Process Log full width

Pada width sempit semua card turun menjadi satu kolom dan tetap memakai vertical
scroll. Font tidak diperkecil. Field tanggal mempunyai label format MM/DD/YYYY dan
tombol kalender. Process Log memakai slate gelap, teks terang, Consolas, serta Copy,
Clear View, dan Open Log pada header. Clear View hanya membersihkan tampilan.

Settings tetap memiliki enam section: General, Module Configuration,
Import / Export, Storage & Database, Backup & Recovery, dan HRIS Recorder Profiles.
Module Configuration maksimal dua card per baris dengan detail read-only on demand.
Import dan Export dipisahkan; import menampilkan tiga langkah Pilih File, Periksa,
dan Terapkan.

## Arsitektur konfigurasi pusat

Konfigurasi aktif normal berada di SQLite `OAS-K.db`. Workbook unified resmi adalah
media import/export, bukan sumber utama halaman proses. Alur normal:

`Unified Workbook → Settings Import → Review/Approval → SQLite → Module Service → temporary legacy export → existing reader/engine`

Attendance dan Outlook Revisi mempertahankan adapter, reader, dan engine yang sudah
ada. UI5B tidak mengubah business rule atau output. Advanced / Manual Fallback tetap
session-only, tidak menulis SQLite/Global Settings, dan workbook sementara berada di
OS temp serta dibersihkan best-effort.

Membuka Settings, Module Configuration, Attendance, atau Outlook Revisi hanya
membangun UI dan melakukan read-only configuration refresh. Tidak ada bootstrap,
import/export, backup/restore/reset, browser, mailbox, atau engine yang dijalankan.
Schema v1 tetap 24 tabel. `main.py`, Configuration Reader, workbook/template resmi,
engine, HRIS, Utilities, assets, build, dan dist tidak diubah oleh alignment visual.

## Responsive dan DPI

Target 1180×720 memakai dua kolom; minimum 1000×640 memakai fallback satu kolom
dengan scroll ketika content width melewati breakpoint. Construction smoke lulus
pada scaling Tk 1.00, 1.25, dan 1.50 untuk kedua ukuran. Pada desktop acceptance,
work area membatasi tinggi 1180×720 menjadi 701 px; konten tetap dapat discroll.

Final polish lintas semua halaman, dialog, keyboard/accessibility, dan sertifikasi
high-DPI multi-monitor sengaja ditunda ke UI8.

# OAS-K Production Manual Book

Manual ini dipakai untuk menjalankan Office Automation Suite - Karina di
production dan untuk menyiapkan template konfigurasi supaya proses import tidak
error.

## 1. File Penting

- EXE terbaru: `dist\OAS-K.exe`
- Template konfigurasi aktif:
  `config\templates\OAS-K_Configuration_Template.xlsx`
- Template konfigurasi versi user:
  `config\templates\OAS-K_Configuration_Template v.1.xlsx`
- Database production mengikuti Data Root yang dipilih di aplikasi.
- Recorder profile HRIS berada di Data Root:
  `recorder_profiles\hris`

## 2. Urutan Setup Pertama Kali

1. Buka aplikasi OAS-K.
2. Klik `START` pada welcome screen.
3. Masuk ke `Settings`.
4. Buka bagian `Storage & Database`.
5. Pastikan Data Root dan database aktif terbaca.
6. Jalankan `System Health`.
7. Pastikan status database valid sebelum import konfigurasi.
8. Masuk `Settings -> Import / Export`.
9. Pilih workbook konfigurasi.
10. Klik `Periksa Konfigurasi`.
11. Baca hasil preview.
12. Jika tidak ada error, klik `Terapkan Konfigurasi`.
13. Cek `Settings -> Module Configuration`.

Preview import hanya membaca file. Database baru berubah setelah tombol
`Terapkan Konfigurasi` ditekan.

## 3. Aturan Umum Template Konfigurasi

- Jangan menghapus sheet bawaan template.
- Jangan mengubah nama header kolom.
- Jangan menghapus baris `setting_key`, `setting_value`, `required`, dan
  `description` pada sheet setting.
- Nilai boolean gunakan `TRUE` atau `FALSE`.
- Workflow gunakan `HO` atau `BRANCH`. Untuk beberapa rule Outlook boleh `ALL`.
- Tanggal global gunakan format `YYYY-MM-DD`.
- Payroll Period Outlook gunakan format `MM-YYYY`, contoh `07-2026`.
- Extension attachment Outlook wajib diawali titik, contoh `.xlsx`, `.xls`,
  `.csv`, `.txt`.
- Jangan isi path developer seperti `D:\Python Project\...` untuk production
  kecuali memang sedang testing lokal.

## 4. Bagian Template Yang Tidak Boleh Kosong

Daftar berikut adalah nilai yang paling penting untuk dicek sebelum import.
Kalau nilai ini kosong atau salah format, import bisa gagal atau module dianggap
belum siap.

### Global_Settings

| setting_key | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `output_root` | Ya | Path folder | Folder output production. |
| `period_start` | Jika periode global dipakai | `YYYY-MM-DD` | Contoh `2026-07-01`. |
| `period_end` | Jika periode global dipakai | `YYYY-MM-DD` | Contoh `2026-07-15`. |

### Attendance_Settings

| setting_key | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `use_global_output` | Ya | `TRUE`/`FALSE` | Gunakan output global. |
| `use_global_period` | Ya | `TRUE`/`FALSE` | Gunakan periode global. |
| `split_txt_rows` | Ya | Angka lebih dari 0 | Contoh `10000`. |
| `generate_report_default` | Ya | `TRUE`/`FALSE` | Default generate report. |
| `default_workflow` | Ya | `HO`/`BRANCH` | Workflow awal. |

### Attendance_Sources

| Kolom | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `workflow` | Ya | `HO`/`BRANCH` | Harus sesuai sumber data. |
| `source_code` | Ya | Text unik per workflow | Tidak boleh duplikat dalam workflow sama. |
| `mdb_path` | Ya untuk baris aktif | Path file MDB | Wajib jika `is_active=TRUE`. |
| `is_active` | Ya | `TRUE`/`FALSE` | Baris aktif akan dipakai. |
| `sort_order` | Ya | Angka | Urutan sumber. |

### Outlook_Settings

| setting_key | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `use_global_output` | Ya | `TRUE`/`FALSE` | Gunakan output global. |
| `use_global_period` | Ya | `TRUE`/`FALSE` | Tetap wajib ada di template. |
| `integration_method` | Ya | Text | Biasanya `OOM_COM`. |
| `mailbox_smtp` | Ya | Email valid | Contoh `karina.hr.1@oto.co.id`. |
| `source_folder` | Ya | Nama folder Outlook | Contoh `Inbox`. |
| `send_transport` | Ya | `OUTLOOK`/`SMTP` | Sesuai konfigurasi email. |
| `smtp_port` | Ya | Angka | Contoh `25`. |
| `smtp_timeout_seconds` | Ya | Angka | Contoh `30`. |
| `save_smtp_copy_to_sent` | Ya | `TRUE`/`FALSE` | Simpan copy ke Sent. |
| `processed_folder` | Ya | Nama folder Outlook | Contoh `Deleted Items`. |
| `auto_reply_enabled` | Ya | `TRUE`/`FALSE` | Production biasanya `TRUE`. |
| `send_mode` | Ya | `DRAFT`/`SEND` | `SEND` adalah mode live. |
| `txt_max_lines` | Ya | Angka lebih dari 0 | Contoh `10000`. |
| `module_display_name` | Ya | Text | Contoh `Outlook Revisi`. |
| `payroll_period` | Ya | `MM-YYYY` | Contoh `07-2026`. Jangan kosong. |

Catatan penting: error terakhir terjadi karena `Outlook_Settings` baris
`payroll_period` kosong. Isi dengan `07-2026` atau periode yang sesuai subject
email bulan berjalan.

### Outlook_HO_Senders dan Outlook_Branch_Senders

| Kolom | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `sender_email` | Ya untuk baris aktif | Email valid | Tidak boleh kosong jika `is_active=TRUE`. |
| `is_active` | Ya | `TRUE`/`FALSE` | Hanya baris aktif diproses. |
| `company_code` | Disarankan | Text | Bagian dari kunci data. |
| `branch_code` | Disarankan | Text | Bagian dari kunci data. |
| `required_cc_email` | Jika aturan CC dipakai | Email valid | Dipakai validasi CC. |

Kombinasi `workflow + company_code + branch_code + sender_email` tidak boleh
duplikat.

### Outlook_Subject_Rules

| Kolom | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `workflow` | Ya | `HO`/`BRANCH` | Workflow rule. |
| `subject_pattern` | Ya | Text | Pola subject email. |
| `is_active` | Ya | `TRUE`/`FALSE` | Rule aktif dipakai. |

Kombinasi `workflow + subject_pattern` tidak boleh duplikat.

### Outlook_Attachment_Rules

| Kolom | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `workflow` | Ya | `HO`/`BRANCH` | Workflow rule. |
| `extension` | Ya | Text diawali titik | Contoh `.xlsx`. |
| `is_active` | Ya | `TRUE`/`FALSE` | Rule aktif dipakai. |

Jangan isi `xlsx` tanpa titik. Yang benar adalah `.xlsx`.

### Outlook_Validation_Rules

| Kolom | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `rule_code` | Ya | Text unik per workflow | Contoh kode validasi. |
| `workflow` | Ya | `HO`/`BRANCH`/`ALL` | `ALL` boleh untuk rule umum. |
| `rule_value` | Ya | Text | Nilai aturan validasi. |
| `is_active` | Ya | `TRUE`/`FALSE` | Rule aktif dipakai. |

### Outlook_Reply_Templates

| Kolom | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `reply_code` | Ya | Text unik | Kode template. |
| `recipient_type` | Ya | Text | Sesuai konfigurasi template. |
| `trigger_code` | Ya | Text | Kode trigger. |
| `body_template` | Ya | Text | Isi email balasan. |
| `is_active` | Ya | `TRUE`/`FALSE` | Template aktif dipakai. |

Placeholder yang boleh dipakai:
`{ERROR_REASON}`, `{EXPECTED_SUBJECT}`, `{FAILED_EMAIL}`,
`{ORIGINAL_SUBJECT}`, `{OUTPUT_FOLDER}`, `{OUTPUT_TXT_COUNT}`, `{PERIOD}`,
`{REQUIRED_CC_EMAIL}`, `{RESUBMIT_DEADLINE}`, `{SENDER_NAME}`,
`{SUCCESS_EMAIL}`, `{TOTAL_EMAIL}`.

Placeholder di luar daftar tersebut akan membuat import error.

### HRIS_Settings

| setting_key | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `use_global_output` | Ya | `TRUE`/`FALSE` | Gunakan output global. |
| `use_global_period` | Ya | `TRUE`/`FALSE` | Gunakan periode global. |
| `hris_url` | Ya | URL lengkap | Harus punya scheme, contoh `https://...`. |
| `browser_channel` | Ya | Text | Biasanya `msedge`. |
| `browser_headless` | Ya | `TRUE`/`FALSE` | Production biasanya `FALSE`. |
| `stop_on_first_failure` | Ya | `TRUE`/`FALSE` | Berhenti saat gagal. |
| `manual_recovery_enabled` | Ya | `TRUE`/`FALSE` | Recovery manual. |
| `require_profile_match` | Ya | `TRUE`/`FALSE` | Cocokkan recorder profile. |
| `browser_x` | Ya | Angka | Koordinat browser. |
| `browser_y` | Ya | Angka | Koordinat browser. |
| `browser_width` | Ya | Angka | Lebar browser. |
| `browser_height` | Ya | Angka | Tinggi browser. |
| `browser_zoom` | Ya | Angka | Zoom persen. |
| `verification_enabled` | Ya | `TRUE`/`FALSE` | Verifikasi assisted. |
| `verification_wait_seconds` | Ya | Angka desimal | Contoh `1.0`. |
| `verification_timeout_seconds` | Ya | Angka desimal | Contoh `10.0`. |
| `verification_poll_seconds` | Ya | Angka desimal | Contoh `1.0`. |
| `verification_success_texts` | Ya | Text | Teks sukses yang dicari. |
| `verification_failure_texts` | Ya | Text | Teks gagal yang dicari. |
| `manual_verification_on_unknown` | Ya | `TRUE`/`FALSE` | Manual bila status unknown. |
| `manual_verification_on_error` | Ya | `TRUE`/`FALSE` | Manual bila error. |

`click_profile_path` boleh kosong karena aplikasi juga membaca recorder profile
dari Data Root.

### HRIS_Run_Controls

| Kolom | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `workflow` | Ya | `HO`/`BRANCH` | Workflow upload. |
| `sequence` | Ya | Angka lebih dari 0 | Tidak boleh duplikat. |
| `run_control_id` | Ya | Text | Tidak boleh kosong. |
| `is_active` | Ya | `TRUE`/`FALSE` | Run control aktif dipakai. |

Kombinasi `workflow + run_control_id` tidak boleh duplikat. Nomor `sequence`
juga tidak boleh duplikat.

### HRIS_Assisted_Steps

| Kolom | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `sequence` | Ya | Angka | Tidak boleh duplikat. |
| `step_name` | Ya | Text unik | Tidak boleh duplikat. |
| `action` | Ya | Daftar action valid | Lihat daftar di bawah. |
| `input_source` | Ya | Daftar source valid | Lihat daftar di bawah. |
| `method` | Ya | Daftar method valid | Lihat daftar di bawah. |
| `is_required` | Ya | `TRUE`/`FALSE` | Step wajib atau opsional. |
| `wait_after_seconds` | Ya | Angka desimal | Delay setelah step. |
| `is_active` | Ya | `TRUE`/`FALSE` | Step aktif dipakai. |

Action valid: `click`, `click_type`, `type`, `press`, `attach_file`, `wait`,
`manual_continue`.

Input source valid: `NONE`, `RUN_CONTROL_ID`, `START_DATE`, `END_DATE`,
`TXT_FILE_PATH`.

Method valid: `coordinate`, `playwright`, `manual`, `assisted`.

### Comparison_Settings

| setting_key | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `use_global_output` | Ya | `TRUE`/`FALSE` | Gunakan output global. |
| `use_global_period` | Ya | `TRUE`/`FALSE` | Gunakan periode global. |

### Attachment_Consolidation

| setting_key | Wajib | Format | Catatan |
| --- | --- | --- | --- |
| `use_global_output` | Ya | `TRUE`/`FALSE` | Gunakan output global. |
| `txt_max_lines` | Ya | Angka lebih dari 0 | Contoh `10000`. |

## 5. Checklist Sebelum Import Konfigurasi

1. Sheet `Outlook_Settings`, `payroll_period` sudah diisi `MM-YYYY`.
2. `mailbox_smtp` adalah email kantor yang valid.
3. `source_folder` Outlook tidak kosong.
4. Attachment extension memakai titik, contoh `.xlsx`.
5. Tidak ada placeholder email template di luar daftar resmi.
6. Semua baris aktif Attendance punya `mdb_path`.
7. `hris_url` berisi URL lengkap.
8. Semua `run_control_id` HRIS aktif tidak kosong.
9. Semua boolean memakai `TRUE` atau `FALSE`.
10. Preview import tidak memiliki error.

## 6. Cara Import Konfigurasi

1. Buka `Settings`.
2. Masuk `Import / Export`.
3. Klik pilih file konfigurasi.
4. Pilih workbook `.xlsx`.
5. Klik `Periksa Konfigurasi`.
6. Bila muncul error, perbaiki workbook terlebih dahulu.
7. Bila hanya warning, baca detailnya dan pastikan aman.
8. Centang konfirmasi jika aplikasi meminta persetujuan.
9. Klik `Terapkan Konfigurasi`.
10. Buka `Module Configuration` dan pastikan module yang diperlukan `Ready`.

## 7. Cara Menjalankan Module

### Attendance

1. Pastikan periode benar.
2. Pilih workflow `HO` atau `BRANCH`.
3. Jalankan validate/check.
4. Klik tombol START.
5. Cek output TXT dan Excel Report.
6. TXT hasil Attendance juga disalin ke folder HRIS sesuai workflow.

### Outlook Revisi

1. Pastikan `Payroll Period` sudah benar, contoh `07-2026`.
2. Jalankan mailbox check.
3. Untuk testing, gunakan mode aman/dry run bila tersedia.
4. Untuk production reply, pastikan mode `SEND` memang sengaja dipakai.
5. Klik tombol START.
6. TXT hasil Outlook Revisi juga disalin ke folder HRIS sesuai workflow.

### HRIS

1. Pastikan folder TXT source mengarah ke folder HRIS yang benar.
2. Pilih workflow `HO` atau `BRANCH`.
3. Pastikan recorder profile HRIS terbaca.
4. Login memakai username dan password yang disimpan di setting.
5. Klik tombol START.
6. Ikuti pause/manual confirmation jika aplikasi meminta lanjut.

### Utilities

1. Pilih fitur `Comparison Result` atau `Attachment Consolidation`.
2. Isi source folder yang sesuai.
3. Pastikan periode benar.
4. Klik START.
5. Cek result summary dan output folder.

## 8. Troubleshooting Cepat

| Pesan / Gejala | Penyebab Umum | Solusi |
| --- | --- | --- |
| `OUTLOOK_PAYROLL_PERIOD_INVALID` | `payroll_period` kosong atau salah format | Isi `Outlook_Settings -> payroll_period` dengan `MM-YYYY`. |
| `OUTLOOK_MAILBOX_INVALID` | Email mailbox tidak valid | Isi `mailbox_smtp` dengan email lengkap. |
| `OUTLOOK_SOURCE_FOLDER_REQUIRED` | Folder sumber Outlook kosong | Isi `source_folder`, contoh `Inbox`. |
| `OUTLOOK_ATTACHMENT_EXTENSION_INVALID` | Extension tanpa titik | Ubah `xlsx` menjadi `.xlsx`. |
| `UNKNOWN_REPLY_TEMPLATE_PLACEHOLDER` | Placeholder template tidak dikenal | Pakai placeholder resmi saja. |
| `ATTENDANCE_SOURCE_PATH_REQUIRED` | Source aktif tanpa MDB path | Isi `mdb_path` atau nonaktifkan baris. |
| `HRIS_URL_INVALID` | URL HRIS tidak lengkap | Isi URL dengan `https://...`. |
| `HRIS_RUN_CONTROL_ID_REQUIRED` | Run control kosong | Isi `run_control_id`. |
| `HRIS CLIC Profile not found` | Recorder profile tidak ditemukan/namanya tidak cocok | Pastikan file JSON ada di Data Root `recorder_profiles\hris`. |

## 9. Catatan Production

- Excel adalah media import/export. Database tetap sumber utama konfigurasi
  aplikasi setelah import berhasil.
- Mengubah value di Settings akan langsung memperbarui database.
- Mengubah Excel tidak mengubah database sampai file Excel diimport ulang.
- Jangan rebuild EXE kecuali memang sedang membuat paket baru untuk production.
- Simpan backup database sebelum mengganti konfigurasi besar.

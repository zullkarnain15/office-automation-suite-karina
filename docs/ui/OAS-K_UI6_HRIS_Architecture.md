# OAS-K UI6 — HRIS Integration Architecture

## Boundary

Alur Unified UI:

`HRISPage → HRISService → HRISAdapter → existing HRIS reader/planner/engine`

`HRISPage` hanya mengelola widget dan typed request/event. Page tidak mengimpor
Playwright, engine HRIS, SQLite, Registry, JSON parser, browser manager, atau file
manager. `HRISService` mengelola konfigurasi read-only, request resolution, audit
job, status event, confirmation gate, dan cancellation. `HRISAdapter` adalah satu-
satunya boundary yang mengimpor reader/planner/engine legacy.

## Configuration strategy

Mode normal memakai SQLite. Saat validation/run, adapter mengekspor subset HRIS
melalui `export_hris_legacy()` ke `TemporaryDirectory`, lalu membacanya memakai
`HRISConfigurationReader`. Workbook sementara bukan konfigurasi aktif, tidak berada
di project/Data Root, dan dibersihkan best-effort.

Advanced / Manual Fallback menerima workbook `.xlsx` untuk satu job. Path hanya
disimpan dalam state page dan tidak menulis SQLite/Global Settings. Browse legacy
tidak tampil sebagai alur utama.

Run Control selalu disimpan dan dipetakan sebagai text. Planner existing mengurutkan
TXT dan active Run Control berdasarkan sequence; `001`, `02`, dan `3` tidak pernah
dikonversi menjadi integer. Job diblokir bila TXT kosong, Run Control kurang, atau
mapping duplikat/ambigu.

## Recorder profile

Persisted reference harus relatif terhadap Data Root dan berada di:

`recorder_profiles/hris/*.json`

Storage validator menolak absolute path, traversal, path di luar recorder profile,
non-JSON, unreadable JSON, dan root selain object. HRIS validator juga memakai safe
payload checker existing dan menolak workflow mismatch. JSON tidak disimpan sebagai
BLOB dan validation tidak mengubah file. Engine menerima absolute runtime override
yang diturunkan dari relative reference; absolute path tidak dipersist.

Record / Calibrate ditampilkan disabled karena recorder calibration belum memiliki
kontrak Unified UI yang cukup aman. Legacy calibrator tidak dihapus.

## Assisted state and intervention

State typed terpusat di `HRISJobState`: IDLE, VALIDATING, READY,
STARTING_BROWSER, WAITING_FOR_LOGIN, NAVIGATING, FILLING_RUN_CONTROL,
FILLING_PERIOD, SELECTING_ATTACHMENT, WAITING_FOR_USER_UPLOAD, RESUMING,
RUNNING_REQUEST, VERIFYING, FILE_COMPLETED, NEXT_FILE, COMPLETED,
CANCEL_REQUESTED, CANCELLED, FAILED, dan PAUSED.

Worker berkomunikasi melalui TaskRunner queue dan `HRISInteractionGate` berbasis
`threading.Event`. Tk callback tidak dipanggil dari worker.

Urutan aman:

1. Engine membuka Edge.
2. Worker masuk WAITING_FOR_LOGIN.
3. User login manual dan menekan Login Selesai — Lanjutkan.
4. Engine menavigasi, mengisi Run Control dan period, lalu memilih TXT.
5. Hook UI6 berjalan tepat setelah attachment dan masuk WAITING_FOR_USER_UPLOAD.
6. User menekan Upload sendiri, menangani popup, lalu kembali ke OAS-K.
7. User menekan Upload Selesai — Lanjutkan.
8. Assisted replay melewati step `upload`, lalu menjalankan `OK after upload → Run → OK`.
9. Existing verifier menentukan sukses; existing file manager hanya memindahkan file
   sukses ke Uploaded pada mode UI6.

Hook `manual_upload_callback` bersifat opsional. Tanpa hook, legacy GUI/engine tetap
memakai perilaku lama. Pada UI6, `upload` dikeluarkan dari replay sehingga tidak ada
double-click atau automatic Upload.

## Cancellation and recovery

Cancellation cooperative diperiksa saat menunggu login dan menunggu manual Upload.
Request cancellation membuka wait event agar worker mencapai safe checkpoint.
Cancellation ketika WAITING_FOR_USER_UPLOAD tidak menjalankan Run dan file tidak
dipindah. Terminal result diselesaikan oleh service; late cancel tidak mengganti
COMPLETED/FAILED/CANCELLED.

UI6 menjalankan engine dengan `move_failed_files=False`. File gagal tetap di source;
tidak dipindahkan ke Uploaded atau Failed oleh jalur UI6. File sukses dipindahkan
hanya setelah manual confirmation, Run, dan verification success. Move failure
tetap tercatat sebagai partial/recovery condition dan tidak memicu auto-upload ulang.

Recovery actions: Open Source, Open Uploaded/Output, Open Process Log, Open Recorder
Profile Folder, Retry as New Job, dan Return to Settings. Tidak ada timer confirmation,
auto-retry, auto-upload ulang, atau source deletion.

## History and security

Job history menyimpan workflow, period, global-period flag, source folder, output,
file counts, relative recorder profile, error summary, dan status transitions.
References mencakup SOURCE_TXT, UPLOADED_TXT, PROCESS_LOG, UPLOAD_REPORT,
UPLOAD_SUMMARY_JSON, dan OUTPUT_FOLDER bila file/folder benar-benar tersedia.
Recorder profile dicatat sebagai metadata reference, bukan output file.

Username, password, cookie, token, clipboard, atau full page content tidak masuk ke
model, request, history, atau log. Login selalu manual pada jalur UI6.

Schema tetap v1 dengan 24 tabel. UI6 tidak mengubah business rule/output HRIS,
Attendance, Outlook, atau Utilities.

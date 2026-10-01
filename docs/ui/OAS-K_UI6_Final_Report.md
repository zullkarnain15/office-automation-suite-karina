# OAS-K Sprint UI6 — Final Report

## Status

**COMPLETED** — acceptance UI6 dipenuhi melalui automated regression dan safe
mock/local acceptance. Pekerjaan berhenti setelah UI6; UI7 tidak dimulai.

## HRIS page structure

HRIS page aktif memakai UI5B visual foundation dan responsive scroll:

1. Active Configuration | Upload Source
2. Period & Workflow | Run Control Summary
3. Assisted Recorder Profile | Validation & Run
4. Manual Intervention full width
5. Progress | Batch Result
6. Process Log full width

Minimum 1000×640 menjadi satu kolom; target 1180×720 menjadi dua kolom. Advanced
legacy fallback tersembunyi secara default dan session-only.

## Architecture and engine API

`HRISPage → HRISService → HRISAdapter → HRISConfigurationReader / HRISUploadJobManager / HRISFullUploadEngine`

Engine existing menerima hook backward-compatible baru:

- `manual_login_callback`
- `manual_upload_callback`
- `profile_path_override`
- `move_failed_files=False` pada UI6

`HRISUploadPageHandler` memanggil manual Upload hook setelah TXT attached dan sebelum
jalur Upload. Assisted replay melewati step `upload` pada UI6, kemudian melanjutkan
`ok_after_upload`, `run`, dan `ok_after_run`. Legacy caller tanpa hook tidak berubah.

SQLite adalah source normal. Adapter membuat workbook HRIS legacy sementara hanya
saat validation/run; fallback workbook manual hanya untuk satu job. Run Control ID
tetap text dan leading zero terjaga.

Recorder profile dipersist sebagai relative reference di
`recorder_profiles/hris/*.json`. Absolute/traversal/non-JSON/invalid JSON/workflow
mismatch ditolak. Tidak ada JSON BLOB atau credential.

## Assisted behavior

State machine typed dan thread-safe interaction gate menangani manual login,
post-attachment pause, manual Upload confirmation, upload failure, resume, serta
cooperative cancellation. Tombol lanjut hanya aktif pada state yang sesuai. Tidak
ada timer yang menganggap Upload sukses.

File sukses dipindahkan oleh file manager existing hanya sesudah verification.
Jalur UI6 tidak memindahkan file gagal. Job audit menyimpan PENDING/RUNNING/PAUSED/
terminal, status event, source references, artifacts yang tersedia, period, workflow,
profile reference, dan recovery summary.

## Test results

| Pemeriksaan | Hasil |
|---|---:|
| UI6 HRIS targeted | 27 passed |
| Existing HRIS regression | 37 passed |
| `py -m pytest tests/ui` | 201 passed, 1 optional Tk skip |
| Database + storage + recovery + UI | 443 passed, 1 optional Tk skip |
| Attendance + Outlook engine regression | 84 passed |
| `py -m pytest` | 579 passed, 1 optional Tk skip |
| Ruff UI scope | passed |
| Schema | v1, 24 tables |

Optional skip adalah real-Tk fixture yang bergantung pada availability Tcl/display;
source launcher dan dedicated HRIS Tk zero-side-effect smoke berhasil.

## Manual/smoke acceptance

Fake Registry source launcher hidup tanpa membuat suggested Data Root atau database.
HRIS construction smoke lulus pada dua ukuran dan tiga scaling. Mock engine lifecycle
membuktikan login pause, attachment pause, manual Upload resume, HRIS date conversion,
dan failed-file move guard tanpa membuka Edge/production HRIS.

Upload **tidak ditekan otomatis** pada jalur default UI6. Credential **tidak disimpan
atau diambil**. Utilities belum terhubung. Legacy `HRISUploadGUI` tetap importable dan
Assisted Mode lama tidak dihapus.

## File baru

- `ui/hris_models.py`
- `ui/adapters/hris_adapter.py`
- `ui/services/hris_service.py`
- `tests/ui/hris/__init__.py`
- `tests/ui/hris/test_hris_service.py`
- `tests/ui/hris/test_hris_page_contract.py`
- `tests/ui/adapters/test_hris_adapter.py`
- `tests/ui/services/test_hris_service.py`
- `docs/ui/OAS-K_UI6_HRIS_Architecture.md`
- `docs/ui/OAS-K_UI6_HRIS_Manual_Checklist.md`
- `docs/ui/OAS-K_UI6_Final_Report.md`

## File diubah

- `ui/pages/hris_page.py`
- `ui/services/service_container.py`
- `ui/services/protocols.py`
- `ui/services/__init__.py`
- `hris/uploader.py`
- `hris/batch_uploader.py`
- `hris/assisted_replay.py`
- `hris/engine.py`
- `hris/file_manager.py`
- `tests/ui/test_boundaries.py`

UI6 tidak mengubah `main.py`, schema v1, `shared/config_manager.py`, Attendance/
Outlook business engine, `utilities/**`, workbook/template resmi, assets, PyInstaller,
build, atau dist. Perubahan lama di dirty worktree tetap dipertahankan dan tidak
di-reset.

## Technical debt

- Real Edge/PeopleSoft iframe/popup certification memerlukan mock page yang lebih
  representatif atau staging HRIS berizin; production tidak digunakan saat acceptance.
- Existing engine membuat artifact folder sebelum browser start setelah preflight;
  ini benar untuk confirmed job, tetapi dry-run artifact preview terpisah belum ada.
- Progress engine internal belum mengekspos setiap micro-stage/file completion sebagai
  native callback; UI menampilkan stage aman dan count yang tersedia.
- Recorder calibrator belum mempunyai typed Unified UI contract, sehingga tombol
  Record / Calibrate sengaja disabled.
- Browser cancellation setelah Run dikirim tetap menunggu safe stage; tidak ada forced
  thread/browser termination.

## Rekomendasi UI7

Integrasikan Utilities melalui Page/Service/Adapter typed tanpa mengubah output
contract: Comparison Result dan Attachment Consolidation harus validation-first,
job-audited, cancellable pada safe checkpoint, dan memakai visual foundation UI5B.
Mulai hanya setelah UI7 diotorisasi eksplisit.

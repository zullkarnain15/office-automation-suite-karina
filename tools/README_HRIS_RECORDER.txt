OAS-K HRIS Recorder & DOM Scanner Tool
======================================

Tujuan tool
-----------
Tool ini dipakai di komputer kantor untuk membuka Microsoft Edge, login HRIS manual,
lalu melakukan scan DOM pada halaman Overtime Upload Attendance. Hasil scan dipakai
untuk menganalisis selector asli HRIS secara aman.

Cara menjalankan
----------------
1. Buka terminal dari root project OAS-K.
2. Jalankan:
   py tools/hris_recorder.py
3. Masukkan HRIS URL saat diminta.
4. Microsoft Edge akan terbuka.
5. Login HRIS secara manual dan navigasi sampai halaman Overtime Upload Attendance.
6. Setelah halaman siap, kembali ke terminal dan tekan ENTER.

Apa yang direkam
----------------
- Page title.
- URL yang sudah disanitasi tanpa query string dan fragment/hash.
- Info frame/iframe.
- Metadata input, button, link, dan select.
- Candidate locator untuk membantu analisis selector.
- Text modal/dialog yang terlihat dan tombol di dalam modal.
- Screenshot halaman saat scan.
- Traceback jika terjadi error.

Apa yang tidak direkam
----------------------
- Password.
- Cookies.
- Session storage.
- Local storage.
- Token.
- Authorization header.
- Value asli input username/password.
- Value dari hidden input.
- Playwright storage_state.
- Persistent browser profile.

Lokasi output
-------------
Setiap run membuat folder baru:

diagnostics/hris_recorder/YYYYMMDD_HHMMSS/

Isi output:
- hris_dom_scan.json
- screenshot.png
- recorder_log.txt
- exception_traceback.txt jika terjadi error

Instruksi kirim balik
---------------------
ZIP folder output run terbaru:

diagnostics/hris_recorder/YYYYMMDD_HHMMSS

Kirim file ZIP tersebut untuk dianalisis. JSON dirancang aman untuk dikirim balik
karena tidak menyimpan cookies, storage, token, password, atau value input.

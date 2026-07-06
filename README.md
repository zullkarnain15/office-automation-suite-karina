# Office Automation Suite - Karina (OAS-K)

Office Automation Suite - Karina adalah aplikasi desktop Windows untuk membantu proses administrasi kantor secara modular.

## Module Status

### Attendance Module
Status: Release Candidate

Fitur:
- Membaca Attendance Configuration Excel
- Membaca MDB Attendance
- Workflow Head Office (HO) dan Branch
- Pairing attendance berdasarkan NIK + tanggal
- Jam masuk = tap paling awal
- Jam keluar = tap paling akhir
- Validasi data sebelum TXT HRIS
- Generate HRIS TXT
- Generate Excel Report
- Generate Process.log
- Generate summary.json

## Attendance Output Format

Format TXT HRIS:

```text
"MM/DD/YYYY","NIK","MM/DD/YYYY","HH:MM","MM/DD/YYYY","HH:MM"
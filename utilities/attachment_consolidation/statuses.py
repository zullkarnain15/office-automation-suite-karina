"""Central status definitions used by the consolidation audit artifacts."""

FILE_READY = "READY"
FILE_SUCCESS = "SUCCESS"
FILE_PARTIAL = "PARTIAL_SUCCESS"
FILE_FAILED = "FAILED"
FILE_NO_VALID = "NO_VALID_RECORD"
FILE_UNSUPPORTED = "UNSUPPORTED_FORMAT"
FILE_TEMPORARY = "TEMPORARY_SKIPPED"
FILE_HIDDEN_SYSTEM = "HIDDEN_SYSTEM_SKIPPED"
FILE_SYMLINK = "SYMLINK_SKIPPED"
FILE_OUTPUT_SKIPPED = "OUTPUT_SKIPPED"
FILE_CANCELLED = "CANCELLED"

ROW_VALID = "VALID"

STATUS_GUIDE: tuple[tuple[str, str, str], ...] = (
    (FILE_READY, "File", "File siap diproses."),
    (FILE_SUCCESS, "File", "Semua record yang terbaca valid."),
    (
        FILE_PARTIAL,
        "File",
        "File menghasilkan record valid dan juga record invalid.",
    ),
    (FILE_FAILED, "File", "File tidak dapat dibaca atau diproses."),
    (FILE_NO_VALID, "File", "File terbaca tetapi tidak memiliki record valid."),
    (FILE_UNSUPPORTED, "File", "Format file ditemukan tetapi tidak didukung."),
    (FILE_TEMPORARY, "File", "File sementara seperti ~$... dilewati."),
    (
        FILE_HIDDEN_SYSTEM,
        "File",
        "File atau folder hidden/system dilewati untuk keamanan.",
    ),
    (FILE_SYMLINK, "File", "Symbolic link/reparse point tidak diikuti."),
    (FILE_OUTPUT_SKIPPED, "File", "Artifact output lama tidak dipindai ulang."),
    (FILE_CANCELLED, "Process", "Proses dibatalkan pada checkpoint yang aman."),
    (ROW_VALID, "Row", "Record lolos validasi dan ditulis ke TXT HRIS."),
    ("COLUMN_COUNT", "Row", "Jumlah kolom bukan enam."),
    ("NIK_REQUIRED", "Row", "NIK kosong."),
    ("DATE_FORMAT", "Row", "Tanggal kosong atau formatnya tidak valid."),
    ("TIME_FORMAT", "Row", "Waktu kosong atau formatnya tidak valid."),
    ("MISSING_REQUIRED_COLUMN", "File", "Kolom Excel wajib tidak ditemukan."),
    ("ATTACHMENT_STRUCTURE_INVALID", "File", "Struktur attachment tidak valid."),
    ("FILE_READ_FAILED", "File", "Isi file tidak dapat dibaca."),
)

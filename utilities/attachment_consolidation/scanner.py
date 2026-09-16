"""Non-destructive recursive scanner for consolidation source files."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from threading import Event

from utilities.attachment_consolidation.models import (
    MODE_EXCEL,
    MODE_TXT,
    ConsolidationRequest,
    ConsolidationScan,
    ScannedAttachment,
    check_cancelled,
)
from utilities.attachment_consolidation.statuses import (
    FILE_HIDDEN_SYSTEM,
    FILE_OUTPUT_SKIPPED,
    FILE_READY,
    FILE_SYMLINK,
    FILE_TEMPORARY,
    FILE_UNSUPPORTED,
)


EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}
EXCEL_DISCOVERY_EXTENSIONS = EXCEL_EXTENSIONS | {".xls"}
TXT_EXTENSIONS = {".txt"}
OUTPUT_FOLDER_NAMES = {"attachment_consolidation"}
OUTPUT_FILE_NAMES = {"process.log", "summary.json"}


class AttachmentScanner:
    """Discover candidate files without following risky links."""

    def scan(
        self,
        request: ConsolidationRequest,
        cancel_event: Event | None = None,
    ) -> ConsolidationScan:
        self.validate_request(request)
        root = request.source_root.resolve()
        files: list[ScannedAttachment] = []
        warnings: list[str] = []
        self._walk(
            root=root,
            folder=root,
            recursive=request.scan_subfolders,
            mode=request.mode,
            files=files,
            warnings=warnings,
            cancel_event=cancel_event,
        )
        files.sort(key=lambda item: item.relative_path.casefold())
        return ConsolidationScan(
            request_fingerprint=request.fingerprint(),
            files=files,
            warnings=warnings,
        )

    @staticmethod
    def validate_request(request: ConsolidationRequest) -> None:
        if request.mode not in {MODE_EXCEL, MODE_TXT}:
            raise ValueError("Mode harus Merge Excel Attachment atau Merge TXT Attachment.")
        if request.workflow not in {"HO", "Branch"}:
            raise ValueError("Workflow harus HO atau Branch.")
        if not request.source_root.exists():
            raise FileNotFoundError(
                f"Source Root tidak ditemukan: {request.source_root}"
            )
        if not request.source_root.is_dir():
            raise NotADirectoryError(
                f"Source Root bukan folder: {request.source_root}"
            )

        source = request.source_root.resolve()
        output = request.output_root.resolve()
        if output == source or source in output.parents:
            raise ValueError(
                "Output Root tidak boleh sama dengan atau berada di dalam "
                "Source Root."
            )

    def _walk(
        self,
        root: Path,
        folder: Path,
        recursive: bool,
        mode: str,
        files: list[ScannedAttachment],
        warnings: list[str],
        cancel_event: Event | None,
    ) -> None:
        check_cancelled(cancel_event)
        try:
            with os.scandir(folder) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name.casefold())
        except OSError as error:
            warnings.append(f"Tidak dapat membaca folder {folder}: {error}")
            return

        for entry in entries:
            check_cancelled(cancel_event)
            path = Path(entry.path)
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            attributes = getattr(metadata, "st_file_attributes", 0)
            linked = stat.S_ISLNK(metadata.st_mode) or bool(
                attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            )
            try:
                is_file = entry.is_file() if linked else stat.S_ISREG(metadata.st_mode)
            except OSError:
                is_file = False
            size = None if linked else metadata.st_size
            relative = self._relative(path, root)
            if self._is_output_artifact(path):
                if is_file:
                    files.append(
                        self._item(path, relative, FILE_OUTPUT_SKIPPED, "Artifact output lama.", size=size)
                    )
                continue
            if linked:
                if is_file:
                    files.append(
                        self._item(path, relative, FILE_SYMLINK, "Symlink/reparse point.")
                    )
                continue
            if path.name.startswith(".") or attributes & (
                getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
                | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 0x4)
            ):
                if is_file and self._is_discovery_extension(path, mode):
                    files.append(
                        self._item(
                            path,
                            relative,
                            FILE_HIDDEN_SYSTEM,
                            "File hidden/system.",
                            size=size,
                        )
                    )
                continue
            if stat.S_ISDIR(metadata.st_mode):
                if recursive:
                    self._walk(
                        root,
                        path,
                        recursive,
                        mode,
                        files,
                        warnings,
                        cancel_event,
                    )
                continue
            if not is_file or not self._is_discovery_extension(path, mode):
                continue
            if path.name.startswith("~$"):
                files.append(
                    self._item(path, relative, FILE_TEMPORARY, "File sementara Excel.", size=size)
                )
                continue
            if mode == MODE_EXCEL and path.suffix.casefold() == ".xls":
                files.append(
                    self._item(
                        path,
                        relative,
                        FILE_UNSUPPORTED,
                        "Format .xls tidak didukung; simpan ulang sebagai .xlsx.",
                        size=size,
                    )
                )
                continue
            files.append(self._item(path, relative, FILE_READY, size=size))

    @staticmethod
    def _item(
        path: Path,
        relative: str,
        status: str,
        reason: str = "",
        *,
        size: int | None = None,
    ) -> ScannedAttachment:
        if size is None:
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
        return ScannedAttachment(
            path=path,
            relative_path=relative,
            extension=path.suffix.casefold(),
            size_bytes=size,
            status=status,
            reason=reason,
        )

    @staticmethod
    def _relative(path: Path, root: Path) -> str:
        try:
            return str(path.relative_to(root))
        except ValueError:
            return path.name

    @staticmethod
    def _is_discovery_extension(path: Path, mode: str) -> bool:
        extension = path.suffix.casefold()
        if mode == MODE_EXCEL:
            return extension in EXCEL_DISCOVERY_EXTENSIONS
        return extension in TXT_EXTENSIONS

    @staticmethod
    def _is_output_artifact(path: Path) -> bool:
        name = path.name.casefold()
        return (
            name in OUTPUT_FOLDER_NAMES
            or name in OUTPUT_FILE_NAMES
            or name.startswith("attachment_consolidation_")
        )

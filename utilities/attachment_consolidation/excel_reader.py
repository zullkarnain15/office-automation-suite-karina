"""Excel attachment reader using the established Outlook mapping."""

from pathlib import Path

from outlook.parser import OutlookAttachmentParser
from outlook.parser import ParseResult


class ConsolidationExcelReader:
    def __init__(self, parser: OutlookAttachmentParser | None = None) -> None:
        self.parser = parser or OutlookAttachmentParser()

    def read(self, path: Path) -> ParseResult:
        return self.parser.parse_ho_excel(path)

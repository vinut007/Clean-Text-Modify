"""Export cleaned data to XLSX / CSV."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExportResult:
    data: bytes


def export(fmt: str, columns: list, rows: list, name: str = "output") -> ExportResult:
    """Export rows to XLSX (default) or CSV. Returns ExportResult with .data bytes."""
    if fmt == "csv":
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)
        data = buf.getvalue().encode("utf-8")
        return ExportResult(data=data)

    # Default: xlsx via openpyxl
    try:
        from openpyxl import Workbook
    except ImportError:
        # Fallback: write CSV with .xlsx extension if openpyxl missing
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)
        return ExportResult(data=buf.getvalue().encode("utf-8"))

    wb = Workbook()
    ws = wb.active
    ws.title = name[:31] or "Sheet1"
    from backend.core.annotate import _sanitize_cell

    ws.append([_sanitize_cell(v) if isinstance(v, str) else v
               for v in columns])
    for row in rows:
        ws.append([_sanitize_cell(v) if isinstance(v, str) else v
                   for v in row])
    import io

    buf = io.BytesIO()
    wb.save(buf)
    return ExportResult(data=buf.getvalue())


def detect_format(path, raw=None):
    """Detect file format from extension. Returns 'excel', 'csv', 'txt', 'json'."""
    from pathlib import Path

    suffix = Path(path).suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return "excel"
    if suffix == ".csv":
        return "csv"
    if suffix in (".txt", ".tsv"):
        return "txt"
    if suffix == ".json":
        return "json"
    return "txt"


# Excel's hard limit per sheet (leaves the 1 header row free)
XLSX_MAX_ROWS_PER_SHEET = 1_048_576


class StreamingXlsxWriter:
    """Append rows to an .xlsx with constant memory (openpyxl write-only).

    Rolls over to a fresh sheet (header repeated) before the Excel
    1,048,576-row limit, so a 10M-row export stays a single valid file.
    """

    def __init__(self, path, columns, max_rows_per_sheet: int = XLSX_MAX_ROWS_PER_SHEET):
        from openpyxl import Workbook

        self.path = str(path)
        self.columns = list(columns)
        # at least 1 data row per sheet
        self.max = max(1, int(max_rows_per_sheet))
        self.wb = Workbook(write_only=True)
        self.ws = None
        self.n = 0
        self.sheets = 0
        self.rows_written = 0

    def _new_sheet(self) -> None:
        from backend.core.annotate import _sanitize_cell

        self.ws = self.wb.create_sheet()
        self.ws.append([_sanitize_cell(v) if isinstance(v, str) else v
                        for v in self.columns])
        self.n = 0
        self.sheets += 1

    def add_row(self, row) -> None:
        if self.ws is None or self.n >= self.max:
            self._new_sheet()
        from backend.core.annotate import _sanitize_cell

        # write-boundary gate: never hand lxml a control char / lone surrogate
        self.ws.append([_sanitize_cell(v) if isinstance(v, str) else v
                        for v in row])
        self.n += 1
        self.rows_written += 1

    def close(self) -> None:
        if self.ws is None:
            self._new_sheet()
        self.wb.save(self.path)

class StreamingCsvWriter:
    """Append rows to a .csv with constant memory (same add_row API)."""

    def __init__(self, path, columns):
        import csv

        self.f = open(str(path), "w", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        from backend.core.annotate import _sanitize_cell

        self.w.writerow([_sanitize_cell(v) if isinstance(v, str) else v
                         for v in columns])
        self.rows_written = 0

    def add_row(self, row) -> None:
        from backend.core.annotate import _sanitize_cell

        self.w.writerow([_sanitize_cell(v) if isinstance(v, str) else v
                         for v in row])
        self.rows_written += 1

    def close(self) -> None:
        self.f.close()

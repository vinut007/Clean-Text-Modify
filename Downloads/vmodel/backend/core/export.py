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
    ws.append(columns)
    for row in rows:
        ws.append(row)
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

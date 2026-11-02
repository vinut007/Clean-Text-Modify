"""Ingest: read Excel / CSV / TXT / JSON into columns + rows."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class TableData:
    columns: list[str]
    rows: list[list]


def ingest(fpath, raw=None, fmt=None) -> TableData:
    """Read file into columns + rows.

    fmt: None (auto-detect), 'excel', 'csv', 'txt', 'json'
    """
    fpath = Path(fpath)
    if fmt is None:
        fmt = detect_format(fpath)

    if fmt == "excel":
        df = pd.read_excel(fpath, header=0)
    elif fmt == "csv":
        df = pd.read_csv(fpath, encoding="utf-8")
    elif fmt == "txt":
        # Tab-separated or comma-separated
        df = pd.read_csv(fpath, encoding="utf-8", sep=None, engine="python")
    elif fmt == "json":
        df = pd.read_json(fpath, encoding="utf-8")
    else:
        df = pd.read_excel(fpath, header=0)

    columns = [str(c) for c in df.columns.tolist()]
    rows = df.where(pd.notna(df), None).values.tolist()
    # Normalize None cells
    rows = [[cell if cell is not None else None for cell in row] for row in rows]
    return TableData(columns=columns, rows=rows)


def detect_format(path, raw=None):
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
    return "excel"

"""Ingest: read Excel / CSV / TXT / JSON / Access (.accdb, .mdb) into columns + rows."""
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

    fmt: None (auto-detect), 'excel', 'csv', 'txt', 'json', 'access'
    """
    fpath = Path(fpath)
    if fmt is None:
        fmt = detect_format(fpath)

    if fmt == "excel":
        df = pd.read_excel(fpath, header=0)
    elif fmt == "csv":
        # Read everything as raw text: numeric inference turns ID columns
        # into floats (977208 -> 977208.0) whenever the column has blanks.
        df = pd.read_csv(fpath, encoding="utf-8", dtype=str,
                         keep_default_na=False, na_filter=False)
    elif fmt == "txt":
        # Tab-separated or comma-separated
        df = pd.read_csv(fpath, encoding="utf-8", sep=None, engine="python",
                         dtype=str, keep_default_na=False, na_filter=False)
    elif fmt == "json":
        df = pd.read_json(fpath, encoding="utf-8")
    elif fmt == "access":
        raise ValueError(
            "Access files need a table name — use ingest_access(path, table) "
            "or list_access_tables(path) first."
        )
    else:
        df = pd.read_excel(fpath, header=0)

    columns = [str(c) for c in df.columns.tolist()]
    rows = df.where(pd.notna(df), None).values.tolist()
    # Normalize None cells
    rows = [[cell if cell is not None else None for cell in row] for row in rows]
    return TableData(columns=columns, rows=rows)


# ---------------------------------------------------------------------------
# Microsoft Access (.accdb / .mdb) via pyodbc + ACE ODBC driver
# ---------------------------------------------------------------------------

_ACCESS_DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"


def _access_connect(path):
    import pyodbc
    return pyodbc.connect(
        f"DRIVER={{{_ACCESS_DRIVER}}};DBQ={Path(path).resolve()};"
    )


def _ident(name: str) -> str:
    """Bracket-quote an Access identifier (] escaped as ]])."""
    return "[" + str(name).replace("]", "]]") + "]"


def list_access_tables(path) -> list[tuple[str, int]]:
    """Analyse an Access database: return [(table_name, row_count), ...].

    System tables (MSys*, ~*, temp*) are filtered out; sorted by name so
    interactive numbering is stable.
    """
    conn = _access_connect(path)
    try:
        cur = conn.cursor()
        names = []
        for t in cur.tables(tableType="TABLE"):
            name = str(t.table_name)
            if name.startswith(("MSys", "~", "temp")):
                continue
            names.append(name)
        out: list[tuple[str, int]] = []
        for name in sorted(names, key=str.lower):
            try:
                n = cur.execute(f"SELECT COUNT(*) FROM {_ident(name)}").fetchone()[0]
            except Exception:
                n = -1
            out.append((name, int(n)))
        return out
    finally:
        conn.close()


def _access_cell(v):
    """Convert a pyodbc value into a cell openpyxl/pandas can export."""
    import datetime as _dt
    import decimal as _de
    if v is None:
        return None
    if isinstance(v, _de.Decimal):
        return float(v)
    if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v).decode("utf-8", errors="replace")
    return v


def ingest_access(path, table: str) -> TableData:
    """Read one Access table into columns + rows."""
    conn = _access_connect(path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {_ident(table)}")
        columns = [str(d[0]) for d in (cur.description or [])]
        rows = [[_access_cell(v) for v in r] for r in cur.fetchall()]
        return TableData(columns=columns, rows=rows)
    finally:
        conn.close()


def access_peek(path, table: str, n: int = 5) -> tuple[list[str], list[list]]:
    """Columns + first n rows of an Access table (for preview) without
    loading the whole table — used before the streaming pipeline runs."""
    conn = _access_connect(path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {_ident(table)}")
        columns = [str(d[0]) for d in (cur.description or [])]
        rows = [[_access_cell(v) for v in r] for r in cur.fetchmany(n)]
        return columns, rows
    finally:
        conn.close()


def iter_access_rows(path, table: str, chunk_size: int = 50_000):
    """Yield row-chunks (lists of lists) from an Access table.

    Memory stays bounded at ~chunk_size rows no matter how large the table
    is; each yield is one fetchmany() round-trip. Two passes over the data
    (scan, then apply) simply call this twice.
    """
    conn = _access_connect(path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {_ident(table)}")
        while True:
            batch = cur.fetchmany(chunk_size)
            if not batch:
                break
            yield [[_access_cell(v) for v in r] for r in batch]
    finally:
        conn.close()


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
    if suffix in (".accdb", ".mdb"):
        return "access"
    return "excel"

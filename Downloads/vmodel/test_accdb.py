"""Access (.accdb / .mdb) ingest test — analyse tables, pick one, mode-1 clean.

Fixture creation needs pywin32 + the ACE OLEDB provider (ADOX.Catalog is the
only reliable way to create a new .accdb); reading needs pyodbc + the Access
ODBC driver — the same path production uses. Skips when any is missing.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

try:
    import pyodbc
    if "Microsoft Access Driver (*.mdb, *.accdb)" not in pyodbc.drivers():
        print("RESULT: SKIP — Access ODBC driver not installed")
        sys.exit(0)
except ImportError:
    print("RESULT: SKIP — pyodbc not installed")
    sys.exit(0)

try:
    import win32com.client as _w
except ImportError:
    print("RESULT: SKIP — pywin32 not installed (needed to create test .accdb)")
    sys.exit(0)

from backend.core.ingest import (  # noqa: E402
    detect_format,
    ingest_access,
    list_access_tables,
)
from backend.core.clean import CleanOptions, clean_cell  # noqa: E402

db = Path(tempfile.gettempdir()) / "vmodel_accdb_test.accdb"
if db.exists():
    db.unlink()

# create a fresh .accdb (ADOX + ACE OLEDB — ODBC refuses to create files)
try:
    cat = _w.Dispatch("ADOX.Catalog")
    cat.Create("Provider=Microsoft.ACE.OLEDB.12.0;Data Source=" + str(db))
except Exception as e:
    print(f"RESULT: SKIP — cannot create test .accdb ({e})")
    sys.exit(0)

conn = _w.Dispatch("ADODB.Connection")
conn.Open("Provider=Microsoft.ACE.OLEDB.12.0;Data Source=" + str(db))
conn.Execute("CREATE TABLE Customers (ID LONG, Name TEXT(50), Notes TEXT(255))")
conn.Execute(
    "INSERT INTO Customers VALUES (1, 'Jos\u00c3\u00a9 M\u00c3\u00bcller', 'caf\u00e9 r\u00e9sum\u00e9')"
)
conn.Execute("CREATE TABLE Orders (ID LONG, Item TEXT(50))")
conn.Execute("INSERT INTO Orders VALUES (1, 'widget')")
conn.Close()

fails = []

# format detection
if detect_format(db) != "access":
    fails.append(f"detect_format: {detect_format(db)!r} != 'access'")

# analyse: user tables + row counts, sorted, system tables filtered
tables = list_access_tables(db)
names = [n for n, _ in tables]
if names != ["Customers", "Orders"]:
    fails.append(f"tables: {names!r}")
counts = dict(tables)
if counts.get("Customers") != 1 or counts.get("Orders") != 1:
    fails.append(f"row counts: {counts!r}")

# load the chosen table
td = ingest_access(db, "Customers")
if td.columns != ["ID", "Name", "Notes"]:
    fails.append(f"columns: {td.columns!r}")
if len(td.rows) != 1:
    fails.append(f"rows: {td.rows!r}")
else:
    name_cell = td.rows[0][1]
    notes_cell = td.rows[0][2]
    # mode-1 defaults: mojibake fixed, accents folded
    opts = CleanOptions(
        fix_mojibake=True,
        fold_accents=True,
        normalize_invisible=True,
        fold_symbols=True,
        collapse_punctuation=True,
        keep_emoji=False,
        fold_scripts=False,
        transliterate_columns=set(),
    )
    got_name = clean_cell(name_cell, opts, "Name").cleaned
    got_notes = clean_cell(notes_cell, opts, "Notes").cleaned
    if got_name != "Jose Muller":
        fails.append(f"name not cleaned: {name_cell!r} -> {got_name!r}")
    if got_notes != "cafe resume":
        fails.append(f"notes not cleaned: {notes_cell!r} -> {got_notes!r}")

# ingest() without a table must refuse clearly
from backend.core.ingest import ingest  # noqa: E402
try:
    ingest(db, fmt="access")
    fails.append("ingest(access) without table did not raise")
except ValueError:
    pass

try:
    db.unlink()
except OSError:
    pass

if fails:
    print("RESULT: FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("RESULT: PASS — Access .accdb analyse + table pick + mode-1 clean")

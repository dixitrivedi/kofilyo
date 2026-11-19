"""Where Kofilyo keeps its data: a Google Sheet (online) or a local SQLite file (laptop).

Both stores expose the same two calls, `read(table)` and `write(table, df)`, which load and save a
whole table as a DataFrame. The data is small (a few rows a day), so whole-table writes are fine and
keep the Google Sheet tidy: one tab per table, one row per record, a header row on top.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pandas as pd

# table -> {column: kind}; kind is int, float, str or date (stored as YYYY-MM-DD text)
TABLES: dict[str, dict[str, str]] = {
    "products": {"id": "int", "name": "str", "category": "str", "price": "float", "active": "int", "deleted": "int"},
    "sales": {"id": "int", "sale_date": "date", "product_id": "int", "product_name": "str", "quantity": "int",
              "unit_price": "float"},
    "expenses": {"id": "int", "expense_date": "date", "item": "str", "quantity": "float", "unit": "str",
                 "amount": "float", "notes": "str"},
    # rent, salaries, electricity...; spread "month" = shared evenly over that month's days, "day" = that day only
    "running_costs": {"id": "int", "cost_date": "date", "name": "str", "amount": "float", "spread": "str",
                      "notes": "str"},
    # how each day's takings came in
    "payments": {"id": "int", "pay_date": "date", "cash": "float", "upi": "float", "card": "float"},
    # what goes into one cup of each drink
    "recipes": {"id": "int", "product_id": "int", "product_name": "str", "item": "str", "quantity": "float",
                "unit": "str"},
}


class StorageError(RuntimeError):
    """A problem reaching the data store, worded for the person using the app."""


def coerce(table: str, df: pd.DataFrame) -> pd.DataFrame:
    """Give a frame exactly the table's columns, in order, with clean types."""
    out = pd.DataFrame(index=df.index)
    for col, kind in TABLES[table].items():
        s = df[col] if col in df.columns else pd.Series([None] * len(df), index=df.index, dtype=object)
        if kind == "int":
            out[col] = pd.to_numeric(s, errors="coerce").fillna(0).astype(int)
        elif kind == "float":
            out[col] = pd.to_numeric(s, errors="coerce").fillna(0.0).astype(float)
        elif kind == "date":
            # ISO text from the app; tolerate dates someone typed into the sheet by hand (e.g. 13/11/2026)
            parsed = pd.to_datetime(s.astype(str).str.strip(), errors="coerce", format="mixed", dayfirst=True)
            out[col] = parsed.dt.strftime("%Y-%m-%d")
        else:
            out[col] = s.where(s.notna(), "").astype(str).replace({"nan": "", "None": ""}).str.strip()
    if "id" in out.columns:
        out = out[out["id"] > 0]
    date_cols = [c for c, k in TABLES[table].items() if k == "date"]
    if date_cols:
        out = out.dropna(subset=date_cols)
    return out.reset_index(drop=True)


def empty(table: str) -> pd.DataFrame:
    return coerce(table, pd.DataFrame(columns=list(TABLES[table])))


# --------------------------------------------------------------- local SQLite
class SQLiteStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.label = f"Local file: {self.path}"

    def _conn(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def read(self, table: str) -> pd.DataFrame:
        with self._conn() as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if not exists:
                return empty(table)
            return coerce(table, pd.read_sql_query(f'SELECT * FROM "{table}"', conn))

    def write(self, table: str, df: pd.DataFrame) -> None:
        with self._conn() as conn:
            coerce(table, df).to_sql(table, conn, if_exists="replace", index=False)

    def snapshot(self, table: str, name: str) -> str:
        """Copy a table to a new table called `name` (made unique). Returns the name used."""
        with self._conn() as conn:
            taken = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            name = _unique(name, taken)
            conn.execute(f'CREATE TABLE "{name}" AS SELECT * FROM "{table}"')
        return name


# --------------------------------------------------------------- Google Sheet
class SheetsStore:
    """One worksheet (tab) per table inside a single Google Sheet."""

    CACHE_SECONDS = 300  # re-read the sheet after 5 minutes, so hand edits in Google Sheets show up

    def __init__(self, spreadsheet, client_email: str = ""):
        self.sh = spreadsheet
        self.client_email = client_email
        self.label = f"Google Sheet: {getattr(spreadsheet, 'title', 'connected')}"
        self._cache: dict[str, tuple[float, pd.DataFrame, int]] = {}
        self._worksheets: dict[str, object] = {}
        self._lock = threading.RLock()

    @classmethod
    def from_settings(cls, settings) -> "SheetsStore":
        try:
            import gspread
        except ImportError as exc:
            raise StorageError("The gspread package is missing. Add it to requirements.txt "
                               "(or run: pip install gspread).") from exc
        try:
            account = dict(settings["service_account"])
            ref = str(settings["spreadsheet"]).strip()
        except (KeyError, TypeError) as exc:
            raise StorageError("The [gsheets] secrets need a `spreadsheet` link and a "
                               "[gsheets.service_account] section. See secrets.toml.example.") from exc
        email = account.get("client_email", "the service account")
        try:
            gc = gspread.service_account_from_dict(account)
            sh = gc.open_by_url(ref) if ref.startswith("http") else gc.open_by_key(ref)
        except gspread.exceptions.SpreadsheetNotFound as exc:
            raise StorageError(f"Can't open the Google Sheet. Share it with {email} as an Editor "
                               "and check the link in your secrets.") from exc
        except gspread.exceptions.APIError as exc:
            raise StorageError(f"Google refused access to the sheet ({exc}). Share it with {email} as an "
                               "Editor and make sure the Google Sheets API is enabled.") from exc
        except Exception as exc:
            raise StorageError(f"Couldn't connect to Google Sheets: {exc}") from exc
        return cls(sh, email)

    def _ws(self, table: str):
        if table in self._worksheets:
            return self._worksheets[table]
        try:
            ws = self.sh.worksheet(table)
        except Exception as exc:
            if type(exc).__name__ != "WorksheetNotFound":
                raise
            cols = list(TABLES[table])
            ws = self.sh.add_worksheet(title=table, rows=200, cols=len(cols))
            ws.update(values=[cols], range_name="A1", value_input_option="RAW")
        self._worksheets[table] = ws
        return ws

    def _read(self, table: str) -> pd.DataFrame:
        hit = self._cache.get(table)
        if hit and time.monotonic() - hit[0] < self.CACHE_SECONDS:
            return hit[1].copy()
        values = self._ws(table).get_all_values()
        if values:
            header = [h.strip() for h in values[0]]
            rows = [r + [""] * (len(header) - len(r)) for r in values[1:] if any(str(c).strip() for c in r)]
            df = coerce(table, pd.DataFrame([r[:len(header)] for r in rows], columns=header))
        else:
            df = empty(table)
        self._cache[table] = (time.monotonic(), df, len(values))
        return df.copy()

    def _write(self, table: str, df: pd.DataFrame) -> None:
        ws = self._ws(table)
        df = coerce(table, df)
        cols = list(TABLES[table])
        values = [cols] + [[_cell(v) for v in row] for row in df[cols].itertuples(index=False)]
        old_rows = self._cache[table][2] if table in self._cache else len(ws.get_all_values())
        if ws.row_count < len(values):
            ws.add_rows(len(values) - ws.row_count + 50)
        # Write first, then clear leftovers, so a failed call never leaves the tab empty.
        ws.update(values=values, range_name="A1", value_input_option="RAW")
        if old_rows > len(values):
            last_col = chr(ord("A") + len(cols) - 1)
            ws.batch_clear([f"A{len(values) + 1}:{last_col}{old_rows}"])
        self._cache[table] = (time.monotonic(), df, len(values))

    # Everything that touches the sheet goes through one lock, so two people (or two clicks) at the
    # same moment take turns instead of overwriting each other.
    def read(self, table: str) -> pd.DataFrame:
        with self._lock:
            return self._read(table)

    def write(self, table: str, df: pd.DataFrame) -> None:
        with self._lock:
            self._write(table, df)

    def snapshot(self, table: str, name: str) -> str:
        """Duplicate a tab inside Google (exact copy) as a new tab at the end. Returns its name."""
        with self._lock:
            ws = self._ws(table)
            for _ in range(10):
                tabs = self.sh.worksheets()
                candidate = _unique(name, {w.title for w in tabs})
                try:
                    ws.duplicate(insert_sheet_index=len(tabs), new_sheet_name=candidate)
                    return candidate
                except Exception as exc:  # someone took the name a moment ago: try the next one
                    if "already exists" not in str(exc):
                        raise
            raise StorageError(f"Couldn’t find a free name for the backup of {table}.")

    def refresh(self) -> None:
        self._cache.clear()


def _unique(name: str, taken: set[str]) -> str:
    candidate, n = name, 2
    while candidate in taken:
        candidate, n = f"{name} ({n})", n + 1
    return candidate


def _cell(v):
    """Plain Python values for the Sheets API (no numpy types, no NaN)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v

"""Copy your local Kofilyo data (data/beverage.db) into the Google Sheet set in .streamlit/secrets.toml.

Run once, from this folder:   python copy_to_sheets.py
If the sheet already has sales or purchases, it stops; add --force to overwrite them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import toml

from storage import TABLES, SheetsStore, SQLiteStore, StorageError

HERE = Path(__file__).parent


def main() -> int:
    force = "--force" in sys.argv
    local = SQLiteStore(HERE / "data" / "beverage.db")
    if not local.path.exists():
        print(f"No local data file at {local.path}. Nothing to copy.")
        return 1
    secrets = HERE / ".streamlit" / "secrets.toml"
    if not secrets.exists():
        print(f"Missing {secrets}. Copy secrets.toml.example there and fill it in first.")
        return 1
    try:
        sheet = SheetsStore.from_settings(toml.load(secrets)["gsheets"])
    except (KeyError, StorageError) as exc:
        print(f"Couldn't open the Google Sheet: {exc}")
        return 1

    existing = {t: len(sheet.read(t)) for t in ("sales", "expenses")}
    if any(existing.values()) and not force:
        print(f"The sheet already has {existing['sales']} sales rows and {existing['expenses']} purchase rows. "
              "Run again with --force to replace them with your local data.")
        return 1

    for table in TABLES:
        df = local.read(table)
        sheet.write(table, df)
        print(f"Copied {len(df):>5} rows into the '{table}' tab")
    print(f"Done. Your data is now in {sheet.label}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

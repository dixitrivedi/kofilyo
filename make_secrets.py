"""Create .streamlit/secrets.toml from the JSON key Google gave you and your sheet's link.

Usage (from this folder):
    python make_secrets.py ~/Downloads/your-key-file.json "https://docs.google.com/spreadsheets/d/.../edit"

Then paste the same file's contents into Streamlit Cloud: your app > Settings > Secrets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import toml

HERE = Path(__file__).parent


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    key_file, sheet = Path(sys.argv[1]).expanduser(), sys.argv[2].strip()
    try:
        account = json.loads(key_file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Couldn't read the key file {key_file}: {exc}")
        return 1
    if account.get("type") != "service_account" or "private_key" not in account:
        print("That file isn't a service account key. Download a JSON key from the service account's Keys tab.")
        return 1
    out = HERE / ".streamlit" / "secrets.toml"
    if out.exists() and "--force" not in sys.argv:
        print(f"{out} already exists. Delete it first if you want to replace it.")
        return 1
    out.parent.mkdir(exist_ok=True)
    out.write_text(toml.dumps({"gsheets": {"spreadsheet": sheet, "service_account": account}}))
    print(f"Wrote {out}")
    print(f"Now share your Google Sheet with {account.get('client_email')} as an Editor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

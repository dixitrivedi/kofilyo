"""The café's clock: what day and time it is in India, wherever the app runs.

Streamlit Cloud servers run on UTC, 5½ hours behind India, so the server's own date would roll over
at 5:30 am. Everything that asks "what is today?" uses this module instead.
Set the KOFILYO_TZ environment variable to use another time zone (e.g. "Asia/Dubai").
"""
from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

TIMEZONE = os.environ.get("KOFILYO_TZ", "Asia/Kolkata")
TZ = ZoneInfo(TIMEZONE)


def now() -> datetime:
    return datetime.now(TZ)


def today() -> date:
    return now().date()

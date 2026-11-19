"""Kofilyo data: the menu, daily sales and stock purchases.

Data lives in a Google Sheet when `[gsheets]` secrets are set (Streamlit Cloud), otherwise in a local
SQLite file (laptop). The functions below work the same on both; see storage.py.
"""
from __future__ import annotations

import functools
import os
import random
import threading
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

import clock

from storage import SheetsStore, SQLiteStore, StorageError, coerce, empty  # noqa: F401 (StorageError re-exported)

DB_PATH = Path(os.environ.get("BEVERAGE_DB", Path(__file__).parent / "data" / "beverage.db"))

UNITS = ["kg", "g", "L", "ml", "pcs", "pack", "dozen", "cylinder"]

DEFAULT_PRODUCTS = [
    ("Masala Chai", "Hot", 20),
    ("Ginger Tea", "Hot", 20),
    ("Filter Coffee", "Hot", 30),
    ("Cappuccino", "Hot", 80),
    ("Hot Chocolate", "Hot", 90),
    ("Cold Coffee", "Cold", 90),
    ("Iced Tea", "Cold", 60),
    ("Fresh Lime Soda", "Cold", 50),
    ("Mango Shake", "Cold", 100),
    ("Cold Chocolate", "Cold", 100),
]

_STORE = None
_LOCK = threading.RLock()


def _locked(fn):
    """Run a change while holding the lock, so changes from two sessions never interleave
    (each reads, changes and writes a whole table)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _LOCK:
            return fn(*args, **kwargs)
    return wrapper


def _sheet_settings():
    try:
        import streamlit as st
        if "gsheets" in st.secrets:
            return st.secrets["gsheets"]
    except Exception:  # no secrets file, or not running under Streamlit
        pass
    return None


def uses_google_sheets() -> bool:
    return not os.environ.get("BEVERAGE_DB") and _sheet_settings() is not None


def store():
    """The active data store, created once per server process."""
    global _STORE
    if _STORE is None:
        settings = None if os.environ.get("BEVERAGE_DB") else _sheet_settings()
        _STORE = SheetsStore.from_settings(settings) if settings else SQLiteStore(DB_PATH)
    return _STORE


def storage_label() -> str:
    return store().label


def _read(table: str) -> pd.DataFrame:
    return store().read(table)


NAMED = ("sales", "recipes")  # tables that carry a readable product_name next to product_id


def _with_names(df: pd.DataFrame) -> pd.DataFrame:
    """Fill the product_name column from the menu, so the sheet is readable.
    The app itself always goes by product_id; product_name is just a label for people."""
    p = _read("products")
    names = dict(zip(p["id"], p["name"]))
    return df.assign(product_name=df["product_id"].map(names).fillna(""))


def _write(table: str, df: pd.DataFrame) -> None:
    if table in NAMED:
        store().write(table, _with_names(df))
        return
    if table == "products":
        old = _read("products")
        store().write("products", df)
        renamed = (old.merge(coerce("products", df), on="id", suffixes=("_old", "_new"))
                   .query("name_old != name_new"))
        if len(renamed):  # keep the names in the other sheets up to date
            for t in NAMED:
                other = _read(t)
                if other["product_id"].isin(renamed["id"]).any():
                    store().write(t, _with_names(other))
        return
    store().write(table, df)


def _next_id(df: pd.DataFrame) -> int:
    return int(df["id"].max()) + 1 if len(df) else 1


def _append(table: str, df: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return df
    start = _next_id(df)
    new = pd.DataFrame([{**r, "id": start + i} for i, r in enumerate(rows)])
    return pd.concat([df, coerce(table, new)], ignore_index=True)


@_locked
def init_db() -> None:
    if _read("products").empty:
        _write("products", _append("products", empty("products"), [
            {"name": n, "category": c, "price": p, "active": 1, "deleted": 0} for n, c, p in DEFAULT_PRODUCTS
        ]))
    for table in ("sales", "expenses", "running_costs", "payments", "recipes"):
        _read(table)    # creates the tabs in a new Google Sheet


# ---------------------------------------------------------------- products
def get_products(active_only: bool = False, include_deleted: bool = False) -> pd.DataFrame:
    """Drinks on the menu. Deleted drinks with sales history are hidden unless `include_deleted`."""
    df = _read("products")
    if active_only:
        df = df[df["active"] == 1]
    if not include_deleted:
        df = df[df["deleted"] == 0]
    df = df.assign(_n=df["name"].str.lower()).sort_values(["category", "_n"], ascending=[False, True])
    df = df.drop(columns="_n").reset_index(drop=True)
    df["active"] = df["active"].astype(bool)
    df["deleted"] = df["deleted"].astype(bool)
    return df


@_locked
def save_products(edited: pd.DataFrame) -> list[str]:
    """Update or add the drinks in an edited frame. Drinks not in the frame are left alone."""
    edited = edited.copy()
    edited["name"] = edited["name"].fillna("").astype(str).str.strip()
    edited = edited[edited["name"] != ""]
    if edited["name"].str.lower().duplicated().any():
        raise ValueError("Drink names must be unique.")
    if (~edited["category"].isin(["Hot", "Cold"])).any():
        raise ValueError("Every drink needs a type: Hot or Cold.")

    p = _read("products")
    deleted_names = set(p.loc[p["deleted"] == 1, "name"].str.lower())
    for name in edited["name"]:
        if name.lower() in deleted_names:
            raise ValueError(f"“{name}” was deleted earlier. Add it again with Add a drink to bring it back.")
    live_ids = set(p.loc[p["deleted"] == 0, "id"])
    new_rows = []
    for row in edited.itertuples(index=False):
        price = float(row.price) if pd.notna(row.price) else 0.0
        active = 1 if (pd.isna(row.active) or bool(row.active)) else 0
        if pd.notna(row.id) and int(row.id) in live_ids:
            p.loc[p["id"] == int(row.id), ["name", "category", "price", "active"]] = [row.name, row.category, price, active]
        else:
            new_rows.append({"name": row.name, "category": row.category, "price": price, "active": active, "deleted": 0})
    _write("products", _append("products", p, new_rows))
    return []


@_locked
def add_product(name: str, category: str, price: float) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Give the drink a name.")
    p = _read("products")
    match = p[p["name"].str.lower() == name.lower()]
    if len(match) and not match["deleted"].iloc[0]:
        raise ValueError(f"“{name}” is already on the menu.")
    if len(match):  # bring a deleted drink back, keeping its sales history
        p.loc[p["id"] == match["id"].iloc[0], ["name", "category", "price", "active", "deleted"]] = \
            [name, category, float(price), 1, 0]
    else:
        p = _append("products", p, [{"name": name, "category": category, "price": float(price), "active": 1, "deleted": 0}])
    _write("products", p)


@_locked
def delete_product(product_id: int) -> bool:
    """Delete a drink. Returns True when it had sales, in which case it is hidden but its history kept."""
    pid = int(product_id)
    p = _read("products")
    if (_read("sales")["product_id"] == pid).any():
        p.loc[p["id"] == pid, ["active", "deleted"]] = [0, 1]
        _write("products", p)
        return True
    _write("products", p[p["id"] != pid])
    return False


# ------------------------------------------------------------------- sales
def get_sales_for_date(d: date) -> pd.DataFrame:
    s = _read("sales")
    return s.loc[s["sale_date"] == d.isoformat(), ["product_id", "quantity", "unit_price"]].reset_index(drop=True)


@_locked
def save_sales_for_date(d: date, rows: list[tuple[int, int, float]]) -> None:
    """Replace all sales for a date with (product_id, quantity, unit_price) rows."""
    s = _read("sales")
    s = s[s["sale_date"] != d.isoformat()]
    s = _append("sales", s, [{"sale_date": d.isoformat(), "product_id": int(pid), "quantity": int(q),
                              "unit_price": float(price)} for pid, q, price in rows if q and q > 0])
    _write("sales", s.sort_values(["sale_date", "id"]))


def load_sales() -> pd.DataFrame:
    s = _read("sales")
    p = _read("products")[["id", "name", "category"]]
    df = s.merge(p, left_on="product_id", right_on="id", how="inner")
    df = pd.DataFrame({
        "date": pd.to_datetime(df["sale_date"]),
        "product": df["name"],
        "category": df["category"],
        "quantity": df["quantity"],
        "unit_price": df["unit_price"],
        "revenue": df["quantity"] * df["unit_price"],
    })
    return df


# ---------------------------------------------------------------- expenses
def get_expenses_for_date(d: date) -> pd.DataFrame:
    e = _read("expenses")
    e = e[e["expense_date"] == d.isoformat()].sort_values("id")
    return e[["id", "item", "quantity", "unit", "amount", "notes"]].reset_index(drop=True)


@_locked
def add_expense(d: date, item: str, quantity: float, unit: str, amount: float, notes: str) -> None:
    e = _read("expenses")
    e = _append("expenses", e, [{"expense_date": d.isoformat(), "item": item.strip(), "quantity": float(quantity),
                                 "unit": unit or "", "amount": float(amount), "notes": (notes or "").strip()}])
    _write("expenses", e)


def last_unit_for(item: str) -> str | None:
    """The unit used the last time this item was bought, to pre-fill the form."""
    e = _read("expenses")
    e = e[(e["item"].str.lower() == item.strip().lower()) & (e["unit"] != "")]
    if e.empty:
        return None
    return e.sort_values(["expense_date", "id"]).iloc[-1]["unit"]


@_locked
def update_expense(expense_id: int, d: date, item: str, quantity: float, unit: str, amount: float,
                   notes: str) -> None:
    if not item.strip():
        raise ValueError("The item needs a name.")
    if amount <= 0:
        raise ValueError("Enter the amount you paid.")
    e = _read("expenses")
    e.loc[e["id"] == int(expense_id), ["expense_date", "item", "quantity", "unit", "amount", "notes"]] = \
        [d.isoformat(), item.strip(), float(quantity), unit or "", float(amount), (notes or "").strip()]
    _write("expenses", e)


@_locked
def delete_expense(expense_id: int) -> None:
    e = _read("expenses")
    _write("expenses", e[e["id"] != int(expense_id)])


def known_expense_items() -> list[str]:
    items = _read("expenses")["item"]
    return sorted({i for i in items if i}, key=str.lower)


def load_expenses() -> pd.DataFrame:
    e = _read("expenses")
    return pd.DataFrame({
        "date": pd.to_datetime(e["expense_date"]),
        "item": e["item"],
        "quantity": e["quantity"],
        "unit": e["unit"],
        "amount": e["amount"],
        "notes": e["notes"],
    })


# ----------------------------------------------------------- running costs
RUNNING_COST_NAMES = ["Rent", "Staff salaries", "Electricity", "Water", "Internet and phone", "Maintenance",
                      "Licences and fees", "Marketing"]


def _check_cost(name: str, amount: float, spread: str) -> None:
    if not name.strip():
        raise ValueError("Give the cost a name, for example Rent.")
    if amount <= 0:
        raise ValueError("Enter the amount.")
    if spread not in ("month", "day"):
        raise ValueError("Choose whether the cost is for the whole month or one day.")


def get_running_costs(month: date) -> pd.DataFrame:
    """All running costs dated in the month that contains `month`."""
    rc = _read("running_costs")
    first = month.replace(day=1).isoformat()[:7]
    rc = rc[rc["cost_date"].str[:7] == first].sort_values(["spread", "cost_date", "id"], ascending=[False, True, True])
    return rc.reset_index(drop=True)


@_locked
def add_running_cost(d: date, name: str, amount: float, spread: str, notes: str = "") -> None:
    _check_cost(name, amount, spread)
    if spread == "month":
        d = d.replace(day=1)
    rc = _append("running_costs", _read("running_costs"), [{"cost_date": d.isoformat(), "name": name.strip(),
                                                          "amount": float(amount), "spread": spread,
                                                          "notes": (notes or "").strip()}])
    _write("running_costs", rc)


@_locked
def update_running_cost(cost_id: int, d: date, name: str, amount: float, spread: str, notes: str = "") -> None:
    _check_cost(name, amount, spread)
    if spread == "month":
        d = d.replace(day=1)
    rc = _read("running_costs")
    rc.loc[rc["id"] == int(cost_id), ["cost_date", "name", "amount", "spread", "notes"]] = \
        [d.isoformat(), name.strip(), float(amount), spread, (notes or "").strip()]
    _write("running_costs", rc)


@_locked
def delete_running_cost(cost_id: int) -> None:
    rc = _read("running_costs")
    _write("running_costs", rc[rc["id"] != int(cost_id)])


@_locked
def copy_monthly_costs(from_month: date, to_month: date) -> int:
    """Copy last month's whole-month costs (rent, salaries...) into another month.
    Skips names already entered there. Returns how many were copied."""
    src = get_running_costs(from_month)
    src = src[src["spread"] == "month"]
    have = set(get_running_costs(to_month)["name"].str.lower())
    rows = [{"cost_date": to_month.replace(day=1).isoformat(), "name": r.name, "amount": r.amount,
             "spread": "month", "notes": r.notes} for r in src.itertuples() if r.name.lower() not in have]
    if rows:
        _write("running_costs", _append("running_costs", _read("running_costs"), rows))
    return len(rows)


def known_running_cost_names() -> list[str]:
    names = set(RUNNING_COST_NAMES) | {n for n in _read("running_costs")["name"] if n}
    return sorted(names, key=str.lower)


def load_running_costs() -> pd.DataFrame:
    rc = _read("running_costs")
    return pd.DataFrame({"date": pd.to_datetime(rc["cost_date"]), "name": rc["name"], "amount": rc["amount"],
                         "spread": rc["spread"], "notes": rc["notes"]})


# ---------------------------------------------------------------- payments
def get_payment(d: date) -> dict | None:
    p = _read("payments")
    row = p[p["pay_date"] == d.isoformat()]
    if row.empty:
        return None
    r = row.iloc[-1]
    return {"cash": float(r.cash), "upi": float(r.upi), "card": float(r.card)}


@_locked
def save_payment(d: date, cash: float, upi: float, card: float) -> None:
    """One row per day. All zeros removes the day's row."""
    p = _read("payments")
    p = p[p["pay_date"] != d.isoformat()]
    if cash or upi or card:
        p = _append("payments", p, [{"pay_date": d.isoformat(), "cash": float(cash), "upi": float(upi),
                                     "card": float(card)}])
    _write("payments", p.sort_values(["pay_date", "id"]))


def load_payments() -> pd.DataFrame:
    p = _read("payments")
    return pd.DataFrame({"date": pd.to_datetime(p["pay_date"]), "cash": p["cash"], "upi": p["upi"],
                         "card": p["card"]})


# ------------------------------------------------------------ cost per cup
RECIPE_UNITS = ["ml", "L", "g", "kg", "pcs", "dozen", "pack"]
# unit -> (base unit, how many base units it holds); units with different bases can't be compared
UNIT_BASE = {"g": ("g", 1), "kg": ("g", 1000), "ml": ("ml", 1), "L": ("ml", 1000), "pcs": ("pcs", 1),
             "dozen": ("pcs", 12), "pack": ("pack", 1), "cylinder": ("cylinder", 1)}
PRICE_WINDOW_DAYS = 90


def get_recipe(product_id: int) -> pd.DataFrame:
    r = _read("recipes")
    return r[r["product_id"] == int(product_id)].sort_values("id")[["item", "quantity", "unit"]].reset_index(drop=True)


@_locked
def save_recipe(product_id: int, rows: list[tuple[str, float, str]]) -> None:
    """Replace a drink's recipe with (item, quantity per cup, unit) rows. Empty items are dropped."""
    clean = [(i.strip(), float(q), u) for i, q, u in rows if i and i.strip() and q and q > 0]
    if len({i.lower() for i, _, _ in clean}) != len(clean):
        raise ValueError("Each ingredient should appear once in a recipe.")
    r = _read("recipes")
    r = r[r["product_id"] != int(product_id)]
    r = _append("recipes", r, [{"product_id": int(product_id), "item": i, "quantity": q, "unit": u}
                               for i, q, u in clean])
    _write("recipes", r.sort_values(["product_id", "id"]))


def ingredient_prices(today: date | None = None) -> dict[str, dict]:
    """Price per base unit (g, ml, pcs...) for every purchased item, keyed by lower-case name.
    Uses the average paid over the last 90 days; if not bought in that time, the latest purchase."""
    today = today or clock.today()
    e = _read("expenses")
    e = e[(e["quantity"] > 0) & (e["amount"] > 0) & e["unit"].isin(UNIT_BASE)]
    out: dict[str, dict] = {}
    if e.empty:
        return out
    e = e.assign(key=e["item"].str.lower(), base=e["unit"].map(lambda u: UNIT_BASE[u][0]),
                 base_qty=e["quantity"] * e["unit"].map(lambda u: UNIT_BASE[u][1]))
    cutoff = (today - timedelta(days=PRICE_WINDOW_DAYS)).isoformat()
    for key, g in e.sort_values(["expense_date", "id"]).groupby("key"):
        latest = g.iloc[-1]
        same = g[g["base"] == latest["base"]]          # compare like with like (mass with mass...)
        recent = same[same["expense_date"] >= cutoff]
        use, how = (recent, f"average of the last {PRICE_WINDOW_DAYS} days") if len(recent) else \
                   (same.tail(1), f"last bought {latest['expense_date']}")
        out[key] = {"item": latest["item"], "base": latest["base"],
                    "per_base": float(use["amount"].sum() / use["base_qty"].sum()), "how": how,
                    "unit": latest["unit"], "per_unit": float(use["amount"].sum() / use["base_qty"].sum())
                    * UNIT_BASE[latest["unit"]][1]}
    return out


def ingredient_cost(item: str, quantity: float, unit: str, prices: dict[str, dict]) -> tuple[float | None, str]:
    """Cost of `quantity` `unit` of an item, and a note when it can't be worked out."""
    info = prices.get(item.strip().lower())
    if info is None:
        return None, "no purchase recorded yet"
    if unit not in UNIT_BASE or UNIT_BASE[unit][0] != info["base"]:
        return None, f"bought in {info['unit']}, can’t convert from {unit}"
    return quantity * UNIT_BASE[unit][1] * info["per_base"], ""


def cost_per_cup() -> pd.DataFrame:
    """One row per drink on the menu: price, cost per cup, profit per cup, margin and any problems."""
    prices = ingredient_prices()
    recipes = _read("recipes")
    rows = []
    for p in get_products().itertuples():
        rec = recipes[recipes["product_id"] == int(p.id)]
        cost, problems = 0.0, []
        for r in rec.itertuples():
            c, why = ingredient_cost(r.item, r.quantity, r.unit, prices)
            if c is None:
                problems.append(f"{r.item}: {why}")
            else:
                cost += c
        has = len(rec) > 0
        rows.append({"product_id": int(p.id), "name": p.name, "category": p.category, "price": float(p.price),
                     "has_recipe": has, "cost": cost if has else None,
                     "profit": float(p.price) - cost if has else None,
                     "margin": (float(p.price) - cost) / float(p.price) if has and p.price else None,
                     "problems": problems})
    return pd.DataFrame(rows, columns=["product_id", "name", "category", "price", "has_recipe", "cost", "profit",
                                       "margin", "problems"])


# ------------------------------------------------------------------- admin
WIPED = ("sales", "expenses", "running_costs", "payments")   # Start fresh clears these; menu and recipes stay


@_locked
def backup_data() -> list[str]:
    """Copy the sales and purchases tables into dated backup tabs. Returns the backup names.
    Raises if a copy fails, so callers never delete data without a backup."""
    stamp = clock.now().strftime("%Y-%m-%d %H.%M")
    names = []
    for table in WIPED:
        if len(_read(table)):
            names.append(store().snapshot(table, f"backup {stamp} {table}"))
    return names


@_locked
def clear_all_data() -> list[str]:
    """Delete all sales, purchases, running costs and payments (the menu and recipes stay), after backing
    them up. Returns backup names."""
    backups = backup_data()
    for table in WIPED:
        _write(table, empty(table))
    return backups


@_locked
def load_demo_data(days: int = 120) -> list[str]:
    """Replace sales and purchases with `days` days of sample data, after backing them up.
    Returns backup names."""
    backups = backup_data()
    rng = random.Random(42)
    today = clock.today()
    products = get_products(active_only=True)
    base = {
        "Masala Chai": 60, "Ginger Tea": 30, "Filter Coffee": 35, "Cappuccino": 14,
        "Hot Chocolate": 8, "Cold Coffee": 22, "Iced Tea": 14, "Fresh Lime Soda": 18,
        "Mango Shake": 10, "Cold Chocolate": 9,
    }
    plan = [("Milk", 28, "L", 58), ("Tea leaves", 1.2, "kg", 420), ("Sugar", 5, "kg", 45),
            ("Ice", 18, "kg", 8), ("Paper cups", 200, "pcs", 1.2)]
    sales, buys = [], []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        iso = d.isoformat()
        month_factor = 1 + 0.4 * ((d.month in (4, 5, 6)) - (d.month in (12, 1)))
        weekend = 1.35 if d.weekday() >= 5 else 1.0
        for p in products.itertuples():
            b = base.get(p.name, 12)
            season = month_factor if p.category == "Cold" else (2 - month_factor)
            q = max(0, int(rng.gauss(b * weekend * season, b * 0.2)))
            if q:
                sales.append({"sale_date": iso, "product_id": int(p.id), "quantity": q, "unit_price": float(p.price)})
        for item, qty, unit, rate in plan:
            if item == "Tea leaves" and d.weekday() not in (0, 3):
                continue
            if item == "Paper cups" and d.weekday() != 0:
                continue
            qn = 1500 if item == "Paper cups" else round(qty * weekend * rng.uniform(0.85, 1.15), 1)
            buys.append({"expense_date": iso, "item": item, "quantity": qn, "unit": unit,
                         "amount": round(qn * rate, 2), "notes": ""})
        if d.weekday() == 0:
            buys.append({"expense_date": iso, "item": "Coffee powder", "quantity": 2, "unit": "kg",
                         "amount": 1800, "notes": ""})
        if d.day in (1, 15):
            buys.append({"expense_date": iso, "item": "LPG cylinder", "quantity": 1, "unit": "cylinder",
                         "amount": 1750, "notes": ""})
        if d.weekday() in (1, 4):
            buys.append({"expense_date": iso, "item": "Mangoes & lemons", "quantity": 5, "unit": "kg",
                         "amount": round(rng.uniform(900, 1300), 2), "notes": ""})
    # how each day was paid: mostly UPI, some cash, a little card
    day_rev: dict[str, float] = {}
    for r in sales:
        day_rev[r["sale_date"]] = day_rev.get(r["sale_date"], 0.0) + r["quantity"] * r["unit_price"]
    pays = []
    for iso, rev in day_rev.items():
        upi = round(rev * rng.uniform(0.5, 0.62), -1)
        card = round(rev * rng.uniform(0.05, 0.12), -1)
        pays.append({"pay_date": iso, "cash": round(rev - upi - card, 2), "upi": upi, "card": card})
    # rent and salaries for each month, electricity at month end, the odd repair
    costs, month = [], (today - timedelta(days=days - 1)).replace(day=1)
    while month <= today:
        costs += [{"cost_date": month.isoformat(), "name": "Rent", "amount": 25000, "spread": "month", "notes": ""},
                  {"cost_date": month.isoformat(), "name": "Staff salaries", "amount": 36000, "spread": "month",
                   "notes": "2 staff"},
                  {"cost_date": month.isoformat(), "name": "Electricity", "amount": round(rng.uniform(3800, 5200)),
                   "spread": "month", "notes": ""}]
        if rng.random() < 0.5:
            costs.append({"cost_date": month.replace(day=rng.randint(5, 25)).isoformat(),
                          "name": "Maintenance", "amount": round(rng.uniform(800, 2500)), "spread": "day",
                          "notes": "Coffee machine service"})
        month = (month + timedelta(days=32)).replace(day=1)
    _write("sales", _append("sales", empty("sales"), sales))
    _write("expenses", _append("expenses", empty("expenses"), buys))
    _write("payments", _append("payments", empty("payments"), pays))
    _write("running_costs", _append("running_costs", empty("running_costs"), costs))
    return backups

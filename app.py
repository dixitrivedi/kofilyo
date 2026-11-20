"""Kofilyo: daily sales and stock-spend tracker with weekly and monthly reports.

Run with:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import analytics as an
import auth
import clock
import db
from theme import (BRAND_NAME, T, apply_theme, current_theme, delta_text, empty, esc, html_table, legend, md,
                   menu_board, money, page_title, panel_head, sidebar_brand, split_bar, stat_strip, theme_switch)

st.set_page_config(page_title=BRAND_NAME, page_icon="🍊", layout="wide", initial_sidebar_state="auto")
current_theme()
apply_theme()

CHART = an.CHART_CONFIG
NEW_ITEM = "+ New item…"
# ------------------------------------------------------------------ helpers
def flash() -> None:
    msg = st.session_state.pop("flash", None)
    if msg:
        st.toast(msg, icon=":material/check_circle:")


def date_picker(key: str) -> date:
    mode_key = f"{key}-mode"
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "Today"
    choice = st.segmented_control("Date", ["Today", "Yesterday", "Other day"], key=mode_key,
                                  label_visibility="collapsed")
    today = clock.today()
    if choice == "Yesterday":
        return today - timedelta(days=1)
    if choice == "Other day":
        return st.date_input("Pick a date", value=today - timedelta(days=2), max_value=today,
                             format="DD/MM/YYYY", key=f"{key}-date", label_visibility="collapsed")
    return today


def day_phrase(d: date) -> str:
    if d == clock.today():
        return "today"
    if d == clock.today() - timedelta(days=1):
        return "yesterday"
    return f"on {d:%a %d %b}"


def _forget(*prefixes: str) -> None:
    """Drop widget values whose keys start with any prefix, so the next open starts fresh."""
    for k in [k for k in st.session_state if isinstance(k, str) and k.startswith(prefixes)]:
        del st.session_state[k]


def _stop_editing(flag: str, prefix: str) -> None:
    # Streamlit drops the edit boxes' values by itself once they are off screen.
    st.session_state.pop(flag, None)


def name_picker(label: str, options: list[str], key: str, placeholder: str, new_label: str) -> str | None:
    """A list to choose from, with “+ New item…” at the top that opens a box for a new name."""
    choice = st.selectbox(label, [NEW_ITEM] + options, index=None, key=key, placeholder=placeholder)
    if choice == NEW_ITEM:
        typed = st.text_input(new_label, key=f"{key}-new").strip()
        st.caption("It will be in the list next time.")
        return typed or None
    return choice


def _remove_choice(kind: str, name: str) -> None:
    db.remove_choice(kind, name)
    st.session_state["flash"] = f"Removed {name} from the list"


def list_editor(kind: str, noun: str, used_for: str) -> None:
    """An “Edit the list” section: every name with a remove button, and a box to add a new one."""
    import hashlib
    with st.expander("Edit the list", icon=":material/edit_note:"):
        names = db.get_choices(kind)
        if not names:
            md(f'<p class="muted">The list is empty. Add a {noun} below.</p>')
        for n in names:
            slug = hashlib.md5(n.lower().encode()).hexdigest()[:10]
            with st.container(key=f"chrow-{kind}{slug}"):
                c = st.columns([5, 0.7], vertical_alignment="center", gap="small")
                c[0].markdown(f'<div class="drink" style="font-size:16px">{esc(n)}</div>', unsafe_allow_html=True)
                c[1].button(":material/delete:", key=f"del-ch{kind}{slug}", help=f"Remove {n} from the list",
                            on_click=_remove_choice, args=(kind, n))
        v = st.session_state.get(f"ch-v-{kind}", 0)
        c = st.columns([3, 1.2], vertical_alignment="bottom", gap="small")
        new = c[0].text_input(f"Add a {noun}", key=f"ch-new-{kind}-{v}")
        if c[1].button("Add", key=f"ch-add-{kind}", width="stretch", icon=":material/add:"):
            try:
                added = db.add_choice(kind, new)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state[f"ch-v-{kind}"] = v + 1
                st.session_state["flash"] = f"Added {added} to the list"
                st.rerun()
        st.caption(f"Removing a name only takes it off this list. {used_for} already saved keep their name.")


def pay_status(revenue: float, paid: float) -> str:
    if paid == 0:
        return '<span class="faint">Not entered yet</span>'
    diff = revenue - paid
    if abs(diff) < 0.5:
        return '<span class="up">Matches the day’s sales</span>'
    if diff > 0:
        return f'<span class="down">{money(diff)} not accounted for</span>'
    return f'<span class="down">{money(-diff)} more than the day’s sales</span>'


def running_costs_df() -> pd.DataFrame:
    return db.load_running_costs()


# =================================================================== Today
def page_today() -> None:
    flash()
    t_ = T()
    today = pd.Timestamp(clock.today())
    yday = today - pd.Timedelta(days=1)
    sales, expenses, rc = db.load_sales(), db.load_expenses(), running_costs_df()

    left, right = st.columns([1.3, 1], vertical_alignment="center")
    left.markdown(f'<p class="page-sub" style="margin:0">{today:%A, %d %B}</p>', unsafe_allow_html=True)
    with right:
        a, b = st.columns(2)
        with a, st.container(key="cta-secondary"):
            st.page_link(PAGES["expenses"], label="Add a purchase", width="stretch")
        with b, st.container(key="cta-primary"):
            st.page_link(PAGES["sales"], label="Record today’s sales", width="stretch")

    t = an.summarize(an.between(sales, today, today), an.between(expenses, today, today),
                     an.running_daily(rc, today, today).sum())
    y = an.summarize(an.between(sales, yday, yday), an.between(expenses, yday, yday))
    if t["cups"] == 0:
        sub = "Nothing recorded for today yet."
    elif y["revenue"]:
        ch = an.change(t["revenue"], y["revenue"])
        word, cls = ("more", "up") if ch >= 0 else ("less", "down")
        sub = f'taken today, <span class="{cls}">{abs(ch):.1%} {word}</span> than yesterday'
    else:
        sub = "taken today"
    strip = stat_strip([
        {"label": "Cups sold", "value": f"{t['cups']:,}"},
        {"label": "Spent on stock", "value": money(t["expense"])},
        {"label": "Running costs (today)", "value": money(t["running"])},
        {"label": "Profit", "value": money(t["profit"]), "color": t_["good"] if t["profit"] >= 0 else t_["bad"]},
    ])
    md(f'<section class="hero"><div><h1 class="hero-num">{money(t["revenue"])}</h1>'
       f'<p class="hero-sub">{sub}</p></div>{strip}</section>')

    if sales.empty and expenses.empty:
        empty("Nothing here yet",
              "Record today’s sales and stock purchases to fill this page. "
              "To look around first, load demo data from <b>Menu and prices</b>.")
        return

    start14 = today - pd.Timedelta(days=13)
    s14, e14 = an.between(sales, start14, today), an.between(expenses, start14, today)
    run14 = an.running_daily(rc, start14, today)
    c1, c2 = st.columns([2, 1], gap="medium")
    with c1, st.container(key="panel-chart"):
        items = [("Sales", t_["accent"]), ("Stock spend", t_["expense"])]
        if run14.any():
            items.append(("Running costs", t_["running"]))
        panel_head("Last 14 days", legend(items))
        st.plotly_chart(an.daily_chart(s14, e14, start14, today, running=run14), config=CHART, width="stretch")
    with c2:
        mix, mix_title = an.between(sales, today, today), "Hot or cold"
        if mix.empty:
            mix, mix_title = an.between(sales, today - pd.Timedelta(days=6), today), "Hot or cold, last 7 days"
        by_type = mix.groupby("category")["quantity"].sum()
        with st.container(key="panel-split"):
            panel_head(mix_title)
            md(split_bar(int(by_type.get("Hot", 0)), int(by_type.get("Cold", 0))))
        with st.container(key="panel-board"):
            top = mix.groupby("product")["quantity"].sum().sort_values(ascending=False).head(6)
            title = "Today’s bestsellers" if mix_title == "Hot or cold" else "This week’s bestsellers"
            if top.empty:
                md('<p class="muted">No sales yet.</p>')
            else:
                md(menu_board(title, [(n, f"{int(q):,}") for n, q in top.items()]))


# ============================================================ Record sales
def _step(key: str, delta: int) -> None:
    st.session_state[key] = max(0, int(st.session_state.get(key, 0)) + delta)


def _rest_is_cash(keys: dict[str, str], total: float) -> None:
    other = float(st.session_state[keys["upi"]]) + float(st.session_state[keys["card"]])
    st.session_state[keys["cash"]] = float(max(0.0, round(total - other, 2)))


def _start_over(tag: str) -> None:
    """Clear the correction counters for a day, so the next screen starts from what is saved."""
    _forget(f"fix-{tag}-")


METHOD_COLOR = {"Cash": "good", "UPI": "cold", "Card": "accent"}


def page_sales() -> None:
    flash()
    head, pick = st.columns([1.6, 1], vertical_alignment="bottom")
    with pick:
        d = date_picker("sales")
        tag = d.isoformat()
        fix = st.toggle("Correct the day’s totals", key="sales-fix", on_change=_start_over, args=(tag,),
                        help="Change what is already saved for the day, instead of taking a new order")
    whose = f"{day_phrase(d)}’s" if day_phrase(d) in ("today", "yesterday") else f"{d:%a %d %b}’s"
    with head:
        if fix:
            page_title(f"Correct {whose} totals",
                       "These are the saved totals for the whole day. Change them and press Save totals. "
                       "The order list is not changed.")
        else:
            page_title("New order", "Pick each drink the customer asks for, choose how they paid, then press "
                                    "Save order.")
    st.write("")
    products = db.get_products(include_deleted=True)
    if products.empty:
        empty("No drinks on the menu", "Add your drinks in <b>Menu and prices</b>, then come back here.")
        return
    if fix:
        _correct_totals(d, tag, products)
    else:
        _take_order(d, tag, whose, products)


# ------------------------------------------------------------- new order
def _order(tag: str) -> list[dict]:
    return st.session_state.setdefault(f"order-{tag}", [])


def _add_to_order(tag: str) -> None:
    pid = st.session_state.get(f"pick-{tag}")
    qty = int(st.session_state.get(f"pickqty-{tag}") or 1)
    if pid is None:
        st.session_state["order-msg"] = "Choose a drink first."
        return
    lines = _order(tag)
    for line in lines:
        if line["pid"] == pid:
            line["qty"] += qty
            break
    else:
        lines.append({"pid": pid, "qty": qty})
    st.session_state[f"pick-{tag}"] = None       # ready for the next drink
    st.session_state[f"pickqty-{tag}"] = 1


def _change_line(tag: str, pid: int, delta: int) -> None:
    lines = _order(tag)
    for line in lines:
        if line["pid"] == pid:
            line["qty"] += delta
    st.session_state[f"order-{tag}"] = [ln for ln in lines if ln["qty"] > 0]


def _clear_order(tag: str) -> None:
    st.session_state[f"order-{tag}"] = []
    st.session_state[f"method-{tag}"] = None


def _ask_remove_order(order_id: int) -> None:
    st.session_state["confirm-order"] = order_id


def _keep_order() -> None:
    st.session_state.pop("confirm-order", None)


def _remove_order(order_id: int) -> None:
    db.delete_order(order_id)
    st.session_state.pop("confirm-order", None)
    st.session_state["flash"] = "Order removed, and taken off the day’s totals"


def _take_order(d: date, tag: str, whose: str, products: pd.DataFrame) -> None:
    t_ = T()
    menu = products[products["active"] & ~products["deleted"]]
    price = dict(zip(products["id"].astype(int), products["price"].astype(float)))
    names = dict(zip(products["id"].astype(int), products["name"]))
    if st.session_state.pop("order-reset", None) == tag:          # just saved: start a fresh order
        st.session_state[f"order-{tag}"] = []
        st.session_state[f"method-{tag}"] = None

    for k, start in ((f"pick-{tag}", None), (f"pickqty-{tag}", 1), (f"method-{tag}", None)):
        st.session_state.setdefault(k, start)      # set here only, so code can reset them later

    left, right = st.columns([1.15, 1], gap="medium")
    with left, st.container(key="panel-order"):
        lines = _order(tag)
        total = sum(ln["qty"] * price[ln["pid"]] for ln in lines)
        cups = sum(ln["qty"] for ln in lines)
        panel_head("This order", f'<span class="muted">{cups} {"cup" if cups == 1 else "cups"}</span>')
        c = st.columns([3, 1, 1.5], vertical_alignment="bottom", gap="small")
        c[0].selectbox("Drink", [int(i) for i in menu["id"]], key=f"pick-{tag}",
                       format_func=lambda i: f"{names[i]}  ·  {money(price[i])}", placeholder="Choose a drink")
        c[1].number_input("How many", min_value=1, step=1, key=f"pickqty-{tag}")
        c[2].button("Add to order", on_click=_add_to_order, args=(tag,), icon=":material/add:", width="stretch",
                    key=f"addline-{tag}")
        msg = st.session_state.pop("order-msg", None)
        if msg:
            st.warning(msg, icon=":material/info:")
        if not lines:
            md('<p class="muted" style="margin:14px 0 4px">Choose a drink above and press Add to order. '
               'Add each drink the customer asks for.</p>')
        for ln in lines:
            pid = ln["pid"]
            with st.container(key=f"row-ol{pid}"):
                c = st.columns([3.2, 0.8, 0.8, 0.8, 1.3, 0.5], vertical_alignment="center", gap="small")
                c[0].markdown(f'<div class="drink">{esc(names[pid])}<small>{money(price[pid])} a cup</small></div>',
                              unsafe_allow_html=True)
                c[1].button("−", key=f"dec-o{pid}", on_click=_change_line, args=(tag, pid, -1), help="One less")
                c[2].markdown(f'<div class="total-num" style="font-size:30px;text-align:center;color:inherit">'
                              f'{ln["qty"]}</div>', unsafe_allow_html=True)
                c[3].button("+", key=f"inc-o{pid}", on_click=_change_line, args=(tag, pid, 1), help="One more")
                c[4].markdown(f'<div class="amount">{money(ln["qty"] * price[pid])}</div>', unsafe_allow_html=True)
                c[5].button(":material/delete:", key=f"del-ol{pid}", help=f"Take {names[pid]} off the order",
                            on_click=_change_line, args=(tag, pid, -ln["qty"]))
        st.write("")
        md(f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin:6px 0 10px">'
           f'<span class="muted">Order total</span><span class="total-num">{money(total)}</span></div>')
        c = st.columns([1.5, 1], vertical_alignment="bottom", gap="small")
        method = c[0].selectbox("Paid by", db.METHODS, key=f"method-{tag}",
                                placeholder="Choose cash, UPI or card")
        if c[1].button("Save order", type="primary", width="stretch", key=f"save-order-{tag}"):
            try:
                db.add_order(d, [(ln["pid"], ln["qty"], price[ln["pid"]]) for ln in lines], method or "")
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["order-reset"] = tag
                st.session_state["flash"] = f"Saved: {cups} {'cup' if cups == 1 else 'cups'}, {money(total)} by {method}"
                st.rerun()
        if lines:
            st.button("Clear this order", on_click=_clear_order, args=(tag,), key=f"clear-order-{tag}")

    with right, st.container(key="panel-orders"):
        orders = db.get_orders(d)
        existing = db.get_sales_for_date(d)
        day_total = float((existing["quantity"] * existing["unit_price"]).sum())
        day_cups = int(existing["quantity"].sum())
        pay = db.get_payment(d) or {"cash": 0.0, "upi": 0.0, "card": 0.0}
        panel_head(f"{whose[0].upper() + whose[1:]} orders",
                   f'<span class="muted">{money(day_total)}, {day_cups} {"cup" if day_cups == 1 else "cups"}</span>')
        if any(pay.values()):
            md('<div class="paylist" style="margin:0 0 12px">' + "".join(
                f'<div><i style="background:{t_[METHOD_COLOR[m]]}"></i>{m}<b>{money(pay[m.lower()])}</b></div>'
                for m in db.METHODS) + "</div>")
        gap = sum(pay.values()) - day_total
        if abs(gap) > 0.5:     # e.g. a sale deleted by hand in the Google Sheet, but not its payment
            st.warning(f"Payments recorded ({money(sum(pay.values()))}) don’t match the day’s sales "
                       f"({money(day_total)}). To fix it, turn on Correct the day’s totals.", icon=":material/warning:")
        if orders.empty:
            md('<p class="muted">No orders saved for this day yet.</p>')
        for r in orders.itertuples():
            oid = int(r.id)
            if st.session_state.get("confirm-order") == oid:
                with st.container(key=f"row-confirm-o{oid}"):
                    c = st.columns([3, 1.1, 1.1], vertical_alignment="center", gap="small")
                    c[0].markdown(f'<div class="drink">Remove this order?<small>{esc(r.items)}, {money(r.total)}'
                                  '</small></div>', unsafe_allow_html=True)
                    c[1].button("Keep", key=f"keep-o{oid}", on_click=_keep_order, width="stretch")
                    c[2].button("Remove", key=f"confirmdel-o{oid}", type="primary", on_click=_remove_order,
                                args=(oid,), width="stretch")
                continue
            with st.container(key=f"row-ord{oid}"):
                c = st.columns([0.8, 3, 1.3, 0.5], vertical_alignment="center", gap="small")
                c[0].markdown(f'<div class="muted">{esc(r.order_time) or "–"}</div>', unsafe_allow_html=True)
                c[1].markdown(f'<div class="drink" style="font-size:16px">{esc(r.items)}<small>'
                              f'<span style="color:{t_[METHOD_COLOR.get(r.method, "faint")]}">●</span> '
                              f'{esc(r.method)}</small></div>', unsafe_allow_html=True)
                c[2].markdown(f'<div class="amount" style="color:inherit">{money(r.total)}</div>',
                              unsafe_allow_html=True)
                c[3].button(":material/delete:", key=f"del-o{oid}", help="Remove this order",
                            on_click=_ask_remove_order, args=(oid,))


# ------------------------------------------------------- correct totals
def _correct_totals(d: date, tag: str, products: pd.DataFrame) -> None:
    t_ = T()
    existing = db.get_sales_for_date(d)
    ex_qty = {int(k): int(v) for k, v in zip(existing["product_id"], existing["quantity"])}
    ex_price = {int(k): float(v) for k, v in zip(existing["product_id"], existing["unit_price"])}
    show = products[(products["active"] & ~products["deleted"]) | products["id"].isin(ex_qty.keys())]
    if st.session_state.pop("sales-reset", None) == tag:
        _start_over(tag)
    qkey = {int(pid): f"fix-{tag}-q{int(pid)}" for pid in show["id"]}
    for pid, k in qkey.items():
        if k not in st.session_state:
            st.session_state[k] = ex_qty.get(pid, 0)
    saved_pay = db.get_payment(d) or {"cash": 0.0, "upi": 0.0, "card": 0.0}
    pkey = {m: f"fix-{tag}-pay-{m}" for m in ("cash", "upi", "card")}
    for m, k in pkey.items():
        if k not in st.session_state:
            st.session_state[k] = float(saved_pay[m])

    cols = st.columns(2, gap="medium")
    for col, cat in zip(cols, ["Hot", "Cold"]):
        part = show[show["category"] == cat]
        with col, st.container(key=f"panel-{cat.lower()}"):
            cups = sum(int(st.session_state[qkey[int(p)]]) for p in part["id"])
            color = t_["accent_text"] if cat == "Hot" else t_["cold"]
            md(f'<div class="group-h"><h3 style="color:{color}">{cat}</h3><span class="muted">{cups:,} cups</span></div>')
            if part.empty:
                md(f'<p class="muted">No {cat.lower()} drinks on the menu.</p>')
            for p in part.itertuples():
                pid = int(p.id)
                price = ex_price.get(pid, float(p.price))
                qty = int(st.session_state[qkey[pid]])
                with st.container(key=f"row-{pid}"):
                    c = st.columns([3.2, 0.8, 1.15, 0.8, 1.3], vertical_alignment="center", gap="small")
                    c[0].markdown(f'<div class="drink">{esc(p.name)}<small>{money(price)} a cup</small></div>',
                                  unsafe_allow_html=True)
                    c[1].button("−", key=f"dec-{pid}", on_click=_step, args=(qkey[pid], -1), help=f"One less {p.name}")
                    c[2].number_input(f"Cups of {p.name}", min_value=0, step=1, key=qkey[pid],
                                      label_visibility="collapsed")
                    c[3].button("+", key=f"inc-{pid}", on_click=_step, args=(qkey[pid], 1), help=f"One more {p.name}")
                    c[4].markdown(f'<div class="amount">{money(qty * price)}</div>', unsafe_allow_html=True)

    rows, cups, total = [], 0, 0.0
    for p in show.itertuples():
        q = int(st.session_state[qkey[int(p.id)]])
        pr = ex_price.get(int(p.id), float(p.price))
        rows.append((int(p.id), q, pr))
        cups += q
        total += q * pr
    paid = {m: float(st.session_state[k]) for m, k in pkey.items()}

    st.write("")
    with st.container(key="panel-pay"):
        panel_head("How were you paid for the whole day?", pay_status(total, sum(paid.values())))
        c = st.columns([1, 1, 1, 1], vertical_alignment="bottom", gap="small")
        c[0].number_input("Cash (₹)", min_value=0.0, step=10.0, format="%.0f", key=pkey["cash"])
        c[1].number_input("UPI (₹)", min_value=0.0, step=10.0, format="%.0f", key=pkey["upi"])
        c[2].number_input("Card (₹)", min_value=0.0, step=10.0, format="%.0f", key=pkey["card"])
        c[3].button("Rest is cash", on_click=_rest_is_cash, args=(pkey, total), width="stretch",
                    help="Sets cash to the total minus UPI and card")

    st.write("")
    with st.container(key="savebar"):
        a, b = st.columns([3, 1], vertical_alignment="center")
        changed = any(q != ex_qty.get(pid, 0) for pid, q, _ in rows) or \
            any(abs(paid[m] - saved_pay[m]) > 0.001 for m in paid)
        status = '<span class="down">Not saved yet</span>' if changed else '<span class="faint">Saved</span>'
        a.markdown(f'<span class="total-num">{money(total)}</span>&nbsp; <span class="muted">for the day</span>'
                   f'&nbsp;&nbsp;&nbsp; <b>{cups:,}</b> cups&nbsp;&nbsp;&nbsp; {status}', unsafe_allow_html=True)
        if b.button("Save totals", type="primary", width="stretch"):
            db.save_sales_for_date(d, rows)
            db.save_payment(d, paid["cash"], paid["upi"], paid["card"])
            st.session_state["sales-reset"] = tag
            st.session_state["flash"] = f"Saved the totals for {d:%d %b}: {cups:,} cups, {money(total)}"
            st.rerun()


# ========================================================= Record purchases
def _delete_expense(expense_id: int, item: str) -> None:
    db.delete_expense(expense_id)
    st.session_state["flash"] = f"Deleted {item}"


def _edit_expense(expense_id: int) -> None:
    st.session_state["edit_exp"] = expense_id


def page_expenses() -> None:
    flash()
    head, pick = st.columns([1.6, 1], vertical_alignment="bottom")
    with pick:
        d = date_picker("exp")
    with head:
        page_title(f"What did you buy {day_phrase(d)}?", "Log stock purchases such as milk, tea, sugar, cups, ice and gas.")
    st.write("")

    left, right = st.columns([1, 1.35], gap="medium")
    with left, st.container(key="panel-add"):
        panel_head("Add a purchase")
        v = st.session_state.get("exp_form_v", 0)
        items = db.get_choices("items")
        choice = st.selectbox("Item", [NEW_ITEM] + items, index=None, key=f"exp-item-{v}",
                              placeholder="Choose what you bought")
        item = choice
        if choice == NEW_ITEM:
            item = st.text_input("Name of the new item", key=f"exp-new-{v}", placeholder="Cardamom").strip()
            st.caption("It will be in the Item list next time.")
        last_unit = db.last_unit_for(item) if item and item != NEW_ITEM else None
        q1, q2 = st.columns(2)
        qty = q1.number_input("Quantity", min_value=0.0, step=0.5, value=1.0, key=f"exp-qty-{v}")
        unit = q2.selectbox("Unit", db.UNITS, index=db.UNITS.index(last_unit) if last_unit in db.UNITS else 0,
                            key=f"exp-unit-{v}-{item or ''}")
        amount = st.number_input("Total paid (₹)", min_value=0.0, step=10.0, key=f"exp-amt-{v}")
        notes = st.text_input("Note", placeholder="Supplier or bill number (optional)", key=f"exp-note-{v}")
        if st.button("Add purchase", type="primary", width="stretch"):
            if not item:
                st.error("Choose an item, or pick “+ New item…” and type its name.")
            elif amount <= 0:
                st.error("Enter the amount you paid.")
            else:
                db.add_expense(d, item, qty, unit, amount, notes)
                db.add_choice("items", item)
                st.session_state["exp_form_v"] = v + 1
                st.session_state["flash"] = f"Added {item}: {money(amount, 2)}"
                st.rerun()
        list_editor("items", "item", "Purchases")

    with right, st.container(key="panel-list"):
        current = db.get_expenses_for_date(d)
        panel_head(f"Bought {day_phrase(d)}", f'<span class="muted">{money(current["amount"].sum(), 2)} in total</span>')
        if current.empty:
            md('<p class="muted">Nothing logged for this day yet.</p>')
        for r in current.itertuples():
            rid = int(r.id)
            if st.session_state.get("edit_exp") == rid:
                _purchase_editor(r, d)
                continue
            with st.container(key=f"row-exp{rid}"):
                c = st.columns([3, 1.4, 1.3, 0.5, 0.5], vertical_alignment="center", gap="small")
                note = esc(r.notes) if r.notes else ""
                c[0].markdown(f'<div class="drink">{esc(r.item)}<small>{note}</small></div>',
                              unsafe_allow_html=True)
                qty_txt = f"{r.quantity:g} {r.unit or ''}".strip()
                c[1].markdown(f'<div class="muted">{esc(qty_txt)}</div>', unsafe_allow_html=True)
                c[2].markdown(f'<div class="amount" style="color:inherit">{money(r.amount, 2)}</div>', unsafe_allow_html=True)
                c[3].button(":material/edit:", key=f"edit-e{rid}", help=f"Edit {r.item}",
                            on_click=_edit_expense, args=(rid,))
                c[4].button(":material/delete:", key=f"del-{rid}", help=f"Delete {r.item}",
                            on_click=_delete_expense, args=(rid, r.item))


def _purchase_editor(r, d: date) -> None:
    rid = int(r.id)
    with st.container(key=f"row-editexp{rid}"):
        c = st.columns([2.2, 1, 1.1, 1.3], gap="small")
        item = c[0].text_input("Item", value=r.item, key=f"ee-item-{rid}")
        qty = c[1].number_input("Quantity", value=float(r.quantity), min_value=0.0, step=0.5, key=f"ee-qty-{rid}")
        unit = c[2].selectbox("Unit", db.UNITS, index=db.UNITS.index(r.unit) if r.unit in db.UNITS else 0,
                              key=f"ee-unit-{rid}")
        amount = c[3].number_input("Paid (₹)", value=float(r.amount), min_value=0.0, step=10.0, key=f"ee-amt-{rid}")
        c = st.columns([2.2, 1.4, 1, 1], vertical_alignment="bottom", gap="small")
        notes = c[0].text_input("Note", value=r.notes or "", key=f"ee-note-{rid}")
        when = c[1].date_input("Date", value=d, max_value=clock.today(), format="DD/MM/YYYY", key=f"ee-date-{rid}")
        c[2].button("Cancel", key=f"ee-cancel-{rid}", on_click=_stop_editing, args=("edit_exp", "ee-"),
                    width="stretch")
        if c[3].button("Save", key=f"ee-save-{rid}", type="primary", width="stretch"):
            try:
                db.update_expense(rid, when, item, qty, unit, amount, notes)
            except ValueError as exc:
                st.error(str(exc))
            else:
                _stop_editing("edit_exp", "ee-")
                moved = f" (moved to {when:%d %b})" if when != d else ""
                st.session_state["flash"] = f"Updated {item.strip()}{moved}"
                st.rerun()


# ============================================================ Running costs
def _month_options() -> list[date]:
    this = clock.today().replace(day=1)
    months, m = [], this
    for _ in range(12):
        months.append(m)
        m = (m - timedelta(days=1)).replace(day=1)
    rc = db.load_running_costs()
    months += [ts.date().replace(day=1) for ts in rc["date"]]
    return sorted(set(months), reverse=True)


def _delete_cost(cost_id: int, name: str) -> None:
    db.delete_running_cost(cost_id)
    st.session_state["flash"] = f"Deleted {name}"


def _edit_cost(cost_id: int) -> None:
    st.session_state["edit_cost"] = cost_id


def _copy_costs(src: date, dst: date) -> None:
    n = db.copy_monthly_costs(src, dst)
    st.session_state["flash"] = f"Copied {n} cost{'s' if n != 1 else ''} from {src:%B}"


SPREAD_LABEL = {"month": "The whole month", "day": "One day"}


def page_running() -> None:
    flash()
    head, pick = st.columns([1.6, 1], vertical_alignment="bottom")
    with head:
        page_title("Running costs", "Rent, salaries, electricity and other costs of running the café. "
                                    "They are taken off your profit in every report.")
    with pick:
        month = st.selectbox("Month", _month_options(), format_func=lambda m: f"{m:%B %Y}", key="rc-month")
    month_end = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    st.write("")

    left, right = st.columns([1, 1.35], gap="medium")
    with left, st.container(key="panel-rcadd"):
        panel_head(f"Add a cost for {month:%B}")
        v = st.session_state.get("rc_form_v", 0)
        name = name_picker("What for", db.get_choices("costs"), f"rc-name-{v}", "Choose a cost",
                           "Name of the cost")
        amount = st.number_input("Amount (₹)", min_value=0.0, step=100.0, format="%.0f", key=f"rc-amt-{v}")
        if f"rc-spread-{v}" not in st.session_state:
            st.session_state[f"rc-spread-{v}"] = "month"
        spread = st.segmented_control("This cost covers", ["month", "day"], format_func=SPREAD_LABEL.get,
                                      key=f"rc-spread-{v}") or "month"
        when = month
        if spread == "day":
            default = min(max(clock.today(), month), month_end)
            when = st.date_input("Which day", value=default, min_value=month, max_value=month_end,
                                 format="DD/MM/YYYY", key=f"rc-date-{v}")
        notes = st.text_input("Note", placeholder="Optional", key=f"rc-note-{v}")
        st.caption("A whole-month cost such as rent is shared evenly across the month’s days, so no single "
                   "day looks like a loss.")
        if st.button("Add cost", type="primary", width="stretch"):
            try:
                db.add_running_cost(when, name or "", amount, spread, notes)
            except ValueError as exc:
                st.error(str(exc))
            else:
                db.add_choice("costs", name)
                st.session_state["rc_form_v"] = v + 1
                st.session_state["flash"] = f"Added {name}: {money(amount)}"
                st.rerun()
        list_editor("costs", "cost name", "Costs")

    with right, st.container(key="panel-rclist"):
        costs = db.get_running_costs(month)
        total = float(costs["amount"].sum())
        per_day = total / month_end.day
        panel_head(f"{month:%B} costs", f'<span class="muted">{money(total)} in total, about {money(per_day)} a day</span>')
        prev = (month - timedelta(days=1)).replace(day=1)
        prev_monthly = db.get_running_costs(prev)
        prev_monthly = prev_monthly[prev_monthly["spread"] == "month"]
        have = set(costs["name"].str.lower())
        copyable = [n for n in prev_monthly["name"] if n.lower() not in have]
        if copyable:
            st.button(f"Copy {prev:%B}’s monthly costs ({', '.join(copyable[:3])}{'…' if len(copyable) > 3 else ''})",
                      on_click=_copy_costs, args=(prev, month), icon=":material/content_copy:", key="rc-copy")
        if costs.empty:
            md('<p class="muted">No costs entered for this month yet.</p>')
        for r in costs.itertuples():
            rid = int(r.id)
            if st.session_state.get("edit_cost") == rid:
                _cost_editor(r, month, month_end)
                continue
            with st.container(key=f"row-cost{rid}"):
                c = st.columns([3, 1.4, 1.3, 0.5, 0.5], vertical_alignment="center", gap="small")
                note = esc(r.notes) if r.notes else ""
                c[0].markdown(f'<div class="drink">{esc(r.name)}<small>{note}</small></div>', unsafe_allow_html=True)
                covers = "Whole month" if r.spread == "month" else pd.Timestamp(r.cost_date).strftime("%d %b")
                c[1].markdown(f'<div class="muted">{covers}</div>', unsafe_allow_html=True)
                c[2].markdown(f'<div class="amount" style="color:inherit">{money(r.amount)}</div>', unsafe_allow_html=True)
                c[3].button(":material/edit:", key=f"edit-c{rid}", help=f"Edit {r.name}", on_click=_edit_cost,
                            args=(rid,))
                c[4].button(":material/delete:", key=f"del-c{rid}", help=f"Delete {r.name}", on_click=_delete_cost,
                            args=(rid, r.name))


def _cost_editor(r, month: date, month_end: date) -> None:
    rid = int(r.id)
    with st.container(key=f"row-editcost{rid}"):
        c = st.columns([2.2, 1.2, 1.6], gap="small")
        name = c[0].text_input("What for", value=r.name, key=f"ce-name-{rid}")
        amount = c[1].number_input("Amount (₹)", value=float(r.amount), min_value=0.0, step=100.0, format="%.0f",
                                   key=f"ce-amt-{rid}")
        spread = c[2].selectbox("Covers", ["month", "day"], index=0 if r.spread == "month" else 1,
                                format_func=SPREAD_LABEL.get, key=f"ce-spread-{rid}")
        c = st.columns([1.4, 2, 1, 1], vertical_alignment="bottom", gap="small")
        when = month
        if spread == "day":
            current = pd.Timestamp(r.cost_date).date()
            when = c[0].date_input("Which day", value=min(max(current, month), month_end), min_value=month,
                                   max_value=month_end, format="DD/MM/YYYY", key=f"ce-date-{rid}")
        notes = c[1].text_input("Note", value=r.notes or "", key=f"ce-note-{rid}")
        c[2].button("Cancel", key=f"ce-cancel-{rid}", on_click=_stop_editing, args=("edit_cost", "ce-"),
                    width="stretch")
        if c[3].button("Save", key=f"ce-save-{rid}", type="primary", width="stretch"):
            try:
                db.update_running_cost(rid, when, name, amount, spread, notes)
            except ValueError as exc:
                st.error(str(exc))
            else:
                _stop_editing("edit_cost", "ce-")
                st.session_state["flash"] = f"Updated {name.strip()}"
                st.rerun()


# ============================================================== Cost per cup
def _recipe_rows(pid: int) -> list[dict]:
    key = f"recipe-{pid}"
    if key not in st.session_state:
        rec = db.get_recipe(pid)
        st.session_state[key] = [{"uid": i, "item": r.item, "qty": float(r.quantity), "unit": r.unit}
                                 for i, r in enumerate(rec.itertuples())]
        st.session_state[f"{key}-next"] = len(rec)
    return st.session_state[key]


def _add_ingredient(pid: int) -> None:
    key = f"recipe-{pid}"
    uid = st.session_state[f"{key}-next"]
    st.session_state[f"{key}-next"] = uid + 1
    st.session_state[key].append({"uid": uid, "item": None, "qty": 0.0, "unit": "ml"})


def _remove_ingredient(pid: int, uid: int) -> None:
    key = f"recipe-{pid}"
    st.session_state[key] = [r for r in st.session_state[key] if r["uid"] != uid]
    _forget(f"ri-{pid}-{uid}-")


def _reload_recipe(pid: int) -> None:
    st.session_state.pop(f"recipe-{pid}", None)
    _forget(f"ri-{pid}-")


def page_costing() -> None:
    flash()
    t_ = T()
    page_title("Cost per cup", "What goes into each drink, and what each cup earns you. "
                               "Ingredient prices come from your purchases.")
    st.write("")
    table = db.cost_per_cup()
    if table.empty:
        empty("No drinks on the menu", "Add your drinks in <b>Menu and prices</b> first.")
        return
    prices = db.ingredient_prices()

    with st.container(key="panel-cpc"):
        panel_head("Every drink", '<span class="muted">Sorted by profit per cup</span>')
        known = pd.to_numeric(table["profit"], errors="coerce").where(table["problems"].map(len) == 0)
        order = table.assign(_p=known.fillna(-1e9))
        order = order.sort_values("_p", ascending=False)
        rows = []
        for r in order.itertuples():
            if not r.has_recipe:
                cost = profit = margin = '<span class="faint">–</span>'
                note = '<span class="faint">No recipe yet</span>'
            elif r.problems:   # part of the cost is unknown, so profit and margin would be overstated
                cost = f'{money(r.cost, 2)} <span class="faint">+ ?</span>'
                profit = margin = '<span class="faint">–</span>'
                note = f'<span class="down">Missing price: {esc("; ".join(r.problems))}</span>'
            else:
                cost, profit = money(r.cost, 2), money(r.profit, 2)
                margin = f"{r.margin:.0%}" if r.margin is not None else "–"
                note = '<span class="up">Complete</span>'
            rows.append([esc(r.name), money(r.price), cost, profit, margin, note])
        md(html_table([("Drink", False), ("Price", True), ("Cost per cup", True), ("Profit per cup", True),
                       ("Margin", True), ("Recipe", False)], rows))

    st.write("")
    a, b = st.columns([1.6, 1], gap="medium")
    names = dict(zip(table["product_id"], table["name"]))
    sell = dict(zip(table["product_id"], table["price"]))
    with a, st.container(key="panel-recipe"):
        panel_head("Recipe for one cup")
        pid = st.selectbox("Drink", list(names), format_func=names.get, key="cpc-drink")
        rows = _recipe_rows(pid)
        items = sorted(set(db.get_choices("items")) | {r["item"] for r in rows if r["item"]}, key=str.lower)
        if rows:
            h = st.columns([2.4, 1.1, 1, 1.2, 0.5], gap="small")
            for col, label in zip(h, ["Ingredient", "Amount", "Unit", "Cost", ""]):
                col.markdown(f'<span class="muted">{label}</span>', unsafe_allow_html=True)
        else:
            md('<p class="muted">No ingredients yet. Add what goes into one cup, for example 150 ml milk.</p>')
        live, missing = 0.0, []
        for r in rows:
            uid = r["uid"]
            with st.container(key=f"row-ing{pid}-{uid}"):
                c = st.columns([2.4, 1.1, 1, 1.2, 0.5], vertical_alignment="center", gap="small")
                item = c[0].selectbox("Ingredient", items, index=items.index(r["item"]) if r["item"] in items else None,
                                      key=f"ri-{pid}-{uid}-item", placeholder="Choose an ingredient",
                                      accept_new_options=True, label_visibility="collapsed")
                qty = c[1].number_input("Amount", value=float(r["qty"]), min_value=0.0, step=1.0,
                                        key=f"ri-{pid}-{uid}-qty", label_visibility="collapsed")
                unit = c[2].selectbox("Unit", db.RECIPE_UNITS,
                                      index=db.RECIPE_UNITS.index(r["unit"]) if r["unit"] in db.RECIPE_UNITS else 0,
                                      key=f"ri-{pid}-{uid}-unit", label_visibility="collapsed")
                if item and qty:
                    cost, why = db.ingredient_cost(item, qty, unit, prices)
                    if cost is None:
                        missing.append(item)
                        c[3].markdown(f'<div class="amount down" title="{esc(why)}">{esc(why)}</div>',
                                      unsafe_allow_html=True)
                    else:
                        live += cost
                        c[3].markdown(f'<div class="amount">{money(cost, 2)}</div>', unsafe_allow_html=True)
                else:
                    c[3].markdown('<div class="amount faint">–</div>', unsafe_allow_html=True)
                c[4].button(":material/delete:", key=f"del-ing{pid}-{uid}", help="Remove this ingredient",
                            on_click=_remove_ingredient, args=(pid, uid))
        st.write("")
        c = st.columns([1, 1, 1.2], gap="small")
        c[0].button("Add ingredient", on_click=_add_ingredient, args=(pid,), icon=":material/add:",
                    width="stretch", key="ing-add")
        c[1].button("Undo changes", on_click=_reload_recipe, args=(pid,), width="stretch", key="ing-undo")
        if c[2].button("Save recipe", type="primary", width="stretch", key="ing-save"):
            data = [(st.session_state.get(f"ri-{pid}-{r['uid']}-item") or "",
                     st.session_state.get(f"ri-{pid}-{r['uid']}-qty") or 0.0,
                     st.session_state.get(f"ri-{pid}-{r['uid']}-unit") or "ml") for r in rows]
            try:
                db.save_recipe(pid, data)
                for item, _, _ in data:
                    if item and item.strip():
                        db.add_choice("items", item)
            except ValueError as exc:
                st.error(str(exc))
            else:
                _reload_recipe(pid)
                st.session_state["flash"] = f"Saved the recipe for {names[pid]}"
                st.rerun()

    with b, st.container(key="panel-recipe-sum"):
        price = float(sell[pid])
        profit = price - live
        counted = any(r["item"] for r in rows) and not missing
        md(stat_strip([
            {"label": "Sells for", "value": money(price)},
            {"label": "Costs to make", "value": money(live, 2) + ("" if counted else " + ?") if live else "–"},
            {"label": "Profit per cup", "value": money(profit, 2) if counted else "–",
             "color": (t_["good"] if profit >= 0 else t_["bad"]) if counted else None},
            {"label": "Margin", "value": f"{profit / price:.0%}" if counted and price else "–"},
        ]))
        if missing:
            md(f'<p class="down" style="margin-top:14px">Not counted yet: {esc(", ".join(missing))}. Record a purchase '
               f'of these (or pick a unit that matches how you buy them) to include their cost.</p>')
        used = [prices[i.lower()] for i in {r["item"] for r in rows if r["item"]} if i.lower() in prices]
        if used:
            md('<p class="muted" style="margin:18px 0 6px">Prices used</p>' + "".join(
                f'<p style="margin:0 0 4px"><b>{esc(u["item"])}</b>: {money(u["per_unit"], 2)} per {esc(u["unit"])}'
                f' <span class="faint">({esc(u["how"])})</span></p>' for u in used))


# ================================================================= Reports
def report_page(freq: str) -> None:
    flash()
    t_ = T()
    noun = "week" if freq == "W" else "month"
    sales, expenses = db.load_sales(), db.load_expenses()
    rc, pays = running_costs_df(), db.load_payments()

    head, pick = st.columns([1.6, 1], vertical_alignment="bottom")
    with head:
        page_title("Weekly report" if freq == "W" else "Monthly report",
                   "Monday to Sunday, compared with the week before." if freq == "W"
                   else "The whole month, compared with the month before.")
    if sales.empty and expenses.empty:
        st.write("")
        empty("No numbers yet", "Reports appear once you have recorded some sales and purchases.")
        return
    with pick:
        periods = an.available_periods(sales, expenses, freq)
        start = st.selectbox(f"Choose a {noun}", periods, format_func=lambda p: an.period_label(p, freq))

    end = an.period_end(start, freq)
    today = pd.Timestamp(clock.today())
    pstart = an.previous_start(start, freq)
    pend = an.period_end(pstart, freq)
    in_progress = end > today
    if in_progress:
        elapsed = (today - start).days
        end = today
        pend = min(pstart + pd.Timedelta(days=elapsed), pend)
        st.caption(f"This {noun} isn’t over yet, so it is compared with the first {elapsed + 1} day(s) of last {noun}.")

    s, e = an.between(sales, start, end), an.between(expenses, start, end)
    ps, pe = an.between(sales, pstart, pend), an.between(expenses, pstart, pend)
    run = an.running_daily(rc, start, end)
    cur = an.summarize(s, e, run.sum())
    prev = an.summarize(ps, pe, an.running_daily(rc, pstart, pend).sum())
    vs = f"last {noun}"
    md('<div style="height:22px"></div>' + stat_strip([
        {"label": "Sales", "value": money(cur["revenue"]), "color": t_["accent_text"],
         "delta_html": delta_text(an.change(cur["revenue"], prev["revenue"]), vs)},
        {"label": "Cups sold", "value": f"{cur['cups']:,}", "delta_html": delta_text(an.change(cur["cups"], prev["cups"]), vs)},
        {"label": "Spent on stock", "value": money(cur["expense"]),
         "delta_html": delta_text(an.change(cur["expense"], prev["expense"]), vs, invert=True)},
        {"label": "Running costs", "value": money(cur["running"]),
         "delta_html": delta_text(an.change(cur["running"], prev["running"]), vs, invert=True)},
        {"label": "Profit", "value": money(cur["profit"]), "color": t_["good"] if cur["profit"] >= 0 else t_["bad"],
         "delta_html": delta_text(an.change(cur["profit"], prev["profit"]), vs)},
        {"label": "Margin", "value": f"{cur['margin']:.0%}"},
    ]) + '<div style="height:26px"></div>')
    if rc.empty:
        st.caption("Profit here only takes off stock purchases. Add rent, salaries and other costs in "
                   "Running costs for your true profit.")

    with st.container(key="panel-days"):
        items = [("Sales", t_["accent"]), ("Stock spend", t_["expense"])]
        if run.any():
            items.append(("Running costs", t_["running"]))
        panel_head("Day by day", legend(items + [("Profit", t_["good"])]))
        st.plotly_chart(an.daily_chart(s, e, start, end, with_profit=True, running=run), config=CHART, width="stretch")

    cpc = db.cost_per_cup()
    cost_of = {r.name: r.cost for r in cpc.itertuples() if r.has_recipe and not r.problems}

    st.write("")
    a, b = st.columns([1, 1.5], gap="medium")
    with a:
        with st.container(key="panel-mix"):
            panel_head("Hot or cold")
            md(split_bar(cur["hot"], cur["cold"]) if cur["cups"] else '<p class="muted">No sales in this period.</p>')
        with st.container(key="panel-paid"):
            panel_head("How you were paid")
            pt = an.payment_totals(pays, start, end)
            paid = pt["cash"] + pt["upi"] + pt["card"]
            if paid == 0:
                md('<p class="muted">No payment split recorded for these days. Enter cash, UPI and card on '
                   'Record sales.</p>')
            else:
                parts = [("Cash", pt["cash"], t_["good"]), ("UPI", pt["upi"], t_["cold"]), ("Card", pt["card"], t_["accent"])]
                bar = "".join(f'<div style="width:{v / paid * 100:.1f}%;background:{c}"></div>' for _, v, c in parts)
                md(f'<div class="split" role="img" aria-label="Payment split">{bar}</div><div class="paylist">'
                   + "".join(f'<div><i style="background:{c}"></i>{n}<b>{money(v)}</b>'
                             f'<span class="muted" style="width:44px;text-align:right">{v / paid:.0%}</span></div>'
                             for n, v, c in parts) + "</div>")
                gap = cur["revenue"] - paid
                if gap > 1:
                    md(f'<p class="down" style="margin-top:10px">{money(gap)} of sales has no payment type recorded.</p>')
                elif gap < -1:
                    md(f'<p class="down" style="margin-top:10px">Payments are {money(-gap)} more than sales.</p>')
        with st.container(key="panel-best"):
            top = (s.groupby("product").agg(cups=("quantity", "sum"), rev=("revenue", "sum"))
                   .sort_values("cups", ascending=False).head(8))
            if top.empty:
                md('<p class="muted">No sales in this period.</p>')
            else:
                md(menu_board("Bestsellers", [(n, f"{int(r.cups):,}") for n, r in top.iterrows()]))
                earn = s.groupby("product").agg(cups=("quantity", "sum"), rev=("revenue", "sum"))
                earn = earn[earn.index.isin(list(cost_of))]
                if len(earn):
                    earn = earn.assign(profit=earn["rev"] - earn["cups"] * earn.index.map(cost_of)).sort_values(
                        "profit", ascending=False).head(8)
                    md('<div style="height:22px"></div>' + menu_board(
                        "Money makers", [(n, money(r.profit)) for n, r in earn.iterrows()]))
                else:
                    md('<p class="muted" style="margin-top:14px">Add recipes in Cost per cup to see which drinks '
                       'make the most money.</p>')
    with b:
        with st.container(key="panel-spend"):
            panel_head("Where the money went")
            if e.empty:
                md('<p class="muted">No purchases in this period.</p>')
            else:
                st.plotly_chart(an.expense_breakdown(e), config=CHART, width="stretch")
        with st.container(key="panel-extra"):
            if s.empty:
                md('<p class="muted">No sales in this period.</p>')
            elif freq == "M":
                panel_head("Average day, by weekday")
                st.plotly_chart(an.weekday_pattern(s), config=CHART, width="stretch")
            else:
                daily = s.groupby("date")["revenue"].sum()
                star = s.groupby("product")["quantity"].sum().idxmax()
                md(menu_board("Highlights", [
                    ("Best day", f"{daily.idxmax():%a %d %b}, {money(daily.max())}"),
                    ("Slowest day", f"{daily.idxmin():%a %d %b}, {money(daily.min())}"),
                    ("Star drink", star),
                    ("Days open", f"{cur['days']} of {(end - start).days + 1}"),
                    ("Average sales a day", money(cur["revenue"] / max(cur["days"], 1))),
                    ("Stock cost per cup", money(cur["expense"] / max(cur["cups"], 1), 2)),
                ]))

    st.write("")
    with st.container(key="panel-trend"):
        panel_head(f"Last 12 {noun}s", legend([("Sales", t_["accent"]), ("All costs", t_["expense"]), ("Profit", t_["good"])]))
        st.plotly_chart(an.trend_chart(sales, expenses, freq, start, running_costs=rc), config=CHART, width="stretch")

    st.write("")
    tab1, tab2, tab3 = st.tabs(["Drinks", "Stock purchases", "Running costs"])
    with tab1:
        if s.empty:
            md('<p class="muted">No sales in this period.</p>')
        else:
            prod = (s.groupby(["product", "category"], as_index=False)
                    .agg(cups=("quantity", "sum"), revenue=("revenue", "sum")).sort_values("revenue", ascending=False))
            total_rev = prod["revenue"].sum()
            rows = []
            for r in prod.itertuples():
                c = cost_of.get(r.product)
                rows.append([esc(r.product), esc(r.category), f"{int(r.cups):,}", money(r.revenue),
                             money(c, 2) if c is not None else '<span class="faint">–</span>',
                             money(r.revenue - r.cups * c) if c is not None else '<span class="faint">–</span>',
                             f'<span class="bar" style="width:{r.revenue / total_rev * 120:.0f}px"></span>&nbsp; '
                             f'{r.revenue / total_rev:.0%}'])
            md(html_table([("Drink", False), ("Type", False), ("Cups", True), ("Sales", True), ("Cost per cup", True),
                           ("Drink profit", True), ("Share of sales", False)], rows))
            if not cost_of:
                st.caption("Cost per cup and drink profit fill in once drinks have recipes in Cost per cup.")
            st.download_button("Download sales as CSV", s.to_csv(index=False).encode(),
                               f"sales_{start:%Y%m%d}_{end:%Y%m%d}.csv", "text/csv")
    with tab2:
        if e.empty:
            md('<p class="muted">No purchases in this period.</p>')
        else:
            items = (e.groupby(["item", "unit"], dropna=False, as_index=False)
                     .agg(quantity=("quantity", "sum"), amount=("amount", "sum"), n=("amount", "size"))
                     .sort_values("amount", ascending=False))
            rows = [[esc(r.item), esc(f"{r.quantity:g} {r.unit if isinstance(r.unit, str) else ''}"),
                     f"{int(r.n)}", money(r.amount)] for r in items.itertuples()]
            md(html_table([("Item", False), ("Quantity", True), ("Times bought", True), ("Spent", True)], rows))
            st.download_button("Download purchases as CSV", e.to_csv(index=False).encode(),
                               f"purchases_{start:%Y%m%d}_{end:%Y%m%d}.csv", "text/csv")
    with tab3:
        share = [(r, an.running_daily(rc.iloc[[i]], start, end).sum()) for i, r in enumerate(rc.itertuples())]
        share = [(r, v) for r, v in share if v > 0.005]
        if not share:
            md('<p class="muted">No running costs in this period.</p>')
        else:
            rows = [[esc(r.name), "Whole month" if r.spread == "month" else f"{r.date:%d %b}", money(r.amount),
                     money(v)] for r, v in sorted(share, key=lambda x: -x[1])]
            md(html_table([("Cost", False), ("Covers", False), ("Full amount", True), (f"Share in this {noun}", True)],
                          rows))


def page_weekly() -> None:
    report_page("W")


def page_monthly() -> None:
    report_page("M")


# ========================================================== Menu and prices
def _ask_delete(pid: int) -> None:
    st.session_state["confirm_delete"] = pid


def _cancel_delete() -> None:
    st.session_state.pop("confirm_delete", None)


def _do_delete(pid: int, name: str) -> None:
    kept_history = db.delete_product(pid)
    st.session_state.pop("confirm_delete", None)
    st.session_state["flash"] = (f"Deleted {name}. Its past sales stay in your reports." if kept_history
                                 else f"Deleted {name}")


def _safely(action) -> list[str]:
    """Run a wipe-and-replace action; if the backup (or anything) fails, show why and stop."""
    try:
        return action()
    except Exception as exc:
        st.error(f"Stopped, because the backup couldn’t be made: {exc}. Check the Sheet’s tabs before trying "
                 "again.", icon=":material/error:")
        st.stop()


def _with_backup_note(done: str, backups: list[str]) -> str:
    if not backups:
        return done
    where = "tabs" if db.uses_google_sheets() else "backup tables"
    return f"{done}. Backup saved in {where}: " + ", ".join(f"“{b}”" for b in backups)


def page_menu() -> None:
    flash()
    for k in st.session_state.pop("untick", []):   # reset confirmation boxes after a wipe
        st.session_state[k] = False
    page_title("Menu and prices", "Change names and prices, switch a drink off for a while, or delete it. "
                                  "Past sales keep the price they were sold at.")
    st.write("")
    products = db.get_products()

    with st.container(key="panel-menu"):
        h = st.columns([3, 1.4, 1.3, 1, 0.5], gap="small")
        for col, label in zip(h, ["Drink", "Type", "Price (₹)", "On the menu", ""]):
            col.markdown(f'<span class="muted">{label}</span>', unsafe_allow_html=True)
        for p in products.itertuples():
            pid = int(p.id)
            if st.session_state.get("confirm_delete") == pid:
                with st.container(key=f"row-confirm{pid}"):
                    c = st.columns([4.2, 1.3, 1.3], vertical_alignment="center", gap="small")
                    c[0].markdown(f'<div class="drink">Delete {esc(p.name)}?<small>Past sales of this drink stay in '
                                  f'your reports. You can add it back later.</small></div>', unsafe_allow_html=True)
                    c[1].button("Keep it", key=f"keep-{pid}", on_click=_cancel_delete, width="stretch")
                    c[2].button("Delete", key=f"confirmdel-{pid}", type="primary", on_click=_do_delete,
                                args=(pid, p.name), width="stretch")
                continue
            with st.container(key=f"row-m{pid}"):
                c = st.columns([3, 1.4, 1.3, 1, 0.5], vertical_alignment="center", gap="small")
                c[0].text_input("Drink", value=p.name, key=f"m-name-{pid}", label_visibility="collapsed")
                c[1].selectbox("Type", ["Hot", "Cold"], index=0 if p.category == "Hot" else 1, key=f"m-cat-{pid}",
                               label_visibility="collapsed")
                c[2].number_input("Price", value=float(p.price), min_value=0.0, step=5.0, format="%.0f",
                                  key=f"m-price-{pid}", label_visibility="collapsed")
                c[3].toggle("On the menu", value=bool(p.active), key=f"m-on-{pid}", label_visibility="collapsed")
                c[4].button(":material/delete:", key=f"del-p{pid}", help=f"Delete {p.name}", on_click=_ask_delete,
                            args=(pid,))
        st.write("")
        if st.button("Save menu", type="primary"):
            edited = pd.DataFrame([{
                "id": int(p.id),
                "name": st.session_state[f"m-name-{int(p.id)}"],
                "category": st.session_state[f"m-cat-{int(p.id)}"],
                "price": st.session_state[f"m-price-{int(p.id)}"],
                "active": st.session_state[f"m-on-{int(p.id)}"],
            } for p in products.itertuples() if f"m-name-{int(p.id)}" in st.session_state])
            try:
                db.save_products(edited)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["flash"] = "Menu saved"
                st.rerun()

    st.write("")
    a, b = st.columns([1, 1.6], gap="medium")
    with a, st.container(key="panel-newdrink"):
        panel_head("Add a drink")
        with st.form("add_drink", clear_on_submit=True):
            name = st.text_input("Name", placeholder="Rose Milk")
            c1, c2 = st.columns(2)
            cat = c1.selectbox("Type", ["Hot", "Cold"])
            price = c2.number_input("Price (₹)", min_value=0.0, step=5.0, value=50.0, format="%.0f")
            if st.form_submit_button("Add to menu", type="primary", width="stretch"):
                try:
                    db.add_product(name, cat, price)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["flash"] = f"Added {name.strip()} to the menu"
                    st.rerun()
    with b, st.container(key="panel-data"):
        panel_head("Your data")
        x, y, z = st.columns(3, gap="medium")
        with x:
            md('<p><b>Back up</b><br><span class="muted">Your records as CSV files.</span></p>')
            st.download_button("Sales", db.load_sales().to_csv(index=False).encode(), "all_sales.csv", "text/csv",
                               width="stretch", icon=":material/download:")
            st.download_button("Purchases", db.load_expenses().to_csv(index=False).encode(), "all_purchases.csv",
                               "text/csv", width="stretch", icon=":material/download:")
            st.download_button("Running costs", db.load_running_costs().to_csv(index=False).encode(),
                               "all_running_costs.csv", "text/csv", width="stretch", icon=":material/download:")
            st.download_button("Payments", db.load_payments().to_csv(index=False).encode(), "all_payments.csv",
                               "text/csv", width="stretch", icon=":material/download:")
        with y:
            md('<p><b>Try demo data</b><br><span class="muted">Fills 120 days with sample numbers. '
               'Replaces your sales, purchases, running costs and payments; a backup copy is saved first.</span></p>')
            ok = st.checkbox("Replace my data", key="demo_ok")
            if st.button("Load demo data", disabled=not ok, width="stretch"):
                with st.spinner("Backing up, then loading demo data…"):
                    backups = _safely(db.load_demo_data)
                st.session_state["untick"] = ["demo_ok"]
                st.session_state["flash"] = _with_backup_note("Demo data loaded", backups)
                st.rerun()
        with z:
            md('<p><b>Start fresh</b><br><span class="muted">Deletes every sale, purchase, running cost and payment. '
               'Your menu and recipes stay, and a backup copy is saved first.</span></p>')
            ok2 = st.checkbox("Delete everything", key="clear_ok")
            if st.button("Delete all data", disabled=not ok2, width="stretch"):
                with st.spinner("Backing up, then deleting…"):
                    backups = _safely(db.clear_all_data)
                st.session_state["untick"] = ["clear_ok"]
                st.session_state["flash"] = _with_backup_note(
                    "All sales, purchases, running costs and payments deleted", backups)
                st.rerun()
    st.caption(f"Your data is stored in: {db.storage_label()}")


# ============================================================== Navigation
PAGES = {
    "today": st.Page(page_today, title="Today", default=True),
    "sales": st.Page(page_sales, title="Record sales", url_path="sales"),
    "expenses": st.Page(page_expenses, title="Record purchases", url_path="purchases"),
    "running": st.Page(page_running, title="Running costs", url_path="running-costs"),
    "weekly": st.Page(page_weekly, title="Weekly report", url_path="weekly"),
    "monthly": st.Page(page_monthly, title="Monthly report", url_path="monthly"),
    "costing": st.Page(page_costing, title="Cost per cup", url_path="cost-per-cup"),
    "menu": st.Page(page_menu, title="Menu and prices", url_path="menu"),
}

# Register the pages first (hidden while logged out) so a link like /menu opens that page after login.
online = db.uses_google_sheets()
locked = auth.needs_login(online)
nav = st.navigation(list(PAGES.values()), position="hidden" if locked else "sidebar")
if locked:
    auth.require_login(online)  # shows the login screen and stops

try:
    db.init_db()
except db.StorageError as exc:
    st.error(f"Can’t reach your data. {exc}", icon=":material/cloud_off:")
    st.stop()

sidebar_brand()
if "_theme_seg" not in st.session_state:
    st.session_state["_theme_seg"] = current_theme()
theme_switch()
if online:
    st.sidebar.button("Refresh data", on_click=db.refresh, icon=":material/refresh:", key="refresh-data",
                      help="Show changes made directly in the Google Sheet right away")
auth.logout_button()
nav.run()

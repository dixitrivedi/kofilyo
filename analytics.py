"""Period maths, summaries and Plotly charts drawn in the current theme."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

import clock
from theme import CURRENCY, T

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CHART_CONFIG = {"displayModeBar": False}


# ------------------------------------------------------------ period maths
def period_start(ts: pd.Timestamp, freq: str) -> pd.Timestamp:
    ts = pd.Timestamp(ts).normalize()
    if freq == "W":
        return ts - pd.Timedelta(days=ts.weekday())
    return ts.replace(day=1)


def period_end(start: pd.Timestamp, freq: str) -> pd.Timestamp:
    if freq == "W":
        return start + pd.Timedelta(days=6)
    return start + pd.offsets.MonthEnd(0)


def previous_start(start: pd.Timestamp, freq: str) -> pd.Timestamp:
    if freq == "W":
        return start - pd.Timedelta(days=7)
    return (start - pd.Timedelta(days=1)).replace(day=1)


def period_label(start: pd.Timestamp, freq: str) -> str:
    if freq == "W":
        end = period_end(start, freq)
        return f"{start:%d %b} to {end:%d %b %Y}"
    return f"{start:%B %Y}"


def available_periods(sales: pd.DataFrame, expenses: pd.DataFrame, freq: str) -> list[pd.Timestamp]:
    dates = pd.concat([sales["date"], expenses["date"]])
    starts = {period_start(pd.Timestamp(clock.today()), freq)}
    starts.update(period_start(d, freq) for d in dates.dropna().unique())
    return sorted(starts, reverse=True)


def between(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return df[(df["date"] >= start) & (df["date"] <= end)]


def running_daily(rc: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Running costs per day between start and end. A whole-month cost (rent) is shared evenly over
    the days of its month; a one-day cost lands on its date."""
    days = pd.date_range(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize(), freq="D")
    out = pd.Series(0.0, index=days)
    if rc is None or rc.empty or not len(days):
        return out
    for r in rc.itertuples():
        when = pd.Timestamp(r.date).normalize()
        if r.spread == "month":
            m0 = when.replace(day=1)
            m1 = m0 + pd.offsets.MonthEnd(0)
            lo, hi = max(m0, days[0]), min(m1, days[-1])
            if lo <= hi:
                out[lo:hi] += r.amount / m1.day
        elif days[0] <= when <= days[-1]:
            out[when] += r.amount
    return out


def summarize(s: pd.DataFrame, e: pd.DataFrame, running: float = 0.0) -> dict:
    revenue = float(s["revenue"].sum())
    expense = float(e["amount"].sum())
    running = float(running)
    profit = revenue - expense - running
    by_cat = s.groupby("category")["quantity"].sum()
    return {
        "revenue": revenue, "expense": expense, "running": running, "profit": profit,
        "margin": profit / revenue if revenue else 0.0,
        "cups": int(s["quantity"].sum()),
        "hot": int(by_cat.get("Hot", 0)), "cold": int(by_cat.get("Cold", 0)),
        "days": int(s["date"].nunique()),
    }


def change(cur: float, prev: float) -> float | None:
    if not prev:
        return None
    return (cur - prev) / abs(prev)


# ------------------------------------------------------------------ charts
def _style(fig: go.Figure, height: int, money_axis: bool = True) -> go.Figure:
    t = T()
    fig.update_layout(
        height=height, showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Familjen Grotesk, sans-serif", color=t["muted"], size=13),
        margin=dict(l=4, r=4, t=8, b=4), bargap=0.28, bargroupgap=0.1,
        hoverlabel=dict(bgcolor=t["surface2"], bordercolor=t["accent"], font=dict(color=t["text"], size=13)),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=t["line2"], ticks="", tickfont=dict(color=t["faint"]))
    fig.update_yaxes(gridcolor=t["line"], zeroline=False, ticks="", tickfont=dict(color=t["faint"]),
                     tickprefix=CURRENCY if money_axis else "", separatethousands=True)
    return fig


def daily_chart(s: pd.DataFrame, e: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
                height: int = 300, with_profit: bool = False, running: pd.Series | None = None) -> go.Figure:
    t = T()
    days = pd.date_range(start, end, freq="D")
    rev = s.groupby("date")["revenue"].sum().reindex(days, fill_value=0)
    exp = e.groupby("date")["amount"].sum().reindex(days, fill_value=0)
    run = (running if running is not None else pd.Series(0.0, index=days)).reindex(days, fill_value=0)
    fig = go.Figure()
    fig.add_bar(x=days, y=rev, name="Sales", offsetgroup="sales", marker=dict(color=t["accent"], cornerradius=5),
                hovertemplate=f"%{{x|%a %d %b}}<br>Sales {CURRENCY}%{{y:,.0f}}<extra></extra>")
    fig.add_bar(x=days, y=exp, name="Stock spend", offsetgroup="costs", marker=dict(color=t["expense"]),
                hovertemplate=f"%{{x|%a %d %b}}<br>Stock spend {CURRENCY}%{{y:,.0f}}<extra></extra>")
    if run.any():  # stacked on top of stock spend, so the costs bar shows everything paid out that day
        fig.add_bar(x=days, y=run, base=exp, name="Running costs", offsetgroup="costs",
                    marker=dict(color=t["running"]),
                    hovertemplate=f"%{{x|%a %d %b}}<br>Running costs {CURRENCY}%{{y:,.0f}}<extra></extra>")
    if with_profit:
        fig.add_scatter(x=days, y=rev - exp - run, name="Profit", mode="lines+markers",
                        line=dict(color=t["good"], width=2.5), marker=dict(size=6),
                        hovertemplate=f"%{{x|%a %d %b}}<br>Profit {CURRENCY}%{{y:,.0f}}<extra></extra>")
    fig.update_layout(barmode="group", hovermode="x unified")
    if len(days) > 7:
        fig.update_xaxes(tickformat="%d %b")
    else:
        fig.update_xaxes(tickformat="%a %d", dtick=86_400_000, tick0=days[0])
    return _style(fig, height)


def payment_totals(payments: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    p = between(payments, start, end)
    return {"cash": float(p["cash"].sum()), "upi": float(p["upi"].sum()), "card": float(p["card"].sum()),
            "days": int(len(p))}


def expense_breakdown(e: pd.DataFrame) -> go.Figure:
    t = T()
    g = e.groupby("item")["amount"].sum().sort_values(ascending=False)
    if len(g) > 8:  # keep the chart readable: top 7 items plus the rest together
        g = pd.concat([g.iloc[:7], pd.Series({"Everything else": g.iloc[7:].sum()})])
    g = g.iloc[::-1]
    colors = [t["expense"]] * len(g)
    if len(g):
        colors[int(g.values.argmax())] = t["accent"]
    fig = go.Figure(go.Bar(
        x=g.values, y=g.index, orientation="h", marker=dict(color=colors, cornerradius=5),
        text=[f"{CURRENCY}{v:,.0f}" for v in g.values], textposition="outside", cliponaxis=False,
        textfont=dict(color=t["text"]), hovertemplate=f"%{{y}}<br>{CURRENCY}%{{x:,.0f}}<extra></extra>",
    ))
    fig = _style(fig, max(220, 36 * len(g) + 40))
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, g.max() * 1.3 if len(g) else 1],
                     linecolor="rgba(0,0,0,0)")
    fig.update_yaxes(showgrid=False, tickprefix="", tickfont=dict(color=t["muted"], size=14))
    return fig


def weekday_pattern(s: pd.DataFrame) -> go.Figure:
    t = T()
    daily = s.groupby("date", as_index=False).agg(cups=("quantity", "sum"), revenue=("revenue", "sum"))
    daily["wd"] = daily["date"].dt.weekday
    g = daily.groupby("wd")[["cups", "revenue"]].mean().reindex(range(7), fill_value=0)
    best = int(g["revenue"].idxmax()) if g["revenue"].any() else -1
    fig = go.Figure(go.Bar(
        x=WEEKDAYS, y=g["revenue"], customdata=g["cups"],
        marker=dict(color=[t["accent"] if i == best else t["expense"] for i in range(7)], cornerradius=6),
        hovertemplate=f"%{{x}}<br>Average sales {CURRENCY}%{{y:,.0f}}<br>Average cups %{{customdata:,.0f}}<extra></extra>",
    ))
    return _style(fig, 260)


def trend_chart(sales: pd.DataFrame, expenses: pd.DataFrame, freq: str, upto: pd.Timestamp,
                n: int = 12, running_costs: pd.DataFrame | None = None) -> go.Figure:
    t = T()
    starts = [upto]
    for _ in range(n - 1):
        starts.append(previous_start(starts[-1], freq))
    starts = starts[::-1]
    s = sales.assign(p=sales["date"].map(lambda d: period_start(d, freq)))
    e = expenses.assign(p=expenses["date"].map(lambda d: period_start(d, freq)))
    rev = s.groupby("p")["revenue"].sum().reindex(starts, fill_value=0)
    exp = e.groupby("p")["amount"].sum().reindex(starts, fill_value=0)
    run = running_daily(running_costs, starts[0], period_end(starts[-1], freq))
    run = run.groupby(run.index.map(lambda d: period_start(d, freq))).sum().reindex(starts, fill_value=0)
    exp = exp + run.values      # all money paid out: stock + running costs
    active = (rev != 0) | (exp != 0)
    if active.any():
        first = int(active.values.argmax())
        rev, exp, starts = rev.iloc[first:], exp.iloc[first:], starts[first:]
    labels = [f"{x:%d %b}" if freq == "W" else f"{x:%b %y}" for x in starts]
    fig = go.Figure()
    fig.add_bar(x=labels, y=rev - exp, name="Profit", marker=dict(color=t["good"], opacity=0.55, cornerradius=5),
                hovertemplate=f"{CURRENCY}%{{y:,.0f}}<extra>Profit</extra>")
    fig.add_scatter(x=labels, y=rev, name="Sales", mode="lines+markers", line=dict(color=t["accent"], width=3),
                    marker=dict(size=7), hovertemplate=f"{CURRENCY}%{{y:,.0f}}<extra>Sales</extra>")
    fig.add_scatter(x=labels, y=exp, name="All costs", mode="lines+markers",
                    line=dict(color=t["expense"], width=2.5, dash="dot"), marker=dict(size=6),
                    hovertemplate=f"{CURRENCY}%{{y:,.0f}}<extra>All costs</extra>")
    fig.update_layout(hovermode="x unified")
    return _style(fig, 300)

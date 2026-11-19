"""Espresso-bar look: dark and light themes, CSS and small HTML building blocks."""
from __future__ import annotations

import html

import streamlit as st

BRAND_NAME = "Kofilyo"
CURRENCY = "₹"

THEMES = {
    "dark": {
        "bg": "#1E130D", "surface": "#2A1C14", "surface2": "#33231A", "line": "#3A281D", "line2": "#5A4233",
        "text": "#F6EADB", "muted": "#CDB8A4", "faint": "#A88F7B",
        "accent": "#FF8C1A", "accent_text": "#FF8C1A", "accent_soft": "#FFB366", "on_accent": "#1E130D",
        "cold": "#8CC2FF", "expense": "#7A5C49", "running": "#C4A27F", "good": "#8FD6B4", "bad": "#FF9C8A",
    },
    "light": {
        "bg": "#FFFFFF", "surface": "#FBF4EC", "surface2": "#FFFFFF", "line": "#EFE3D6", "line2": "#D9C6B3",
        "text": "#24160F", "muted": "#6B5444", "faint": "#8C7462",
        "accent": "#FF8C1A", "accent_text": "#B85A00", "accent_soft": "#FFC48A", "on_accent": "#24160F",
        "cold": "#2F6FD0", "expense": "#B9A08C", "running": "#DEC9B3", "good": "#1E7A50", "bad": "#B8322A",
    },
}


# ------------------------------------------------------------------ theme state
def current_theme() -> str:
    if "theme" not in st.session_state:
        qp = st.query_params.get("theme", "dark")
        st.session_state.theme = qp if qp in THEMES else "dark"
    return st.session_state.theme


def T() -> dict:
    return THEMES[current_theme()]


def _on_theme_change() -> None:
    choice = st.session_state.get("_theme_seg")
    if choice in THEMES:
        st.session_state.theme = choice
    else:  # segmented control was deselected; keep the current theme selected
        st.session_state._theme_seg = st.session_state.theme


def theme_switch() -> None:
    st.sidebar.segmented_control(
        "Theme", options=["dark", "light"], key="_theme_seg",
        format_func=lambda t: ":material/dark_mode: Dark" if t == "dark" else ":material/light_mode: Light",
        on_change=_on_theme_change, label_visibility="collapsed",
    )
    st.query_params["theme"] = current_theme()


# ------------------------------------------------------------------------- CSS
def _css(t: dict) -> str:
    vars_ = ";".join(f"--{k.replace('_', '-')}:{v}" for k, v in t.items())
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;800&family=Familjen+Grotesk:wght@400;500;600&display=swap');
:root {{ {vars_}; }}

/* canvas */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: var(--bg) !important; color: var(--text); }}
header[data-testid="stHeader"] {{ background: transparent !important; }}
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp li, .stApp td, .stApp th,
.stApp h1, .stApp h2, .stApp h3, .stApp dt, .stApp dd {{ font-family: 'Familjen Grotesk', sans-serif !important; }}
.stApp p, .stApp label, .stApp li, .stApp dt, .stApp dd, .stMarkdown, [data-testid="stWidgetLabel"] p {{ color: var(--text); }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: var(--muted) !important; }}
.block-container {{ max-width: 1240px; padding: 2.4rem 3rem 4rem !important; }}
@media (max-width: 640px) {{ .block-container {{ padding: 1.5rem 1rem 3rem !important; }} }}
.display {{ font-family: 'Big Shoulders Display', sans-serif !important; letter-spacing: .01em; }}
hr {{ border-color: var(--line) !important; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: var(--bg) !important; border-right: 1px solid var(--line); }}
[data-testid="stSidebarContent"] {{ display: flex; flex-direction: column; }}
[data-testid="stSidebarHeader"] {{ order: -2; }}
[data-testid="stSidebarUserContent"] {{ order: -1; padding-bottom: .5rem; }}
[data-testid="stSidebarNav"] a {{ background: transparent !important; position: relative; padding-left: 22px !important; }}
[data-testid="stSidebarNav"] a span {{ color: var(--muted) !important; font-size: 1rem !important; font-family: 'Familjen Grotesk', sans-serif !important; }}
[data-testid="stSidebarNav"] a:hover span {{ color: var(--text) !important; }}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: var(--accent-text) !important; font-weight: 600 !important; }}
[data-testid="stSidebarNav"] a[aria-current="page"]::before {{ content: ""; position: absolute; left: 4px; top: 50%;
  width: 8px; height: 8px; margin-top: -4px; border-radius: 50%; background: var(--accent); }}
[data-testid="stSidebarNavSeparator"] {{ display: none; }}
.brand {{ display: flex; align-items: center; gap: 12px; margin: 4px 0 18px; }}
.brand-name {{ font-family: 'Big Shoulders Display', sans-serif; font-weight: 800; font-size: 34px; line-height: 1; letter-spacing: .02em; color: var(--text); }}

/* inputs */
.stApp [data-baseweb="input"], .stApp [data-baseweb="base-input"], .stApp [data-baseweb="select"] > div,
.stApp [data-baseweb="textarea"] {{ background: var(--surface2) !important; border-color: var(--line2) !important; border-radius: 12px !important; }}
.stApp [data-baseweb="input"]:focus-within, .stApp [data-baseweb="select"] > div:focus-within {{ border-color: var(--accent) !important; }}
.stApp input, .stApp textarea, .stApp [data-baseweb="select"] div {{ color: var(--text) !important; -webkit-text-fill-color: var(--text); }}
.stApp input::placeholder, .stApp textarea::placeholder {{ color: var(--faint) !important; -webkit-text-fill-color: var(--faint); }}
.stApp [data-baseweb="select"] svg {{ fill: var(--muted) !important; }}
[data-testid="stNumberInputContainer"] button {{ background: var(--surface2) !important; color: var(--text) !important; }}
[data-baseweb="popover"] > div, [data-baseweb="popover"] ul, [data-baseweb="menu"], [role="listbox"] {{ background: var(--surface) !important; }}
[data-baseweb="popover"] li {{ color: var(--text) !important; background: transparent; }}
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] {{ background: var(--surface2) !important; }}
[data-baseweb="calendar"], [data-baseweb="calendar"] > div, [data-baseweb="calendar"] [role="grid"],
[data-baseweb="calendar"] [role="presentation"] {{ background: var(--surface) !important; }}
[data-baseweb="calendar"] div, [data-baseweb="calendar"] button {{ color: var(--text); }}
[data-baseweb="calendar"] svg {{ fill: var(--text) !important; }}
[data-testid="stForm"] {{ border: 0 !important; padding: 0 !important; }}
.stApp [data-baseweb="input"] button, .stApp [data-baseweb="base-input"] button {{ color: var(--muted) !important; background: transparent !important; }}
.stApp [data-baseweb="input"] button svg {{ fill: var(--muted) !important; color: var(--muted) !important; }}

/* buttons */
.stButton button, .stDownloadButton button, .stFormSubmitButton button, [data-testid="stPageLink"] a {{
  border-radius: 999px !important; border: 1px solid var(--line2) !important; background: transparent !important;
  color: var(--text) !important; min-height: 44px; padding: .5rem 1.3rem !important; font-weight: 500; }}
.stButton button:hover, .stDownloadButton button:hover, .stFormSubmitButton button:hover,
[data-testid="stPageLink"] a:hover {{ border-color: var(--accent) !important; color: var(--accent-text) !important; }}
.stButton button p, .stDownloadButton button p, .stFormSubmitButton button p, [data-testid="stPageLink"] a span {{ color: inherit !important; font-weight: inherit; }}
.stApp button[kind="primary"], .stApp button[data-testid="stBaseButton-primary"],
.stApp button[data-testid="stBaseButtonPrimary"], .stApp button[kind="primaryFormSubmit"],
.stApp button[data-testid="stBaseButton-primaryFormSubmit"], .st-key-cta-primary a {{
  background: var(--accent) !important; color: var(--on-accent) !important; border: 0 !important; font-weight: 600 !important; }}
.stApp button[kind="primary"]:hover, .stApp button[data-testid="stBaseButton-primary"]:hover,
.stApp button[data-testid="stBaseButton-primaryFormSubmit"]:hover, .st-key-cta-primary a:hover {{
  background: var(--accent-soft) !important; color: var(--on-accent) !important; }}
.stApp button:focus-visible, .stApp a:focus-visible {{ outline: 3px solid var(--accent-soft) !important; outline-offset: 2px; }}
[data-testid="stPageLink"] a {{ justify-content: center; }}

/* segmented controls */
.stApp [data-testid="stButtonGroup"] button {{ background: var(--surface) !important; border-color: var(--line) !important; color: var(--muted) !important; }}
.stApp [data-testid="stButtonGroup"] button p {{ color: inherit !important; }}
.stApp [data-testid="stButtonGroup"] button[data-testid$="Active"] {{ background: var(--text) !important; color: var(--bg) !important; border-color: var(--text) !important; }}

/* steppers on the sales page */
[class*="st-key-dec-"] button, [class*="st-key-inc-"] button {{ width: 44px; height: 44px; min-height: 44px; padding: 0 !important;
  border-radius: 50% !important; font-size: 22px !important; }}
[class*="st-key-inc-"] button {{ background: var(--accent) !important; color: var(--on-accent) !important; border: 0 !important; font-weight: 600; }}
[class*="st-key-inc-"] button:hover {{ background: var(--accent-soft) !important; color: var(--on-accent) !important; }}
[class*="st-key-qty-"] [data-testid="stNumberInputStepDown"], [class*="st-key-qty-"] [data-testid="stNumberInputStepUp"] {{ display: none; }}
[class*="st-key-qty-"] [data-baseweb="input"] {{ background: var(--bg) !important; border: 0 !important; }}
[class*="st-key-qty-"] input {{ text-align: center; font-family: 'Big Shoulders Display', sans-serif !important; font-size: 26px !important; font-weight: 600; padding: 4px 0 !important; }}
[class*="st-key-row-"] {{ border-top: 1px solid var(--line); padding-top: 10px; }}
[class*="st-key-row-confirm"] {{ background: var(--surface2); border: 1px solid var(--bad); border-radius: 16px; padding: 10px 14px; }}
.stApp [class*="st-key-confirmdel-"] button, .stApp [class*="st-key-confirmdel-"] button:hover {{
  background: var(--bad) !important; color: #FFFFFF !important; }}
.stApp [class*="st-key-confirmdel-"] button:hover {{ filter: brightness(1.1); }}
[class*="st-key-row-"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .6rem; }}
[class*="st-key-row-"] [data-testid="stColumn"] {{ min-width: 0 !important; }}
[class*="st-key-del-"] button {{ width: 44px; padding: 0 !important; border-color: transparent !important; color: var(--faint) !important; }}
[class*="st-key-edit-"] button {{ width: 44px; padding: 0 !important; border-color: transparent !important; color: var(--faint) !important; }}
[class*="st-key-edit-"] button:hover {{ color: var(--accent-text) !important; border-color: var(--accent) !important; }}
[class*="st-key-del-"] button:hover {{ color: var(--bad) !important; border-color: var(--bad) !important; }}

/* panels */
[class*="st-key-panel"] {{ background: var(--surface); border-radius: 24px; padding: 24px 28px 20px; }}
[class*="st-key-savebar"] {{ border: 1px solid var(--line); border-radius: 24px; padding: 14px 18px 14px 28px; }}
@media (max-width: 640px) {{ [class*="st-key-panel"] {{ padding: 18px 16px; }} }}

/* tabs, alerts, toasts, toggles */
[data-baseweb="tab-list"] button p {{ color: var(--muted) !important; font-size: 1rem; }}
[data-baseweb="tab-list"] button[aria-selected="true"] p {{ color: var(--accent-text) !important; font-weight: 600; }}
[data-baseweb="tab-highlight"] {{ background: var(--accent) !important; }}
[data-baseweb="tab-border"] {{ background: var(--line) !important; }}
[data-testid="stAlert"] > div {{ background: var(--surface) !important; color: var(--text) !important; border-radius: 16px; }}
[data-testid="stToast"] {{ background: var(--surface2) !important; color: var(--text) !important; border: 1px solid var(--line2); }}
[data-testid="stToast"] p {{ color: var(--text) !important; }}
[data-testid="stCheckbox"] p {{ color: var(--text) !important; }}

/* display type: beat Streamlit's own heading rules */
.stApp h1.page-title, .stApp h1.hero-num, .stApp h3.board-h, .stApp .group-h h3 {{
  font-family: 'Big Shoulders Display', sans-serif !important; padding: 0 !important; }}
.stApp h1.page-title {{ margin: 0 0 4px !important; font-size: clamp(44px, 6vw, 64px) !important; font-weight: 800 !important; line-height: .92 !important; color: var(--text) !important; }}
.stApp h1.hero-num {{ margin: 6px 0 0 !important; font-size: clamp(72px, 9vw, 128px) !important; font-weight: 800 !important; line-height: .82 !important; color: var(--accent-text) !important; }}
.stApp h3.board-h {{ font-size: 30px !important; font-weight: 800 !important; letter-spacing: .04em; color: var(--accent-text) !important; margin: 0 0 14px !important; }}
.stApp .group-h h3 {{ font-size: 34px !important; font-weight: 800 !important; letter-spacing: .04em; }}
.stApp .panel-h h3 {{ font-size: 20px !important; font-weight: 600 !important; padding: 0 !important; color: var(--text) !important; }}
.stApp button p {{ font-size: 15px; }}
[class*="st-key-dec-"] button p, [class*="st-key-inc-"] button p {{ font-size: 24px !important; line-height: 1; font-weight: 600; }}
[class*="st-key-row-"] [data-testid="stMarkdownContainer"] > div, [class*="st-key-row-"] [data-testid="stMarkdownContainer"] p {{ margin-bottom: 0 !important; }}
[class*="st-key-del-"] [data-testid="stIconMaterial"] {{ color: inherit !important; }}

.stApp p.hero-sub {{ margin-top: 30px !important; }}
.stApp p.page-sub {{ margin-top: 14px !important; }}

/* html building blocks */
.muted {{ color: var(--muted); }}
.faint {{ color: var(--faint); }}
.up {{ color: var(--good); }} .down {{ color: var(--bad); }}
.page-title {{ margin: 0; font-family: 'Big Shoulders Display', sans-serif; font-weight: 800; font-size: 60px; line-height: .92; color: var(--text); }}
.page-sub {{ margin: 10px 0 0; font-size: 17px; color: var(--muted); }}
.hero-num {{ margin: 0; font-family: 'Big Shoulders Display', sans-serif; font-weight: 800; font-size: clamp(84px, 11vw, 148px);
  line-height: .82; color: var(--accent-text); }}
.hero-sub {{ margin: 26px 0 0; font-size: 18px; color: var(--muted); }}
.hero {{ display: flex; align-items: flex-end; gap: 56px; flex-wrap: wrap; margin: 6px 0 34px; }}
.strip {{ margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 28px 40px; flex: 1 1 380px; padding-bottom: 6px; }}
.strip dt {{ font-size: 15px; color: var(--muted) !important; }}
.strip dd {{ margin: 6px 0 0; font-family: 'Big Shoulders Display', sans-serif !important; font-weight: 600; font-size: 48px; line-height: 1; }}
.strip dd {{ white-space: nowrap; }}
.strip:has(> div:nth-child(4)) {{ gap: 24px 28px; }}
.strip:has(> div:nth-child(4)) dd {{ font-size: 42px; }}
.strip:has(> div:nth-child(5)) {{ grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }}
.strip:has(> div:nth-child(5)) dd {{ font-size: 36px; }}
.stApp button p {{ white-space: nowrap; }}
.paylist {{ display: flex; flex-direction: column; gap: 8px; margin-top: 14px; font-size: 16px; }}
.paylist div {{ display: flex; align-items: center; gap: 10px; }}
.paylist i {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
.paylist b {{ margin-left: auto; font-weight: 600; }}
.strip .delta {{ display: block; margin-top: 6px; font-family: 'Familjen Grotesk', sans-serif; font-size: 14px; font-weight: 400; }}
.panel-h {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }}
.panel-h h3 {{ margin: 0; padding: 0; font-size: 20px; font-weight: 600; color: var(--text); }}
.board-h {{ margin: 0 0 14px; padding: 0; font-family: 'Big Shoulders Display', sans-serif !important; font-weight: 800; font-size: 30px; letter-spacing: .04em; color: var(--accent-text); }}
.legend {{ display: flex; gap: 18px; font-size: 14px; color: var(--muted); }}
.legend span {{ display: inline-flex; align-items: center; gap: 8px; }}
.legend i {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
.board {{ margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 12px; font-size: 17px; }}
.board li {{ display: flex; align-items: baseline; gap: 10px; margin: 0; }}
.board .dots {{ flex-grow: 1; border-bottom: 2px dotted var(--line2); transform: translateY(-4px); }}
.board b {{ font-weight: 600; }}
.split {{ display: flex; height: 18px; border-radius: 9px; overflow: hidden; background: var(--line); }}
.split-legend {{ display: flex; justify-content: space-between; margin-top: 12px; font-size: 15px; }}
.drink {{ font-size: 18px; font-weight: 500; line-height: 1.2; color: var(--text); }}
.drink small {{ display: block; font-size: 14px; color: var(--faint); font-weight: 400; margin-top: 2px; }}
.amount {{ text-align: right; font-size: 16px; color: var(--muted); }}
.group-h {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }}
.group-h h3 {{ margin: 0; padding: 0; font-family: 'Big Shoulders Display', sans-serif !important; font-weight: 800; font-size: 32px; letter-spacing: .04em; }}
.total-num {{ font-family: 'Big Shoulders Display', sans-serif; font-weight: 800; font-size: 44px; color: var(--accent-text); line-height: 1; }}
.tbl-wrap {{ overflow-x: auto; }}
.tbl {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
.stApp .tbl, .stApp .tbl th, .stApp .tbl td {{ border-left: 0 !important; border-right: 0 !important; border-top: 0 !important; }}
.stApp .tbl {{ border: 0 !important; }}
.tbl th {{ text-align: left; font-weight: 400; color: var(--muted); padding: 10px 12px 10px 0; border-bottom: 1px solid var(--line2); }}
.tbl td {{ padding: 11px 12px 11px 0; border-bottom: 1px solid var(--line); color: var(--text); }}
.tbl .r {{ text-align: right; }}
.tbl .bar {{ display: inline-block; height: 6px; border-radius: 3px; background: var(--accent); vertical-align: middle; }}
.empty {{ padding: 40px 28px; border: 2px dashed var(--line2); border-radius: 24px; color: var(--muted); font-size: 17px; }}
.empty strong {{ display: block; font-family: 'Big Shoulders Display', sans-serif; font-size: 36px; color: var(--text); margin-bottom: 6px; }}
</style>
"""


def apply_theme() -> None:
    st.markdown(_css(T()), unsafe_allow_html=True)


# --------------------------------------------------------------- HTML helpers
def esc(v) -> str:
    return html.escape(str(v))


def money(v: float, decimals: int = 0) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}{CURRENCY}{abs(v):,.{decimals}f}"


def md(html_str: str) -> None:
    st.markdown(html_str, unsafe_allow_html=True)


def sidebar_brand() -> None:
    t = T()
    st.sidebar.markdown(
        f"""<div class="brand"><svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true">
        <circle cx="20" cy="20" r="18" fill="{t['accent']}"></circle>
        <path d="M20 6 C 23 10, 25 12, 28 12" stroke="{t['bg']}" stroke-width="2.5" fill="none" stroke-linecap="round"></path></svg>
        <div class="brand-name">{esc(BRAND_NAME)}</div></div>""",
        unsafe_allow_html=True,
    )


def page_title(title: str, sub: str | None = None) -> None:
    md(f'<h1 class="page-title">{esc(title)}</h1>' + (f'<p class="page-sub">{esc(sub)}</p>' if sub else ""))


def delta_text(delta: float | None, noun: str, invert: bool = False) -> str:
    """'8.8% less than yesterday' coloured good/bad. `invert`: a rise is bad (spend)."""
    if delta is None:
        return '<span class="delta faint">no earlier figure to compare</span>'
    if abs(delta) < 0.0005:
        return f'<span class="delta muted">same as {noun}</span>'
    good = (delta > 0) != invert
    word = "more" if delta > 0 else "less"
    return f'<span class="delta {"up" if good else "down"}">{abs(delta):.1%} {word} than {noun}</span>'


def stat_strip(items: list[dict]) -> str:
    """items: label, value, optional delta_html, optional color."""
    cells = []
    for it in items:
        color = f' style="color:{it["color"]}"' if it.get("color") else ""
        cells.append(f'<div><dt>{esc(it["label"])}</dt><dd{color}>{esc(it["value"])}{it.get("delta_html", "")}</dd></div>')
    return f'<dl class="strip">{"".join(cells)}</dl>'


def panel_head(title: str, right_html: str = "") -> None:
    md(f'<div class="panel-h"><h3>{esc(title)}</h3>{right_html}</div>')


def legend(items: list[tuple[str, str]]) -> str:
    return '<div class="legend">' + "".join(f'<span><i style="background:{c}"></i>{esc(n)}</span>' for n, c in items) + "</div>"


def split_bar(hot: int, cold: int) -> str:
    t = T()
    total = hot + cold
    hp = hot / total * 100 if total else 0
    cp = cold / total * 100 if total else 0
    return (f'<div class="split" role="img" aria-label="{hot} hot cups and {cold} cold cups">'
            f'<div style="width:{hp:.1f}%;background:{t["accent"]}"></div>'
            f'<div style="width:{cp:.1f}%;background:{t["cold"]}"></div></div>'
            f'<div class="split-legend"><span><b>{hot:,}</b> hot cups</span><span><b>{cold:,}</b> cold cups</span></div>')


def menu_board(title: str, rows: list[tuple[str, str]]) -> str:
    items = "".join(f'<li><span>{esc(n)}</span><span class="dots"></span><b>{esc(v)}</b></li>' for n, v in rows)
    head = f'<h3 class="board-h">{esc(title)}</h3>' if title else ""
    return f'{head}<ol class="board">{items}</ol>'


def html_table(headers: list[tuple[str, bool]], rows: list[list[str]]) -> str:
    """headers: (label, right_aligned). Cells are pre-escaped HTML."""
    head = "".join(f'<th class="{"r" if r else ""}">{esc(h)}</th>' for h, r in headers)
    body = "".join(
        "<tr>" + "".join(f'<td class="{"r" if headers[i][1] else ""}">{c}</td>' for i, c in enumerate(row)) + "</tr>"
        for row in rows
    )
    return f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def empty(title: str, text: str) -> None:
    md(f'<div class="empty"><strong>{esc(title)}</strong>{text}</div>')

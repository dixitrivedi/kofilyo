"""A simple password gate. The password lives in secrets:

    [auth]
    password = "your password"

When the app uses Google Sheets (online) a password is required; without one the app refuses to
open. With only the local file (your laptop) and no password set, the app opens without a login.

"Keep me logged in" stores a signed note (a cookie) in the browser for 30 days, so refreshing the
page does not log you out. The note is signed with a key made from the password: changing the
password logs every device out.
"""
from __future__ import annotations

import hashlib
import hmac
import time

import streamlit as st

from theme import BRAND_NAME, T, esc, md

MAX_TRIES = 5
LOCK_SECONDS = 60
COOKIE = "kofilyo_login"
REMEMBER_DAYS = 30


def _password() -> str | None:
    try:
        if "auth" in st.secrets and str(st.secrets["auth"].get("password", "")).strip():
            return str(st.secrets["auth"]["password"])
    except Exception:  # no secrets file
        pass
    return None


# ------------------------------------------------------------ remember me
def _key(password: str) -> bytes:
    return hashlib.sha256(f"kofilyo-login:{password}".encode()).digest()


def make_token(password: str, days: int = REMEMBER_DAYS, now: float | None = None) -> str:
    expires = int((time.time() if now is None else now) + days * 86400)
    sig = hmac.new(_key(password), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def token_ok(password: str, token: str | None, now: float | None = None) -> bool:
    try:
        expires, sig = (token or "").split(".", 1)
        good = hmac.new(_key(password), expires.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, good) and int(expires) > (time.time() if now is None else now)
    except ValueError:
        return False


def _cookie() -> str | None:
    """The login note the browser sent when this page was opened."""
    try:
        return st.context.cookies.get(COOKIE)
    except Exception:
        return None


def _run_js(code: str) -> None:
    st.html(f"<script>{code}</script>", unsafe_allow_javascript=True)


def _set_cookie(token: str) -> None:
    _run_js(f"document.cookie = '{COOKIE}={token}; path=/; max-age={REMEMBER_DAYS * 86400}; SameSite=Lax'"
            " + (location.protocol === 'https:' ? '; Secure' : '');")


def _clear_cookie() -> None:
    _run_js(f"document.cookie = '{COOKIE}=; path=/; max-age=0; SameSite=Lax';")


# ------------------------------------------------------------------- gate
def _logout() -> None:
    st.session_state.pop("authed", None)
    st.session_state["logged_out"] = True      # don't log straight back in from the old note
    st.session_state["clear_cookie"] = True


def _hide_sidebar() -> None:
    md("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], "
       "[data-testid='stExpandSidebarButton'] { display: none !important; }</style>")


def _brand() -> None:
    t = T()
    md(f"""<div style="display:flex;align-items:center;gap:14px;margin:8vh 0 28px">
      <svg width="52" height="52" viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="18" fill="{t['accent']}"></circle>
      <path d="M20 6 C 23 10, 25 12, 28 12" stroke="{t['bg']}" stroke-width="2.5" fill="none" stroke-linecap="round"></path></svg>
      <span class="display" style="font-weight:800;font-size:48px;line-height:1;color:var(--text)">{esc(BRAND_NAME)}</span></div>""")


def needs_login(online: bool) -> bool:
    """True while the login screen (or the 'no password set' lock) must be shown."""
    password = _password()
    if password is None:
        return online
    if st.session_state.get("authed"):
        return False
    if not st.session_state.get("logged_out") and token_ok(password, _cookie()):
        st.session_state["authed"] = True      # remembered on this device
        return False
    return True


def logout_button() -> None:
    if _password() is not None and st.session_state.get("authed"):
        token = st.session_state.pop("set_cookie", None)
        if token:
            with st.sidebar:
                _set_cookie(token)
        st.sidebar.button("Log out", on_click=_logout, icon=":material/logout:", key="logout")


def require_login(online: bool) -> None:
    """Stop the script with a login screen until the right password is entered."""
    password = _password()
    if password is None:
        if online:
            _hide_sidebar()
            _, mid, _ = st.columns([1, 1.4, 1])
            with mid:
                _brand()
                st.error("This app is locked because no password is set. Add an [auth] section with a "
                         "password to the app’s secrets, then reload.", icon=":material/lock:")
            st.stop()
        return

    if st.session_state.get("authed"):
        return

    if st.session_state.pop("clear_cookie", False):
        _clear_cookie()
    _hide_sidebar()
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        _brand()
        locked_until = st.session_state.get("login_locked_until", 0.0)
        if time.time() < locked_until:
            st.error(f"Too many wrong tries. Try again in {int(locked_until - time.time()) + 1} seconds.",
                     icon=":material/timer:")
        with st.container(key="panel-login"):
            md('<p class="page-sub" style="margin:0 0 6px">Enter your password to open the app.</p>')
            with st.form("login", border=False):
                entered = st.text_input("Password", type="password", placeholder="Password")
                remember = st.checkbox("Keep me logged in on this device", value=True,
                                       help=f"Stay logged in for {REMEMBER_DAYS} days, even after refreshing. "
                                            "Untick on a shared computer.")
                submitted = st.form_submit_button("Log in", type="primary", width="stretch")
        if submitted and time.time() >= locked_until:
            if hmac.compare_digest(entered.encode(), password.encode()):
                st.session_state["authed"] = True
                st.session_state.pop("logged_out", None)
                st.session_state.pop("login_tries", None)
                if remember:
                    st.session_state["set_cookie"] = make_token(password)
                st.rerun()
            time.sleep(1)  # slow down guessing
            tries = st.session_state.get("login_tries", 0) + 1
            st.session_state["login_tries"] = tries
            if tries >= MAX_TRIES:
                st.session_state["login_locked_until"] = time.time() + LOCK_SECONDS
                st.session_state["login_tries"] = 0
                st.error(f"Too many wrong tries. Try again in {LOCK_SECONDS} seconds.", icon=":material/timer:")
            else:
                st.error("That password isn’t right.", icon=":material/error:")
    st.stop()

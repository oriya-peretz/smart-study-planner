"""Who is using the app: the landing screen, log in, sign up, log out, and language."""

import streamlit as st

import api
from texts import LANGUAGES, error_message, language, t


def is_logged_in() -> bool:
    return "token" in st.session_state


def backend() -> api.Backend:
    """The API for the user logged in on this browser tab."""
    return api.Backend(st.session_state["token"])


def end_session(message_key: str) -> None:
    """Forget this tab's user and go back to the landing screen, in the same language."""
    kept = language()
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state["lang"] = kept
    st.session_state["notice"] = t(message_key)
    st.rerun()


def log_out() -> None:
    try:
        backend().log_out()
    except api.BackendError:
        pass  # the session ends on this side either way
    end_session("logged_out")


def set_language(code: str) -> None:
    st.session_state["lang"] = code
    # The switch was already drawn in this run, so its value cannot be changed
    # now; removing it makes the next run draw it again from "lang".
    st.session_state.pop("lang-picker", None)


def _language_changed() -> None:
    chosen = st.session_state["lang-picker"]
    if (
        chosen is None
    ):  # clicking the selected option again clears it: keep the language
        st.session_state["lang-picker"] = language()
        return
    st.session_state["lang"] = chosen
    if not is_logged_in():
        st.session_state["lang-chosen"] = True  # saved to the account on logging in
    else:
        try:
            backend().set_language(chosen)
        except api.BackendError:
            pass  # the page still switches; the account keeps its old language


def language_switch(where=st) -> None:
    """English | עברית. While logged in, the choice is saved to the account."""
    st.session_state.setdefault("lang-picker", language())
    where.segmented_control(
        t("language"),
        list(LANGUAGES),
        format_func=LANGUAGES.get,
        key="lang-picker",
        on_change=_language_changed,
        label_visibility="collapsed",
    )


def _form(signing_up: bool) -> None:
    with st.form("auth", border=False):
        email = st.text_input(t("email"), max_chars=254, key="auth-email")
        password = st.text_input(
            t("password"),
            type="password",
            max_chars=128,
            help=t("password_help") if signing_up else None,
            key="auth-password",
        )
        label = t("create_account") if signing_up else t("log_in")
        if st.form_submit_button(
            label, type="primary", key="auth-submit", width="stretch"
        ):
            try:
                if signing_up:
                    api.sign_up(email, password)
                token = api.log_in(email, password)
                user = api.Backend(token)
                # A language picked on this screen, or a new account, keeps the
                # language shown now; otherwise the account's own language returns.
                if signing_up or st.session_state.get("lang-chosen"):
                    user.set_language(language())
                else:
                    set_language(user.me()["language"])
            except api.BackendError as exc:
                st.error(error_message(exc))
            else:
                st.session_state.pop("auth-mode")
                st.session_state["token"] = token
                st.session_state["email"] = email.strip().lower()
                st.rerun()
    if st.button(
        t("back"), key="auth-back", type="tertiary", icon=":material/arrow_back:"
    ):
        st.session_state.pop("auth-mode")
        st.rerun()


def landing() -> None:
    """The first screen from the sketch: the name, then Log in and Sign up."""
    st.html(f'<p class="tagline">{t("tagline")}</p>')
    _, middle, _ = st.columns([1, 1.8, 1])
    with middle:
        mode = st.session_state.get("auth-mode")
        if mode is None:
            if st.button(t("log_in"), key="go-login", type="primary", width="stretch"):
                st.session_state["auth-mode"] = "login"
                st.rerun()
            if st.button(t("sign_up"), key="go-signup", width="stretch"):
                st.session_state["auth-mode"] = "signup"
                st.rerun()
        else:
            _form(signing_up=mode == "signup")

"""Who is using the app: the landing screen, log in, sign up and log out."""

import streamlit as st

import api


def is_logged_in() -> bool:
    return "token" in st.session_state


def backend() -> api.Backend:
    """The API for the user logged in on this browser tab."""
    return api.Backend(st.session_state["token"])


def end_session(message: str) -> None:
    """Forget everything about this tab's user and go back to the landing screen."""
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state["notice"] = message
    st.rerun()


def log_out() -> None:
    try:
        backend().log_out()
    except api.BackendError:
        pass  # the session ends on this side either way
    end_session("You have logged out.")


def _form(signing_up: bool) -> None:
    with st.form("auth", border=False):
        email = st.text_input("Email", max_chars=254, key="auth-email")
        password = st.text_input(
            "Password",
            type="password",
            max_chars=128,
            help="At least 8 characters" if signing_up else None,
            key="auth-password",
        )
        label = "Create account" if signing_up else "Log in"
        if st.form_submit_button(
            label, type="primary", key="auth-submit", width="stretch"
        ):
            try:
                if signing_up:
                    api.sign_up(email, password)
                token = api.log_in(email, password)
            except api.BackendError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("auth-mode")
                st.session_state["token"] = token
                st.session_state["email"] = email.strip().lower()
                st.rerun()
    if st.button(
        "Back", key="auth-back", type="tertiary", icon=":material/arrow_back:"
    ):
        st.session_state.pop("auth-mode")
        st.rerun()


def landing() -> None:
    """The first screen from the sketch: the name, then Log in and Sign up."""
    st.html('<p class="tagline">Every exam, assignment and project, in one place.</p>')
    _, middle, _ = st.columns([1, 1.8, 1])
    with middle:
        mode = st.session_state.get("auth-mode")
        if mode is None:
            if st.button("Log in", key="go-login", type="primary", width="stretch"):
                st.session_state["auth-mode"] = "login"
                st.rerun()
            if st.button("Sign up", key="go-signup", width="stretch"):
                st.session_state["auth-mode"] = "signup"
                st.rerun()
        else:
            _form(signing_up=mode == "signup")

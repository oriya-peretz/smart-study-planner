"""Smart Study Planner: the page Streamlit runs. It loads the data and picks a screen."""

import html
from datetime import date

import streamlit as st

import account
import api
import dialogs
import views

# "wide" lets each screen set its own width below: narrow for logging in,
# wider for the app so three course cards fit side by side.
st.set_page_config(
    page_title="Smart Study Planner",
    page_icon=":material/auto_stories:",
    layout="wide",
)

# The theme (colours, font, round buttons) is in .streamlit/config.toml.
# This adds only what the theme cannot: the wide-spaced title and thin lines.
st.html(
    """
    <style>
      .wordmark { text-align: center; font-weight: 300; font-size: 2.3rem;
                  letter-spacing: .42em; text-transform: uppercase; margin-top: 1rem; }
      .wordmark.hero { font-size: 2.48rem; line-height: 1.5; margin-top: 12vh; }
      .gold-rule { width: 56px; height: 1px; background: #B08D57; margin: .9rem auto 1.6rem; }
      .tagline { text-align: center; font-weight: 300; color: #7A7266; margin-bottom: 2rem; }
      .tagline.notice { color: #B08D57; margin-bottom: .4rem; }
      .user-email { font-size: .85rem; color: #7A7266; margin: 0; }
      [data-testid="stExpander"] details { border-width: 0 0 1px 0; border-radius: 0; }
    </style>
    """
)

if not account.is_logged_in():
    # Drawn only before logging in, so these larger sizes never reach the app itself.
    # In rem, so they follow theme.baseFontSize (20 px).
    st.html(
        """
        <style>
          [data-testid="stMainBlockContainer"] { max-width: 736px; }
          .tagline { font-size: 0.96rem; }
          [data-testid="stWidgetLabel"] p { font-size: 0.88rem; }
          [data-testid="stTextInput"] input { font-size: 0.92rem; min-height: 2.43rem; }
          .stButton button, [data-testid="stFormSubmitButton"] button { min-height: 2.48rem; }
          .stButton button p, [data-testid="stFormSubmitButton"] button p { font-size: 0.88rem; }
        </style>
        <div class="wordmark hero">Smart Study Planner</div><div class="gold-rule"></div>
        """
    )
    if notice := st.session_state.pop("notice", None):
        st.html(f'<p class="tagline notice">{html.escape(notice)}</p>')
    account.landing()
    st.stop()

user_col, logout_col = st.columns([4, 1], vertical_alignment="center")
with user_col:  # html, because Markdown would turn the address into a mailto link
    st.html(f'<p class="user-email">{html.escape(st.session_state["email"])}</p>')
if logout_col.button(
    "Log out", key="log-out", type="tertiary", icon=":material/logout:"
):
    account.log_out()

st.html(
    """
    <style>
      [data-testid="stMainBlockContainer"] { max-width: 1180px; }
    </style>
    <div class="wordmark">Smart Study Planner</div><div class="gold-rule"></div>
    """
)

VIEWS = ["By course", "By urgency"]

if notice := st.session_state.pop("notice", None):
    st.success(notice)

view_col, toggle_col, add_col = st.columns([2.2, 1.6, 1.2], vertical_alignment="center")
view = view_col.segmented_control(
    "View", VIEWS, default="By urgency", key="view", label_visibility="collapsed"
)
view = view or "By urgency"  # clicking the selected option again clears it
include_done = toggle_col.toggle("Show finished", value=True, key="include-done")

backend = account.backend()
try:
    with st.spinner("Loading..."):
        courses = backend.list_courses()
        if view == "By course":
            groups = backend.list_tasks_by_course(include_done)
        else:
            tasks = backend.list_tasks(include_done)
except api.NotLoggedIn:
    account.end_session("Your session has ended. Please log in again.")
except api.BackendError as exc:
    st.error(str(exc))
    st.stop()  # nothing else on this page works without the backend

today = date.today()
if add_col.button(
    "Add task", key="add-task", type="primary", icon=":material/add:", width="stretch"
):
    dialogs.open_dialog("add-task")

if view == "By urgency":
    views.urgency_view(tasks, courses, today)
else:
    views.course_grid(groups, courses, today)

loaded = tasks if view == "By urgency" else [t for g in groups for t in g["tasks"]]
dialogs.show_open(courses, loaded)

"""Smart Study Planner: the page Streamlit runs. It loads the data and picks a screen."""

import html
from datetime import date

import streamlit as st

import account
import api
import dialogs
import views
from texts import error_message, is_rtl, t

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
      /* Streamlit's "Press Enter to submit form" and "16/254" hints inside text fields:
         noise for a user. max_chars still limits the length. */
      [data-testid="InputInstructions"] { display: none; }
    </style>
    """
)

if is_rtl():
    # Hebrew reads right to left: the page and every dialog. The brand name stays
    # in English, and e-mail addresses and links stay left to right.
    st.html(
        """
        <style>
          [data-testid="stMain"], [role="dialog"] { direction: rtl; }
          .wordmark, .user-email, input[type="email"], code { direction: ltr; }
          .user-email { text-align: right; }
          /* Markdown sets each block's direction from its first letter, so an English
             course name would sit on the left of a Hebrew card. */
          [data-testid="stMarkdownContainer"] { text-align: right; }
          /* Dates and times keep their digit order (27/10/2026, 09:00). */
          [data-testid="stDateInputField"], [data-testid="stTimeInputTimeDisplay"] {
            direction: ltr;
          }
          /* Streamlit's built-in "(required)" marker, in Hebrew. */
          [data-testid="stWidgetLabelRequired"] { font-size: 0; }
          [data-testid="stWidgetLabelRequired"]::after { content: "(חובה)"; font-size: .8rem; }
          /* The two switches lay out left to right, so their rounded ends stay on the
             outside; the views are listed in reverse below, so "By course" stays first
             when read from the right. */
          .st-key-lang-picker, .st-key-view { direction: ltr; }
          /* A toggle's knob slides to the right when on; right to left it would
             slide out of its track, leaving only a gold bar. The label stays Hebrew. */
          [data-testid="stCheckbox"] label > div:not([data-testid="stWidgetLabel"]) {
            direction: ltr;
          }
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
        """
    )
    _, switch_col = st.columns([2, 1.3])
    account.language_switch(switch_col)
    st.html(
        '<div class="wordmark hero">Smart Study Planner</div><div class="gold-rule"></div>'
    )
    if notice := st.session_state.pop("notice", None):
        st.html(f'<p class="tagline notice">{html.escape(notice)}</p>')
    account.landing()
    st.stop()

user_col, switch_col, logout_col = st.columns([3, 1.4, 1], vertical_alignment="center")
with user_col:  # html, because Markdown would turn the address into a mailto link
    st.html(f'<p class="user-email">{html.escape(st.session_state["email"])}</p>')
account.language_switch(switch_col)
if logout_col.button(
    t("log_out"), key="log-out", type="tertiary", icon=":material/logout:"
):
    account.log_out()

st.html(
    """
    <style>
      [data-testid="stMainBlockContainer"] { max-width: 1320px; }
      /* The "+" card for a new course: one large, thin gold plus that fills it. */
      .st-key-new-course button { min-height: 11rem; }
      .st-key-new-course button p { font-size: 6rem; font-weight: 200; line-height: 1;
                                    color: #B08D57; }
      .st-key-new-course button:hover p { color: #8A6D3B; }
    </style>
    <div class="wordmark">Smart Study Planner</div><div class="gold-rule"></div>
    """
)

VIEWS = {"course": "view_course", "urgency": "view_urgency"}

if notice := st.session_state.pop("notice", None):
    st.success(notice)

view_col, toggle_col, add_col = st.columns([2.2, 1.6, 1.2], vertical_alignment="center")
view = view_col.segmented_control(
    t("view"),
    list(reversed(VIEWS)) if is_rtl() else list(VIEWS),
    default="urgency",
    format_func=lambda code: t(VIEWS[code]),
    key="view",
    label_visibility="collapsed",
)
view = view or "urgency"  # clicking the selected option again clears it
include_done = toggle_col.toggle(t("show_finished"), value=True, key="include-done")

backend = account.backend()
try:
    with st.spinner(t("loading")):
        courses = backend.list_courses()
        if view == "course":
            groups = backend.list_tasks_by_course(include_done)
        else:
            tasks = backend.list_tasks(include_done)
except api.NotLoggedIn:
    account.end_session("session_ended")
except api.BackendError as exc:
    st.error(error_message(exc))
    st.stop()  # nothing else on this page works without the backend

today = date.today()
if add_col.button(
    t("add_task"),
    key="add-task",
    type="primary",
    icon=":material/add:",
    width="stretch",
):
    dialogs.open_dialog("add-task")

if view == "urgency":
    views.urgency_view(tasks, courses, today)
else:
    views.course_grid(groups, courses, today)

loaded = tasks if view == "urgency" else [task for g in groups for task in g["tasks"]]
dialogs.show_open(courses, loaded)

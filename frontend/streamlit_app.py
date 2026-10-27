"""Smart Study Planner: the page Streamlit runs. It loads the data and picks a screen."""

from datetime import date

import streamlit as st

import api
import dialogs
import views

st.set_page_config(
    page_title="Smart Study Planner", page_icon=":material/auto_stories:"
)

# The theme (colours, font, round buttons) is in .streamlit/config.toml.
# This adds only what the theme cannot: the wide-spaced title and thin lines.
st.html(
    """
    <style>
      .wordmark { text-align: center; font-weight: 300; font-size: 1.6rem;
                  letter-spacing: .42em; text-transform: uppercase; margin-top: 1rem; }
      .gold-rule { width: 56px; height: 1px; background: #B08D57; margin: .9rem auto 1.6rem; }
      [data-testid="stExpander"] details { border-width: 0 0 1px 0; border-radius: 0; }
    </style>
    <div class="wordmark">Smart Study Planner</div>
    <div class="gold-rule"></div>
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

try:
    with st.spinner("Loading..."):
        courses = api.list_courses()
        if view == "By course":
            groups = api.list_tasks_by_course(include_done)
        else:
            tasks = api.list_tasks(include_done)
except api.BackendError as exc:
    st.error(str(exc))
    st.stop()  # nothing else on this page works without the backend

today = date.today()
open_course = st.session_state.get("course") if view == "By course" else None

if open_course is None and add_col.button(
    "Add task", key="add-task", type="primary", icon=":material/add:", width="stretch"
):
    dialogs.add_task(courses)

if view == "By urgency":
    views.urgency_view(tasks, courses, today)
elif group := next((g for g in groups if g["course"]["id"] == open_course), None):
    views.course_page(group, courses, today)
else:
    views.course_grid(groups, today)

"""The screens: a numbered list by urgency, a grid of courses, and one course's page."""

from datetime import date

import streamlit as st

import account
import api
import dialogs
from labels import (
    FINISHED,
    STATUSES,
    TYPE_ICONS,
    TYPES,
    countdown,
    is_link,
    plain,
    when,
)

CARDS_PER_ROW = 3


def task_row(
    task: api.Task,
    number: int,
    courses: list[api.Course],
    today: date,
    show_course: bool = True,
) -> None:
    """One numbered line; expanding it shows the details and the actions."""
    tid = task["id"]
    title = plain(task["title"])
    if task["status"] == "done":
        title = f"~~{title}~~"
    parts = [f":primary[{number:02d}]", f"**{title}**"]
    if show_course:
        parts.append(plain(task["course"]["name"]))
    parts += [TYPES[task["type"]], countdown(task, today)]
    with st.expander("  ·  ".join(parts), icon=TYPE_ICONS[task["type"]]):
        details = [when(task)]
        if task["type"] != "exam":
            details.append(STATUSES[task["status"]])
        if task["estimated_hours"]:
            details.append(f"{task['estimated_hours']:g} h")
        if task["location"]:
            details.append(plain(task["location"]))
        st.caption("  ·  ".join(details))
        if task["link"]:
            if is_link(task["link"]):
                st.link_button("Open link", task["link"], icon=":material/open_in_new:")
            else:
                st.caption(
                    "Local file or folder (copy the path, then paste it in File Explorer):"
                )
                st.code(task["link"], language=None)
        if task["notes"]:
            st.markdown(plain(task["notes"]))

        done_col, edit_col = st.columns(2)
        can_finish = task["type"] != "exam" and task["status"] != "done"
        if can_finish and done_col.button(
            "Mark as done", key=f"done-{tid}", icon=":material/check:", width="stretch"
        ):
            try:
                account.backend().update_task(tid, {"status": "done"})
            except api.BackendError as exc:
                st.error(str(exc))
            else:
                dialogs.notify(f"Marked {plain(task['title'])} as done.")
        if edit_col.button(
            "Edit", key=f"edit-{tid}", icon=":material/edit:", width="stretch"
        ):
            dialogs.open_dialog("edit-task", task_id=tid)


def numbered_list(
    tasks: list[api.Task],
    courses: list[api.Course],
    today: date,
    show_course: bool = True,
) -> None:
    for number, task in enumerate(tasks, 1):
        task_row(task, number, courses, today, show_course)


def urgency_view(tasks: list[api.Task], courses: list[api.Course], today: date) -> None:
    if not courses:
        st.info(
            "Welcome! Start by adding a course: choose **By course**, then the **+** card."
        )
    elif not tasks:
        st.info("No tasks here. Use **Add task** to add one.")
    numbered_list(tasks, courses, today)


def course_card(group: api.CourseTasks, today: date) -> None:
    course = group["course"]
    open_tasks = [task for task in group["tasks"] if task["status"] not in FINISHED]
    st.markdown(f"#### {plain(course['name'])}")
    count = len(open_tasks)
    st.caption(f"{count} open task{'s' if count != 1 else ''}")
    if open_tasks:
        upcoming = open_tasks[0]
        st.markdown(f"Next: {plain(upcoming['title'])}  \n{countdown(upcoming, today)}")
    else:
        st.markdown(":gray[Nothing due]  \n&nbsp;")
    if st.button(
        "Open",
        key=f"open-course-{course['id']}",
        type="tertiary",
        icon=":material/arrow_forward:",
    ):
        st.session_state["course"] = course["id"]
        st.rerun()


def course_grid(groups: list[api.CourseTasks], today: date) -> None:
    cards: list[api.CourseTasks | None] = [*groups, None]  # None is the "+" card
    for start in range(0, len(cards), CARDS_PER_ROW):
        columns = st.columns(CARDS_PER_ROW)
        for column, group in zip(columns, cards[start : start + CARDS_PER_ROW]):
            with column, st.container(border=True, height="stretch"):
                if group is None:
                    st.space("small")
                    if st.button(
                        "New course",
                        key="new-course",
                        type="tertiary",
                        icon=":material/add:",
                        width="stretch",
                    ):
                        dialogs.open_dialog("add-course")
                else:
                    course_card(group, today)


def course_page(group: api.CourseTasks, courses: list[api.Course], today: date) -> None:
    course = group["course"]
    if st.button(
        "All courses", key="back", type="tertiary", icon=":material/arrow_back:"
    ):
        st.session_state.pop("course")
        st.rerun()
    title_col, settings_col, add_col = st.columns(
        [3, 1, 1], vertical_alignment="center"
    )
    title_col.header(plain(course["name"]))
    if settings_col.button(
        "Settings", key="course-settings", icon=":material/tune:", width="stretch"
    ):
        dialogs.open_dialog("edit-course", course_id=course["id"])
    if add_col.button(
        "Add task",
        key="course-add-task",
        type="primary",
        icon=":material/add:",
        width="stretch",
    ):
        dialogs.open_dialog("add-task", course_id=course["id"])
    if not group["tasks"]:
        st.info("No tasks in this course yet.")
    numbered_list(group["tasks"], courses, today, show_course=False)

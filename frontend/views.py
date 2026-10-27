"""The screens: a numbered list by urgency, and a grid of courses with their tasks."""

from datetime import date

import streamlit as st

import account
import api
import dialogs
from labels import (
    FINISHED,
    TYPE_ICONS,
    countdown,
    is_link,
    plain,
    status_name,
    type_name,
    when,
)
from texts import error_message, separator, t

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
    parts += [type_name(task["type"]), countdown(task, today)]
    with st.expander(separator().join(parts), icon=TYPE_ICONS[task["type"]]):
        details = [when(task)]
        if task["type"] != "exam":
            details.append(status_name(task["status"]))
        if task["estimated_hours"]:
            details.append(t("hours", h=f"{task['estimated_hours']:g}"))
        if task["location"]:
            details.append(plain(task["location"]))
        st.caption(separator().join(details))
        if task["link"]:
            if is_link(task["link"]):
                st.link_button(
                    t("open_link"), task["link"], icon=":material/open_in_new:"
                )
            else:
                st.caption(t("local_path"))
                st.code(task["link"], language=None)
        if task["notes"]:
            st.markdown(plain(task["notes"]))

        # In a narrow course card (no course name shown) the buttons go one under
        # the other, so neither label is cut short.
        done_col, edit_col = (
            st.columns(2) if show_course else (st.container(), st.container())
        )
        can_finish = task["type"] != "exam" and task["status"] != "done"
        if can_finish and done_col.button(
            t("mark_done"), key=f"done-{tid}", icon=":material/check:", width="stretch"
        ):
            try:
                account.backend().update_task(tid, {"status": "done"})
            except api.BackendError as exc:
                st.error(error_message(exc))
            else:
                dialogs.notify(t("marked_done", title=plain(task["title"])))
        if edit_col.button(
            t("edit"), key=f"edit-{tid}", icon=":material/edit:", width="stretch"
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
        st.info(t("welcome"))
    elif not tasks:
        st.info(t("no_tasks"))
    numbered_list(tasks, courses, today)


def course_card(group: api.CourseTasks, courses: list[api.Course], today: date) -> None:
    """One course with all of its tasks, so nothing needs a separate page."""
    course = group["course"]
    cid = course["id"]
    open_count = sum(task["status"] not in FINISHED for task in group["tasks"])
    st.markdown(f"#### {plain(course['name'])}")
    st.caption(
        t("open_tasks_one") if open_count == 1 else t("open_tasks_many", n=open_count)
    )
    add_col, settings_col = st.columns(2)
    if add_col.button(
        t("add_task"), key=f"course-add-{cid}", type="tertiary", icon=":material/add:"
    ):
        dialogs.open_dialog("add-task", course_id=cid)
    if settings_col.button(
        t("settings"),
        key=f"course-settings-{cid}",
        type="tertiary",
        icon=":material/tune:",
    ):
        dialogs.open_dialog("edit-course", course_id=cid)
    if group["tasks"]:
        numbered_list(group["tasks"], courses, today, show_course=False)
    else:
        st.caption(f":gray[{t('no_tasks_yet')}]")


def course_grid(
    groups: list[api.CourseTasks], courses: list[api.Course], today: date
) -> None:
    cards: list[api.CourseTasks | None] = [*groups, None]  # None is the "+" card
    for start in range(0, len(cards), CARDS_PER_ROW):
        columns = st.columns(CARDS_PER_ROW)
        for column, group in zip(columns, cards[start : start + CARDS_PER_ROW]):
            with column, st.container(border=True, height="stretch"):
                if group is None:
                    # A large gold "+" fills the card (styled in streamlit_app.py);
                    # hovering shows what it does.
                    if st.button(
                        "+",
                        key="new-course",
                        type="tertiary",
                        help=t("add_new_course"),
                        width="stretch",
                    ):
                        dialogs.open_dialog("add-course")
                else:
                    course_card(group, courses, today)

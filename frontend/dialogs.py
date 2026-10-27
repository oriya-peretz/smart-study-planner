"""Pop-up windows: add or edit a task, and add, rename or delete a course."""

from datetime import date, datetime, time

import streamlit as st

import account
import api
from labels import STATUSES, TYPES, plain, status_name, type_name
from texts import error_message, t

# Which dialog is open lives in session state, and show_open() draws it on
# every run until it is saved or dismissed. A dialog drawn only in the run of
# the click that opened it would close again on the next full rerun.


def open_dialog(name: str, **details) -> None:
    st.session_state["dialog"] = {"name": name, **details}


def close_dialog() -> None:
    st.session_state.pop("dialog", None)


def notify(message: str) -> None:
    """Remember a success message, close any dialog, and rerun so lists show fresh data."""
    close_dialog()
    st.session_state["notice"] = message
    st.rerun()


def or_none(text: str) -> str | None:
    """Empty optional text means "not set", which the API expects as null."""
    return text.strip() or None


def task_fields(
    key: str,
    task_type: str,
    courses: list[api.Course],
    task: api.Task | None = None,
    course_id: int | None = None,
) -> dict:
    """Draw the inputs for one task type (inside a form) and return a request body."""
    current: dict = dict(task) if task else {}
    is_exam = task_type == "exam"
    due = datetime.fromisoformat(current["due_at"]) if current else None
    names = {course["id"]: course["name"] for course in courses}
    chosen = current.get("course_id", course_id)

    body = {
        "title": st.text_input(
            t("title"),
            current.get("title", ""),
            max_chars=200,
            required=True,
            key=f"{key}-title",
        ),
        "course_id": st.selectbox(
            t("course"),
            list(names),
            index=list(names).index(chosen) if chosen in names else None,
            format_func=names.get,
            placeholder=t("choose_course"),
            key=f"{key}-course",
        ),
    }
    day_col, time_col = st.columns(2)
    due_date = day_col.date_input(
        t("exam_date") if is_exam else t("due_date"),
        due.date() if due else date.today(),
        format="DD/MM/YYYY",
        key=f"{key}-date",
    )
    due_time = time_col.time_input(
        t("time"),
        due.time() if due else (time(9, 0) if is_exam else time(23, 59)),
        step=60,
        key=f"{key}-{task_type}-time",  # per type: exams default to 09:00, others to 23:59
    )
    body["due_at"] = datetime.combine(due_date, due_time).isoformat()
    body["estimated_hours"] = st.number_input(
        t("study_hours") if is_exam else t("work_hours"),
        min_value=0.5,
        max_value=1000.0,
        value=current.get("estimated_hours"),
        step=0.5,
        key=f"{key}-hours",
    )
    if is_exam:
        body["location"] = or_none(
            st.text_input(
                t("location"),
                current.get("location") or "",
                max_chars=200,
                key=f"{key}-location",
            )
        )
    else:
        status = current.get("status") or "todo"
        body["status"] = st.selectbox(
            t("status"),
            STATUSES,
            index=STATUSES.index(status),
            format_func=status_name,
            key=f"{key}-status",
        )
        body["link"] = or_none(
            st.text_input(
                t("link"),
                current.get("link") or "",
                max_chars=2000,
                placeholder=t("link_placeholder"),
                key=f"{key}-link",
            )
        )
    body["notes"] = or_none(
        st.text_area(
            t("notes"),
            current.get("notes") or "",
            max_chars=2000,
            key=f"{key}-notes",
        )
    )
    return body


def missing_fields(body: dict) -> str | None:
    """Frontend check before any request: catch the common mistakes early."""
    if not body["title"].strip():
        return t("need_title")
    if body["course_id"] is None:
        return t("need_course")
    return None


# The dialog bodies below are wrapped in st.dialog when they open (show_open),
# because a dialog's title is fixed when it is wrapped, and the title must be
# in the user's current language.


def add_task(courses: list[api.Course], course_id: int | None = None) -> None:
    if not courses:
        st.info(t("need_course_first"))
        return
    # Outside the form, so choosing a type redraws the form with that type's fields.
    task_type = st.selectbox(t("type"), TYPES, format_func=type_name, key="add-type")
    with st.form("add-task", border=False):
        body = {
            "type": task_type,
            **task_fields("add", task_type, courses, course_id=course_id),
        }
        if st.form_submit_button(
            t("add_task"), type="primary", key="add-submit", width="stretch"
        ):
            if problem := missing_fields(body):
                st.warning(problem)
                return
            try:
                created = account.backend().create_task(body)
            except api.BackendError as exc:
                st.error(error_message(exc))
            else:
                notify(t("added", title=plain(created["title"])))


def edit_task(task: api.Task, courses: list[api.Course]) -> None:
    tid = task["id"]
    st.caption(type_name(task["type"]))
    with st.form(f"edit-{tid}", border=False):
        changes = task_fields(f"edit-{tid}", task["type"], courses, task)
        if st.form_submit_button(
            t("save_changes"), type="primary", key=f"save-{tid}", width="stretch"
        ):
            if problem := missing_fields(changes):
                st.warning(problem)
                return
            try:
                account.backend().update_task(tid, changes)
            except api.BackendError as exc:
                st.error(error_message(exc))
            else:
                notify(t("saved", title=plain(changes["title"])))

    # Deleting cannot be undone, so it takes a second click to confirm.
    if not st.session_state.get(f"confirm-delete-{tid}"):
        if st.button(
            t("delete_task"),
            key=f"delete-{tid}",
            type="tertiary",
            icon=":material/delete:",
        ):
            st.session_state[f"confirm-delete-{tid}"] = True
            st.rerun(scope="fragment")
        return
    st.warning(t("confirm_delete"))
    yes, no = st.columns(2)
    if yes.button(t("yes_delete"), key=f"delete-yes-{tid}", width="stretch"):
        st.session_state.pop(f"confirm-delete-{tid}")
        try:
            account.backend().delete_task(tid)
        except api.BackendError as exc:
            st.error(error_message(exc))
        else:
            notify(t("deleted", title=plain(task["title"])))
    if no.button(t("cancel"), key=f"delete-no-{tid}", width="stretch"):
        st.session_state.pop(f"confirm-delete-{tid}")
        st.rerun(scope="fragment")


def add_course() -> None:
    with st.form("add-course", border=False):
        name = st.text_input(
            t("course_name"), max_chars=100, required=True, key="course-name"
        )
        if st.form_submit_button(
            t("add_course"), type="primary", key="course-submit", width="stretch"
        ):
            if not name.strip():
                st.warning(t("need_course_name"))
                return
            try:
                created = account.backend().create_course(name)
            except api.BackendError as exc:
                st.error(error_message(exc))
            else:
                notify(t("course_added", name=plain(created["name"])))


def edit_course(course: api.Course, has_tasks: bool) -> None:
    cid = course["id"]
    with st.form(f"rename-{cid}", border=False):
        name = st.text_input(
            t("course_name"), course["name"], max_chars=100, key=f"rename-{cid}-name"
        )
        if st.form_submit_button(
            t("rename"), type="primary", key=f"rename-{cid}-submit", width="stretch"
        ):
            try:
                account.backend().rename_course(cid, name)
            except api.BackendError as exc:
                st.error(error_message(exc))
            else:
                notify(t("renamed", name=plain(name)))
    if has_tasks:
        st.caption(t("delete_tasks_first"))
    elif st.button(
        t("delete_course"),
        key=f"delete-course-{cid}",
        type="tertiary",
        icon=":material/delete:",
    ):
        try:
            account.backend().delete_course(cid)
        except api.BackendError as exc:
            st.error(error_message(exc))
        else:
            notify(t("course_deleted", name=plain(course["name"])))


def _dialog(title_key: str, body, *args, width: str = "small") -> None:
    """Open `body` as a dialog titled in the current language."""
    st.dialog(t(title_key), width=width, on_dismiss=close_dialog)(body)(*args)


def show_open(courses: list[api.Course], tasks: list[api.Task]) -> None:
    """Draw the open dialog, if any. The page calls this once, at the end of every run."""
    dialog = st.session_state.get("dialog")
    if dialog is None:
        return
    match dialog["name"]:
        case "add-task":
            _dialog(
                "dlg_add_task",
                add_task,
                courses,
                dialog.get("course_id"),
                width="medium",
            )
        case "add-course":
            _dialog("dlg_new_course", add_course)
        case "edit-task":
            task = next(
                (item for item in tasks if item["id"] == dialog["task_id"]), None
            )
            if task is None:  # e.g. hidden by "Show finished"
                close_dialog()
            else:
                _dialog("dlg_edit_task", edit_task, task, courses, width="medium")
        case "edit-course":
            course = next((c for c in courses if c["id"] == dialog["course_id"]), None)
            if course is None:
                close_dialog()
            else:
                has_tasks = any(item["course_id"] == course["id"] for item in tasks)
                _dialog("dlg_edit_course", edit_course, course, has_tasks)

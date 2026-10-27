"""Pop-up windows: add or edit a task, and add, rename or delete a course."""

from datetime import date, datetime, time

import streamlit as st

import account
import api
from labels import STATUSES, TYPES, plain

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
    t: dict = dict(task) if task else {}
    is_exam = task_type == "exam"
    due = datetime.fromisoformat(t["due_at"]) if t else None
    names = {course["id"]: course["name"] for course in courses}
    chosen = t.get("course_id", course_id)

    body = {
        "title": st.text_input(
            "Title",
            t.get("title", ""),
            max_chars=200,
            required=True,
            key=f"{key}-title",
        ),
        "course_id": st.selectbox(
            "Course",
            list(names),
            index=list(names).index(chosen) if chosen in names else None,
            format_func=names.get,
            placeholder="Choose a course",
            key=f"{key}-course",
        ),
    }
    day_col, time_col = st.columns(2)
    due_date = day_col.date_input(
        "Exam date" if is_exam else "Due date",
        due.date() if due else date.today(),
        format="DD/MM/YYYY",
        key=f"{key}-date",
    )
    due_time = time_col.time_input(
        "Time",
        due.time() if due else (time(9, 0) if is_exam else time(23, 59)),
        step=60,
        key=f"{key}-{task_type}-time",  # per type: exams default to 09:00, others to 23:59
    )
    body["due_at"] = datetime.combine(due_date, due_time).isoformat()
    body["estimated_hours"] = st.number_input(
        "Study hours (optional)" if is_exam else "Estimated hours of work (optional)",
        min_value=0.5,
        max_value=1000.0,
        value=t.get("estimated_hours"),
        step=0.5,
        key=f"{key}-hours",
    )
    if is_exam:
        body["location"] = or_none(
            st.text_input(
                "Location (optional)",
                t.get("location") or "",
                max_chars=200,
                key=f"{key}-location",
            )
        )
    else:
        status = t.get("status") or "todo"
        body["status"] = st.selectbox(
            "Status",
            list(STATUSES),
            index=list(STATUSES).index(status),
            format_func=STATUSES.get,
            key=f"{key}-status",
        )
        body["link"] = or_none(
            st.text_input(
                "Link (optional)",
                t.get("link") or "",
                max_chars=2000,
                placeholder="https://... or C:\\path\\to\\file.docx",
                key=f"{key}-link",
            )
        )
    body["notes"] = or_none(
        st.text_area(
            "Notes (optional)", t.get("notes") or "", max_chars=2000, key=f"{key}-notes"
        )
    )
    return body


def missing_fields(body: dict) -> str | None:
    """Frontend check before any request: catch the common mistakes early."""
    if not body["title"].strip():
        return "Give the task a title before saving."
    if body["course_id"] is None:
        return "Choose a course before saving."
    return None


@st.dialog("Add a task", width="medium", on_dismiss=close_dialog)
def add_task(courses: list[api.Course], course_id: int | None = None) -> None:
    if not courses:
        st.info("Add a course first: choose **By course**, then the **+** card.")
        return
    # Outside the form, so choosing a type redraws the form with that type's fields.
    task_type = st.selectbox("Type", list(TYPES), format_func=TYPES.get, key="add-type")
    with st.form("add-task", border=False):
        body = {
            "type": task_type,
            **task_fields("add", task_type, courses, course_id=course_id),
        }
        if st.form_submit_button(
            "Add task", type="primary", key="add-submit", width="stretch"
        ):
            if problem := missing_fields(body):
                st.warning(problem)
                return
            try:
                created = account.backend().create_task(body)
            except api.BackendError as exc:
                st.error(str(exc))
            else:
                notify(f"Added {plain(created['title'])}.")


@st.dialog("Edit task", width="medium", on_dismiss=close_dialog)
def edit_task(task: api.Task, courses: list[api.Course]) -> None:
    tid = task["id"]
    st.caption(TYPES[task["type"]])
    with st.form(f"edit-{tid}", border=False):
        changes = task_fields(f"edit-{tid}", task["type"], courses, task)
        if st.form_submit_button(
            "Save changes", type="primary", key=f"save-{tid}", width="stretch"
        ):
            if problem := missing_fields(changes):
                st.warning(problem)
                return
            try:
                account.backend().update_task(tid, changes)
            except api.BackendError as exc:
                st.error(str(exc))
            else:
                notify(f"Saved {plain(changes['title'])}.")

    # Deleting cannot be undone, so it takes a second click to confirm.
    if not st.session_state.get(f"confirm-delete-{tid}"):
        if st.button(
            "Delete task",
            key=f"delete-{tid}",
            type="tertiary",
            icon=":material/delete:",
        ):
            st.session_state[f"confirm-delete-{tid}"] = True
            st.rerun(scope="fragment")
        return
    st.warning("Delete this task for good?")
    yes, no = st.columns(2)
    if yes.button("Yes, delete", key=f"delete-yes-{tid}", width="stretch"):
        st.session_state.pop(f"confirm-delete-{tid}")
        try:
            account.backend().delete_task(tid)
        except api.BackendError as exc:
            st.error(str(exc))
        else:
            notify(f"Deleted {plain(task['title'])}.")
    if no.button("Cancel", key=f"delete-no-{tid}", width="stretch"):
        st.session_state.pop(f"confirm-delete-{tid}")
        st.rerun(scope="fragment")


@st.dialog("New course", on_dismiss=close_dialog)
def add_course() -> None:
    with st.form("add-course", border=False):
        name = st.text_input(
            "Course name", max_chars=100, required=True, key="course-name"
        )
        if st.form_submit_button(
            "Add course", type="primary", key="course-submit", width="stretch"
        ):
            if not name.strip():
                st.warning("Give the course a name.")
                return
            try:
                created = account.backend().create_course(name)
            except api.BackendError as exc:
                st.error(str(exc))
            else:
                notify(f"Added the course {plain(created['name'])}.")


@st.dialog("Course settings", on_dismiss=close_dialog)
def edit_course(course: api.Course, has_tasks: bool) -> None:
    cid = course["id"]
    with st.form(f"rename-{cid}", border=False):
        name = st.text_input(
            "Course name", course["name"], max_chars=100, key=f"rename-{cid}-name"
        )
        if st.form_submit_button(
            "Rename", type="primary", key=f"rename-{cid}-submit", width="stretch"
        ):
            try:
                account.backend().rename_course(cid, name)
            except api.BackendError as exc:
                st.error(str(exc))
            else:
                notify(f"Renamed to {plain(name)}.")
    if has_tasks:
        st.caption("To delete this course, delete its tasks first.")
    elif st.button(
        "Delete course",
        key=f"delete-course-{cid}",
        type="tertiary",
        icon=":material/delete:",
    ):
        try:
            account.backend().delete_course(cid)
        except api.BackendError as exc:
            st.error(str(exc))
        else:
            notify(f"Deleted the course {plain(course['name'])}.")


def show_open(courses: list[api.Course], tasks: list[api.Task]) -> None:
    """Draw the open dialog, if any. The page calls this once, at the end of every run."""
    dialog = st.session_state.get("dialog")
    if dialog is None:
        return
    match dialog["name"]:
        case "add-task":
            add_task(courses, dialog.get("course_id"))
        case "add-course":
            add_course()
        case "edit-task":
            task = next((t for t in tasks if t["id"] == dialog["task_id"]), None)
            if task is None:  # e.g. hidden by "Show finished"
                close_dialog()
            else:
                edit_task(task, courses)
        case "edit-course":
            course = next((c for c in courses if c["id"] == dialog["course_id"]), None)
            if course is None:
                close_dialog()
            else:
                has_tasks = any(t["course_id"] == course["id"] for t in tasks)
                edit_course(course, has_tasks)

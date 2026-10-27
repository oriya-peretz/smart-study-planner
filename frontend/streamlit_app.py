import string
from datetime import date, datetime, time

import streamlit as st

import api

st.set_page_config(page_title="Smart Study Planner", page_icon=":material/school:")
st.title("Smart Study Planner")

TYPES = {
    "exam": "Exam",
    "submission": "Submission",
    "online_quiz": "Online quiz",
    "homework": "Homework",
    "project": "Project",
}
TYPE_ICONS = {
    "exam": ":material/school:",
    "submission": ":material/upload_file:",
    "online_quiz": ":material/computer:",
    "homework": ":material/edit_note:",
    "project": ":material/folder:",
}
STATUSES = {"todo": "To do", "in_progress": "In progress", "done": "Done"}
VIEWS = ["By urgency", "By course"]

# Every ASCII punctuation mark, prefixed with a backslash.
MARKDOWN_ESCAPES = str.maketrans({c: "\\" + c for c in string.punctuation})


def plain(text: str) -> str:
    """Escape Markdown so user text is shown, not interpreted."""
    return text.translate(MARKDOWN_ESCAPES)


def notify(message: str) -> None:
    """Remember a success message, then rerun so lists show fresh data."""
    st.session_state["notice"] = message
    st.rerun()


def or_none(text: str) -> str | None:
    """Empty optional text means "not set", which the API expects as null."""
    return text.strip() or None


def due_label(task: api.Task, today: date) -> str:
    """When the task is due, in words, coloured by urgency."""
    due = datetime.fromisoformat(task["due_at"])
    when = f"{due:%a %d %b %Y, %H:%M}"
    if task["status"] == "done":
        return f"{when} · :green[done]"
    days = (due.date() - today).days
    if days < 0:
        return f"{when} · :red[overdue by {-days} day{'s' if days < -1 else ''}]"
    if days == 0:
        return f"{when} · :orange[today]"
    if days == 1:
        return f"{when} · :orange[tomorrow]"
    return f"{when} · in {days} days"


def is_link(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def task_fields(
    key: str, task_type: str, courses: list[str], task: api.Task | None = None
) -> dict:
    """Draw the inputs for one task type (inside a form) and return a request body."""
    t: dict = dict(task) if task else {}
    is_exam = task_type == "exam"
    due = datetime.fromisoformat(t["due_at"]) if t else None
    course = t.get("course")
    course_options = sorted(set(courses) | ({course} if course else set()))

    body = {
        "title": st.text_input(
            "Title",
            t.get("title", ""),
            max_chars=200,
            required=True,
            key=f"{key}-title",
        ),
        "course": st.selectbox(
            "Course",
            course_options,
            index=course_options.index(course) if course else None,
            placeholder="Choose a course or type a new one",
            accept_new_options=True,
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
        key=f"{key}-time",
    )
    body["due_at"] = datetime.combine(due_date, due_time).isoformat()
    body["estimated_hours"] = st.number_input(
        "Estimated hours of work (optional)"
        if not is_exam
        else "Study hours (optional)",
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
    if not body["course"]:
        return "Choose or type a course before saving."
    return None


def show_task(
    task: api.Task, courses: list[str], today: date, show_course: bool = True
) -> None:
    tid = task["id"]
    title = plain(task["title"])
    shown = f"~~{title}~~" if task["status"] == "done" else title
    parts = [f"**{shown}**", TYPES[task["type"]], due_label(task, today)]
    if show_course:  # in the by-course view the course is already the heading
        parts.insert(1, plain(task["course"]))
    label = " · ".join(parts)
    with st.expander(label, icon=TYPE_ICONS[task["type"]]):
        details = []
        if task["type"] != "exam":
            details.append(f"**Status:** {STATUSES[task['status']]}")
        if task["estimated_hours"]:
            details.append(f"**Estimated hours:** {task['estimated_hours']:g}")
        if task["location"]:
            details.append(f"**Location:** {plain(task['location'])}")
        if details:
            st.markdown(" · ".join(details))
        if task["link"]:
            if is_link(task["link"]):
                st.link_button("Open link", task["link"], icon=":material/open_in_new:")
            else:
                st.caption(
                    "Local file or folder (copy the path, then paste it in File Explorer):"
                )
                st.code(task["link"], language=None)
        if task["notes"]:
            st.markdown(f"**Notes:** {plain(task['notes'])}")

        can_finish = task["type"] != "exam" and task["status"] != "done"
        if can_finish and st.button(
            "Mark as done", key=f"done-{tid}", icon=":material/check:"
        ):
            try:
                api.update_task(tid, {"status": "done"})
            except api.BackendError as exc:
                st.error(str(exc))
            else:
                notify(f"Marked {title} as done.")

        with st.form(f"edit-{tid}"):
            st.markdown("**Edit**")
            changes = task_fields(f"edit-{tid}", task["type"], courses, task)
            save_col, delete_col = st.columns(2)
            save = save_col.form_submit_button(
                "Save changes", key=f"save-{tid}", width="stretch"
            )
            delete = delete_col.form_submit_button(
                "Delete", key=f"delete-{tid}", width="stretch"
            )
            try:
                if save:
                    if problem := missing_fields(changes):
                        st.warning(problem)
                    else:
                        api.update_task(tid, changes)
                        notify(f"Saved {plain(changes['title'])}.")
                if delete:
                    api.delete_task(tid)
                    notify(f"Deleted {title}.")
            except api.BackendError as exc:
                st.error(str(exc))


if notice := st.session_state.pop("notice", None):
    st.success(notice)

# Drawn first so it sits at the top, filled in below once the courses are known.
add_box = st.container()

view = st.radio("View", VIEWS, horizontal=True, key="view")
include_done = st.toggle("Show done tasks", value=True, key="include-done")

try:
    with st.spinner("Loading tasks..."):
        if view == "By course":
            groups = api.list_tasks_by_course(include_done)
        else:
            groups = [{"course": None, "tasks": api.list_tasks(include_done)}]
except api.BackendError as exc:
    st.error(str(exc))
    st.stop()  # nothing else on this page works without the backend

courses = sorted({task["course"] for group in groups for task in group["tasks"]})
today = date.today()

with add_box, st.expander("Add a task", icon=":material/add:"):
    # Outside the form, so choosing a type redraws the form with that type's fields.
    new_type = st.selectbox("Type", list(TYPES), format_func=TYPES.get, key="add-type")
    with st.form("add", clear_on_submit=True):
        new_task = {"type": new_type, **task_fields("add", new_type, courses)}
        submitted = st.form_submit_button("Add task", key="add-submit", width="stretch")
        if submitted and (problem := missing_fields(new_task)):
            st.warning(problem)
        elif submitted:
            try:
                created = api.create_task(new_task)
            except api.BackendError as exc:
                st.error(str(exc))
            else:
                notify(f"Added {plain(created['title'])}.")

if not any(group["tasks"] for group in groups):
    st.info("No tasks yet. Open 'Add a task' above to add your first one.")
for group in groups:
    if group["course"] is not None:
        st.subheader(plain(group["course"]))
    for task in group["tasks"]:
        show_task(task, courses, today, show_course=group["course"] is None)

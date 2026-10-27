"""How tasks are put into words: names, icons and due dates."""

import string
from datetime import date, datetime

import api

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
FINISHED = ("done", "past")  # no more work needed: sorted last, can be hidden

# Every ASCII punctuation mark, prefixed with a backslash.
MARKDOWN_ESCAPES = str.maketrans({c: "\\" + c for c in string.punctuation})


def plain(text: str) -> str:
    """Escape Markdown so user text is shown, not interpreted."""
    return text.translate(MARKDOWN_ESCAPES)


def is_link(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def when(task: api.Task) -> str:
    return f"{datetime.fromisoformat(task['due_at']):%a %d %b, %H:%M}"


def countdown(task: api.Task, today: date) -> str:
    """How soon the task is due, in words, coloured by urgency."""
    if task["status"] == "done":
        return ":gray[done]"
    if task["status"] == "past":  # an exam whose date has passed
        return ":gray[past]"
    days = (datetime.fromisoformat(task["due_at"]).date() - today).days
    if days < 0:
        return f":red[overdue {-days} day{'s' if days < -1 else ''}]"
    if days == 0:
        return ":primary[**today**]"
    if days == 1:
        return ":primary[**tomorrow**]"
    return f"in {days} days"

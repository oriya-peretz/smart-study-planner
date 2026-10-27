"""How tasks are put into words: names, icons and due dates, in the user's language."""

import string
from datetime import date, datetime

import api
from texts import date_time, t

TYPES = ["exam", "submission", "online_quiz", "homework", "project"]
TYPE_ICONS = {
    "exam": ":material/school:",
    "submission": ":material/upload_file:",
    "online_quiz": ":material/computer:",
    "homework": ":material/edit_note:",
    "project": ":material/folder:",
}
STATUSES = ["todo", "in_progress", "done"]
FINISHED = ("done", "past")  # no more work needed: sorted last, can be hidden

# Every ASCII punctuation mark, prefixed with a backslash.
MARKDOWN_ESCAPES = str.maketrans({c: "\\" + c for c in string.punctuation})


def plain(text: str) -> str:
    """Escape Markdown so user text is shown, not interpreted."""
    return text.translate(MARKDOWN_ESCAPES)


def type_name(code: str) -> str:
    return t(f"type_{code}")


def status_name(code: str) -> str:
    return t(f"status_{code}")


def is_link(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def when(task: api.Task) -> str:
    return date_time(datetime.fromisoformat(task["due_at"]))


def countdown(task: api.Task, today: date) -> str:
    """How soon the task is due, in words, coloured by urgency."""
    if task["status"] == "done":
        return f":gray[{t('due_done')}]"
    if task["status"] == "past":  # an exam whose date has passed
        return f":gray[{t('due_past')}]"
    days = (datetime.fromisoformat(task["due_at"]).date() - today).days
    if days == -1:
        return f":red[{t('overdue_one')}]"
    if days < 0:
        return f":red[{t('overdue_many', n=-days)}]"
    if days == 0:
        return f":primary[**{t('due_today')}**]"
    if days == 1:
        return f":primary[**{t('due_tomorrow')}**]"
    return t("due_in_days", n=days)

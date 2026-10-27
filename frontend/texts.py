"""Every interface text in English and Hebrew, and the user's language.

What users type themselves (course names, task titles, notes) is never translated.
English is the default. The language lives in st.session_state["lang"]; while
logged in it is also saved to the account (see account.py).
"""

from datetime import datetime

import streamlit as st

import api

LANGUAGES = {"en": "English", "he": "עברית"}

TEXTS: dict[str, dict[str, str]] = {
    # ---- Landing, log in, sign up ----
    "tagline": {
        "en": "Every exam, assignment and project, in one place.",
        "he": "כל המבחנים, המטלות והפרויקטים, במקום אחד.",
    },
    "log_in": {"en": "Log in", "he": "התחברות"},
    "sign_up": {"en": "Sign up", "he": "הרשמה"},
    "email": {"en": "Email", "he": "אימייל"},
    "password": {"en": "Password", "he": "סיסמה"},
    "password_help": {"en": "At least 8 characters", "he": "לפחות 8 תווים"},
    "create_account": {"en": "Create account", "he": "יצירת חשבון"},
    "back": {"en": "Back", "he": "חזרה"},
    "logged_out": {"en": "You have logged out.", "he": "ההתנתקות הצליחה."},
    "session_ended": {
        "en": "Your session has ended. Please log in again.",
        "he": "החיבור הסתיים. יש להתחבר מחדש.",
    },
    "log_out": {"en": "Log out", "he": "התנתקות"},
    "language": {"en": "Language", "he": "שפה"},
    # ---- The app ----
    "view": {"en": "View", "he": "תצוגה"},
    "view_course": {"en": "By course", "he": "לפי קורס"},
    "view_urgency": {"en": "By urgency", "he": "לפי דחיפות"},
    "show_finished": {"en": "Show finished", "he": "הצגת משימות שהסתיימו"},
    "add_task": {"en": "Add task", "he": "הוספת משימה"},
    "loading": {"en": "Loading...", "he": "טוען..."},
    "welcome": {
        "en": "Welcome! Start by adding a course: choose **By course**, then the **+** card.",
        "he": "ברוכים הבאים! מתחילים בהוספת קורס: בוחרים **לפי קורס**, ואז את הכרטיס **+**.",
    },
    "no_tasks": {
        "en": "No tasks here. Use **Add task** to add one.",
        "he": "אין כאן משימות. אפשר להוסיף משימה עם **הוספת משימה**.",
    },
    "open_tasks_one": {"en": "1 open task", "he": "משימה פתוחה אחת"},
    "open_tasks_many": {"en": "{n} open tasks", "he": "{n} משימות פתוחות"},
    "settings": {"en": "Settings", "he": "הגדרות"},
    "no_tasks_yet": {"en": "No tasks yet", "he": "אין עדיין משימות"},
    "new_course": {"en": "New course", "he": "קורס חדש"},
    "open_link": {"en": "Open link", "he": "פתיחת הקישור"},
    "local_path": {
        "en": "Local file or folder (copy the path, then paste it in File Explorer):",
        "he": "קובץ או תיקייה במחשב (מעתיקים את הנתיב ומדביקים בסייר הקבצים):",
    },
    "mark_done": {"en": "Mark as done", "he": "סימון כבוצע"},
    "edit": {"en": "Edit", "he": "עריכה"},
    "hours": {"en": "{h} h", "he": "{h} שעות"},
    # ---- Task types and statuses ----
    "type_exam": {"en": "Exam", "he": "מבחן"},
    "type_submission": {"en": "Submission", "he": "מטלת הגשה"},
    "type_online_quiz": {"en": "Online quiz", "he": "בוחן ממוחשב"},
    "type_homework": {"en": "Homework", "he": "עבודת בית"},
    "type_project": {"en": "Project", "he": "פרויקט"},
    "status_todo": {"en": "To do", "he": "לביצוע"},
    "status_in_progress": {"en": "In progress", "he": "בתהליך"},
    "status_done": {"en": "Done", "he": "בוצע"},
    # ---- When a task is due ----
    "due_done": {"en": "done", "he": "בוצע"},
    "due_past": {"en": "past", "he": "עבר"},
    "overdue_one": {"en": "overdue 1 day", "he": "באיחור של יום"},
    "overdue_many": {"en": "overdue {n} days", "he": "באיחור של {n} ימים"},
    "due_today": {"en": "today", "he": "היום"},
    "due_tomorrow": {"en": "tomorrow", "he": "מחר"},
    "due_in_days": {"en": "in {n} days", "he": "בעוד {n} ימים"},
    # ---- Dialogs ----
    "dlg_add_task": {"en": "Add a task", "he": "הוספת משימה"},
    "dlg_edit_task": {"en": "Edit task", "he": "עריכת משימה"},
    "dlg_new_course": {"en": "New course", "he": "קורס חדש"},
    "dlg_course_settings": {"en": "Course settings", "he": "הגדרות הקורס"},
    "need_course_first": {
        "en": "Add a course first: choose **By course**, then the **+** card.",
        "he": "קודם מוסיפים קורס: בוחרים **לפי קורס**, ואז את הכרטיס **+**.",
    },
    "type": {"en": "Type", "he": "סוג"},
    "title": {"en": "Title", "he": "כותרת"},
    "course": {"en": "Course", "he": "קורס"},
    "choose_course": {"en": "Choose a course", "he": "בחירת קורס"},
    "exam_date": {"en": "Exam date", "he": "תאריך המבחן"},
    "due_date": {"en": "Due date", "he": "תאריך הגשה"},
    "time": {"en": "Time", "he": "שעה"},
    "study_hours": {"en": "Study hours (optional)", "he": "שעות למידה (רשות)"},
    "work_hours": {
        "en": "Estimated hours of work (optional)",
        "he": "שעות עבודה משוערות (רשות)",
    },
    "location": {"en": "Location (optional)", "he": "מיקום (רשות)"},
    "status": {"en": "Status", "he": "סטטוס"},
    "link": {"en": "Link (optional)", "he": "קישור (רשות)"},
    "link_placeholder": {
        "en": "https://... or C:\\path\\to\\file.docx",
        "he": "https://... או C:\\path\\to\\file.docx",
    },
    "notes": {"en": "Notes (optional)", "he": "הערות (רשות)"},
    "need_title": {
        "en": "Give the task a title before saving.",
        "he": "צריך לתת למשימה כותרת לפני השמירה.",
    },
    "need_course": {
        "en": "Choose a course before saving.",
        "he": "צריך לבחור קורס לפני השמירה.",
    },
    "added": {"en": "Added {title}.", "he": "נוסף: {title}"},
    "saved": {"en": "Saved {title}.", "he": "נשמר: {title}"},
    "deleted": {"en": "Deleted {title}.", "he": "נמחק: {title}"},
    "marked_done": {"en": "Marked {title} as done.", "he": "סומן כבוצע: {title}"},
    "save_changes": {"en": "Save changes", "he": "שמירת השינויים"},
    "delete_task": {"en": "Delete task", "he": "מחיקת המשימה"},
    "confirm_delete": {
        "en": "Delete this task for good?",
        "he": "למחוק את המשימה לצמיתות?",
    },
    "yes_delete": {"en": "Yes, delete", "he": "כן, למחוק"},
    "cancel": {"en": "Cancel", "he": "ביטול"},
    "course_name": {"en": "Course name", "he": "שם הקורס"},
    "add_course": {"en": "Add course", "he": "הוספת קורס"},
    "need_course_name": {"en": "Give the course a name.", "he": "צריך לתת לקורס שם."},
    "course_added": {"en": "Added the course {name}.", "he": "הקורס נוסף: {name}"},
    "rename": {"en": "Rename", "he": "שינוי שם"},
    "renamed": {"en": "Renamed to {name}.", "he": "השם שונה ל-{name}"},
    "delete_tasks_first": {
        "en": "To delete this course, delete its tasks first.",
        "he": "כדי למחוק את הקורס, צריך קודם למחוק את המשימות שלו.",
    },
    "delete_course": {"en": "Delete course", "he": "מחיקת הקורס"},
    "course_deleted": {"en": "Deleted the course {name}.", "he": "הקורס נמחק: {name}"},
    # ---- Errors (shown in Hebrew; in English api.py's own message is shown) ----
    "err_unavailable": {
        "en": "Cannot reach the server.",
        "he": "אין חיבור לשרת. יש לוודא שהוא פועל ולרענן את הדף.",
    },
    "err_no_answer_read": {
        "en": "The server took too long to answer.",
        "he": "השרת לא ענה בזמן. כדאי לרענן את הדף ולנסות שוב.",
    },
    "err_no_answer_write": {
        "en": "The server did not answer in time.",
        "he": "השרת לא ענה בזמן. ייתכן שהשינוי נשמר: כדאי לרענן את הדף ולבדוק לפני שמנסים שוב.",
    },
    "err_not_found": {
        "en": "That item no longer exists.",
        "he": "הפריט הזה כבר לא קיים. כדאי לרענן את הדף.",
    },
    "err_server_error": {
        "en": "The server failed ({status}).",
        "he": "השרת נכשל ({status}). כדאי לבדוק את הלוגים שלו.",
    },
    "err_wrong_service": {
        "en": "Another service answered.",
        "he": "שירות אחר ענה במקום השרת. כדאי לבדוק את BACKEND_URL.",
    },
    "err_wrong_login": {
        "en": "Wrong email or password",
        "he": "אימייל או סיסמה שגויים",
    },
    "err_email_taken": {
        "en": "An account with this email already exists",
        "he": "כבר קיים חשבון עם האימייל הזה",
    },
    "err_course_taken": {
        "en": "A course with this name already exists",
        "he": "כבר קיים קורס בשם הזה",
    },
    "err_course_has_tasks": {
        "en": "This course still has tasks.",
        "he": "בקורס הזה יש עדיין משימות. צריך למחוק אותן קודם.",
    },
    "err_session": {"en": "Not logged in", "he": "החיבור הסתיים. יש להתחבר מחדש."},
    "please_fix": {"en": "Please fix: ", "he": "יש לתקן: "},
}

# Hebrew words for the most common validation problems; anything else stays as sent.
FIELDS_HE = {
    "email": "אימייל",
    "password": "סיסמה",
    "name": "שם",
    "title": "כותרת",
    "course_id": "קורס",
    "due_at": "תאריך",
}
PROBLEMS_HE = {
    "String should have at least 8 characters": "צריך לפחות 8 תווים",
    "String should have at least 1 character": "השדה ריק",
    "value is not a valid email address": "כתובת אימייל לא תקינה",
}

# Backend messages that come back as plain text, by their first words.
BACKEND_MESSAGES = {
    "Wrong email or password": "err_wrong_login",
    "An account with this email already exists": "err_email_taken",
    "A course named": "err_course_taken",
    "This course still has tasks": "err_course_has_tasks",
    "Not logged in": "err_session",
}

WEEKDAYS_HE = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
MONTHS_HE = [
    "ינו׳", "פבר׳", "מרץ", "אפר׳", "מאי", "יוני",
    "יולי", "אוג׳", "ספט׳", "אוק׳", "נוב׳", "דצמ׳",
]  # fmt: skip


def language() -> str:
    return st.session_state.get("lang", "en")


def is_rtl() -> bool:
    return language() == "he"


def separator() -> str:
    """The dot between the parts of a line.

    In Hebrew each side gets an invisible right-to-left mark, so English runs
    (a task title next to a course name) keep their order instead of merging
    into one left-to-right run.
    """
    return "\u200f  ·  \u200f" if is_rtl() else "  ·  "


def t(key: str, **values) -> str:
    """The text for `key` in the current language, with {placeholders} filled in."""
    return TEXTS[key][language()].format(**values)


def date_time(moment: datetime) -> str:
    """'Wed 28 Oct, 18:00' in English; 'רביעי 28 אוק׳, 18:00' in Hebrew."""
    if language() == "he":
        weekday, month = WEEKDAYS_HE[moment.weekday()], MONTHS_HE[moment.month - 1]
        return f"{weekday} {moment.day} {month}, {moment:%H:%M}"
    return f"{moment:%a %d %b, %H:%M}"


def _problem_he(problem: str) -> str:
    field, _, message = problem.rpartition(": ")
    for english, hebrew in PROBLEMS_HE.items():
        if message.startswith(english):
            message = hebrew
    return f"{FIELDS_HE.get(field, field)}: {message}" if field else message


def error_message(exc: api.BackendError) -> str:
    """A backend error in the user's language."""
    if language() == "en":
        return str(exc)  # api.py's English message, unchanged
    if exc.code == "invalid":
        return t("please_fix") + "; ".join(
            _problem_he(p) for p in exc.details["problems"]
        )
    if exc.code == "backend_says":
        for start, key in BACKEND_MESSAGES.items():
            if exc.details["detail"].startswith(start):
                return t(key)
        return exc.details["detail"]
    return t(f"err_{exc.code}", **exc.details) if exc.code else str(exc)

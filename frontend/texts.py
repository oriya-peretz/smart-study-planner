"""Every interface text in English and Hebrew, and the user's language.

What users type themselves (course names, task titles, notes) is never translated.
English is the default. The language lives in st.session_state["lang"]; while
logged in it is also saved to the account (see account.py).
"""

from datetime import date, datetime

import streamlit as st

import api

LANGUAGES = {"en": "English", "he": "עברית"}

TEXTS: dict[str, dict[str, str]] = {
    # ---- Landing, log in, sign up ----
    "tagline": {
        "en": "Every exam, assignment and project, in one place",
        "he": "כל המבחנים, המטלות והפרויקטים, במקום אחד",
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
    "view_urgency": {"en": "By due date", "he": "לפי מועד"},
    "show_finished": {"en": "Show completed", "he": "להציג גם מה שהושלם"},
    "add_task": {"en": "Add a task or exam", "he": "הוספת מטלה או מבחן"},
    "loading": {"en": "Loading...", "he": "טוען..."},
    "welcome": {
        "en": "Welcome! Start by adding a course: choose **By course**, then the **+** card.",
        "he": "ברוכים הבאים! מתחילים בהוספת קורס: בוחרים **לפי קורס**, ואז את הכרטיס **+**.",
    },
    "no_tasks": {
        "en": "Nothing here yet. Use **Add a task or exam** to add one.",
        "he": "אין כאן עדיין מטלות או מבחנים. מוסיפים עם **הוספת מטלה או מבחן**.",
    },
    "open_tasks_one": {"en": "1 open task", "he": "מטלה פתוחה אחת"},
    "open_tasks_many": {"en": "{n} open tasks", "he": "{n} מטלות פתוחות"},
    "edit_course": {"en": "Edit course", "he": "עריכת הקורס"},
    "no_tasks_yet": {"en": "No tasks yet", "he": "אין עדיין מטלות"},
    "add_new_course": {"en": "Add a new course", "he": "הוספת קורס חדש"},
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
    "dlg_add_task": {"en": "Add a task or exam", "he": "הוספת מטלה או מבחן"},
    "dlg_edit_task": {"en": "Edit", "he": "עריכה"},
    "dlg_new_course": {"en": "New course", "he": "קורס חדש"},
    "dlg_edit_course": {"en": "Edit course", "he": "עריכת קורס"},
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
        "en": "Give it a title before saving.",
        "he": "צריך לתת כותרת לפני השמירה.",
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
    "delete_task": {"en": "Delete task", "he": "מחיקה"},
    "confirm_delete": {
        "en": "Delete this for good?",
        "he": "למחוק לצמיתות?",
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
        "en": "To delete this course, delete its tasks and exams first.",
        "he": "כדי למחוק את הקורס, צריך קודם למחוק את המטלות והמבחנים שלו.",
    },
    "delete_course": {"en": "Delete course", "he": "מחיקת הקורס"},
    "course_deleted": {"en": "Deleted the course {name}.", "he": "הקורס נמחק: {name}"},
    # ---- The study plan ----
    "page": {"en": "Page", "he": "עמוד"},
    "page_tasks": {"en": "Tasks and exams", "he": "מטלות ומבחנים"},
    "page_plan": {"en": "Weekly study plan", "he": "תוכנית לימוד שבועית"},
    "edit_hours": {"en": "Free study time", "he": "זמן פנוי ללימודים"},
    "dlg_study_hours": {"en": "Free study time", "he": "הגדרת זמן פנוי ללימודים"},
    "hours_intro": {
        "en": "How many hours are you free to study on each day of the week?",
        "he": "כמה שעות פנויות יש לך ללימודים בכל יום בשבוע?",
    },
    "day_sunday": {"en": "Sunday", "he": "ראשון"},
    "day_monday": {"en": "Monday", "he": "שני"},
    "day_tuesday": {"en": "Tuesday", "he": "שלישי"},
    "day_wednesday": {"en": "Wednesday", "he": "רביעי"},
    "day_thursday": {"en": "Thursday", "he": "חמישי"},
    "day_friday": {"en": "Friday", "he": "שישי"},
    "day_saturday": {"en": "Saturday", "he": "שבת"},
    "blocked_dates": {
        "en": "Dates with no study time",
        "he": "תאריכים בלי זמן ללימודים",
    },
    "choose_dates": {"en": "Choose dates", "he": "בחירת תאריכים"},
    "blocked_help": {
        "en": "For example a trip or a family event, in the next 8 weeks.",
        "he": "למשל טיול או אירוע משפחתי, ב-8 השבועות הקרובים.",
    },
    "plan_note": {"en": "A note for the plan (optional)", "he": "הערה לתכנון (רשות)"},
    "plan_note_help": {
        "en": 'Such as "keep Thursday light". It cannot change the free time above.',
        "he": 'למשל "להשאיר את יום חמישי קל". ההערה לא משנה את הזמן הפנוי שהגדרת.',
    },
    "save": {"en": "Save free time", "he": "שמירת הזמן הפנוי"},
    "hours_saved": {"en": "Saved your free study time.", "he": "הזמן הפנוי נשמר."},
    "build_plan": {"en": "Create study plan", "he": "יצירת תוכנית לימוד"},
    "rebuild_plan": {"en": "Update study plan", "he": "עדכון תוכנית הלימוד"},
    "plan_building": {
        "en": "Planning your week. This can take up to a minute...",
        "he": "מתכננים את השבוע. זה יכול לקחת עד דקה...",
    },
    "plan_built": {"en": "Your study plan is ready.", "he": "תוכנית הלימוד מוכנה."},
    "plan_set_hours_first": {
        "en": "To create a plan, first set how much free study time you have each day.",
        "he": "כדי ליצור תוכנית, צריך קודם להגדיר כמה זמן פנוי יש לך ללימודים בכל יום.",
    },
    "plan_none_yet": {
        "en": "No study plan yet.",
        "he": "עדיין אין תוכנית לימוד.",
    },
    "plan_made": {"en": "Made {when}", "he": "נוצרה ביום {when}"},
    "plan_by_model": {
        "en": "The AI model arranged this week, and the planning rules checked it.",
        "he": "מודל ה-AI סידר את השבוע, וכללי התכנון בדקו אותו.",
    },
    "plan_by_rules": {
        "en": "The plan was calculated by the planning rules.",
        "he": "התוכנית חושבה לפי כללי התכנון.",
    },
    "plan_fallback": {
        "en": "The plan was calculated by the planning rules, because {reason}.",
        "he": "התוכנית חושבה לפי כללי התכנון, כי {reason}.",
    },
    "reason_invalid_output": {
        "en": "the AI model's suggestion broke the rules",
        "he": "ההצעה של מודל ה-AI הפרה את הכללים",
    },
    "reason_budget_exceeded": {
        "en": "the AI model used up its budget",
        "he": "מודל ה-AI חרג מהמכסה שלו",
    },
    "reason_timeout": {
        "en": "the AI model took too long",
        "he": "מודל ה-AI לקח יותר מדי זמן",
    },
    "reason_provider_error": {
        "en": "the AI model could not be reached",
        "he": "לא הייתה גישה למודל ה-AI",
    },
    "plan_outdated": {
        "en": "The plan is out of date: something changed in your tasks or free time since it was made.",
        "he": "התוכנית לא מעודכנת: משהו השתנה במטלות או בזמן הפנוי מאז שנוצרה.",
    },
    "plan_tasks": {
        "en": "Tasks and exams in the plan",
        "he": "המטלות והמבחנים בתוכנית",
    },
    "day_off": {"en": "No free time", "he": "אין זמן פנוי"},
    "add_to_course": {"en": "Add", "he": "הוספה"},
    "plan_subtitle": {
        "en": "How your study time is split between tasks and exams this week",
        "he": "חלוקת זמן הלימוד שלך בין המטלות והמבחנים השבוע",
    },
    "plan_details": {"en": "Details", "he": "פרטים"},
    "plan_basis": {
        "en": "The plan follows your free study time and due dates. Its hours come "
        "from your estimates: they are planned study time, not work already done.",
        "he": "התוכנית מתאימה לזמן הפנוי שהגדרת ולמועדים. השעות מבוססות על "
        "ההערכות שלך: זה זמן לימוד מתוכנן, לא עבודה שכבר בוצעה.",
    },
    "day_free": {"en": "Free: {h}", "he": "זמן פנוי: {h}"},
    "status_planned": {
        "en": "All the study time it needs is in the plan",
        "he": "כל זמן הלימוד הנדרש מופיע בתוכנית",
    },
    "status_short_one": {
        "en": "The plan is still {h} short before {due}",
        "he": "חסרה בתוכנית עוד {h} לפני {due}",
    },
    "status_short_many": {
        "en": "The plan is still {h} short before {due}",
        "he": "חסרות בתוכנית עוד {h} לפני {due}",
    },
    "status_no_estimate_exam": {
        "en": "To plan study time for this exam, enter the hours it needs",
        "he": "כדי לתכנן לימוד למבחן, צריך להזין כמה שעות נדרשות",
    },
    "status_no_estimate_task": {
        "en": "To plan study time for this task, enter the hours it needs",
        "he": "כדי לתכנן לימוד למטלה, צריך להזין כמה שעות נדרשות",
    },
    "status_overdue": {
        "en": "Its due date has passed, so it is not in the plan",
        "he": "המועד עבר, ולכן אין לזה זמן בתוכנית",
    },
    "status_later": {
        "en": "Due more than 8 weeks ahead, so not in the plan yet",
        "he": "המועד בעוד יותר מ-8 שבועות, ולכן עוד לא בתוכנית",
    },
    "due_word_task": {"en": "the due date", "he": "ההגשה"},
    "due_word_exam": {"en": "the exam", "he": "המבחן"},
    "detail_needed": {"en": "Study time needed: {h}", "he": "זמן לימוד נדרש: {h}"},
    "detail_planned": {
        "en": "In the plan before {due}: {h}",
        "he": "בתוכנית לפני {due}: {h}",
    },
    "detail_this_week": {"en": "this week: {h}", "he": "השבוע: {h}"},
    "detail_missing": {"en": "Still missing: {h}", "he": "עוד חסר בתוכנית: {h}"},
    "detail_short_hint": {
        "en": "To fit it in, add free study time or update the hours it needs.",
        "he": "כדי שייכנס, אפשר להוסיף זמן פנוי או לעדכן כמה שעות נדרשות.",
    },
    "detail_edit_hint": {
        "en": "Enter it by editing it under Tasks and exams.",
        "he": "אפשר להזין את זה בעריכה, במסך מטלות ומבחנים.",
    },
    "plan_failed": {
        "en": "Couldn't create a new plan right now. Your previous plan is kept. "
        "Try again in a few minutes.",
        "he": "לא הצלחנו ליצור תוכנית חדשה כרגע. התוכנית הקודמת נשמרה. "
        "אפשר לנסות שוב בעוד כמה דקות.",
    },
    "plan_failed_bad": {
        "en": "Couldn't use the new plan. Your previous plan is kept.",
        "he": "לא הצלחנו להשתמש בתוכנית החדשה. התוכנית הקודמת נשמרה.",
    },
    "tech_details": {"en": "Technical details", "he": "פרטים טכניים"},
    "tech_unavailable": {
        "en": "The AI service did not answer (503).",
        "he": "שירות ה-AI לא ענה (503).",
    },
    "tech_bad_output": {
        "en": "The AI service's answer failed the backend's checks (502).",
        "he": "התשובה של שירות ה-AI לא עברה את הבדיקות של השרת (502).",
    },
    # ---- Errors (shown in Hebrew; in English api.py's own message is shown) ----
    "err_unavailable": {
        "en": "Cannot reach the server.",
        "he": "אין חיבור לשרת. יש לוודא שהוא פועל ולנסות שוב.",
    },
    "err_no_answer_read": {
        "en": "The server took too long to answer.",
        "he": "השרת לא ענה בזמן. כדאי לנסות שוב.",
    },
    "err_no_answer_write": {
        "en": "The server did not answer in time.",
        "he": "השרת לא ענה בזמן. ייתכן שהשינוי נשמר: כדאי לבדוק את המטלות לפני שמנסים שוב.",
    },
    "err_not_found": {
        "en": "That item no longer exists.",
        "he": "הפריט הזה כבר לא קיים.",
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
        "he": "בקורס הזה יש עדיין מטלות או מבחנים. צריך למחוק אותם קודם.",
    },
    "err_session": {"en": "Not logged in", "he": "החיבור הסתיים. יש להתחבר מחדש."},
    "err_ai_unavailable": {
        "en": "The planning service is not available right now.",
        "he": "שירות התכנון לא זמין כרגע. התוכנית השמורה לא השתנתה; כדאי לנסות שוב בעוד דקה.",
    },
    "err_ai_bad_output": {
        "en": "The planning service gave an answer that could not be used.",
        "he": "שירות התכנון החזיר תשובה שאי אפשר להשתמש בה. התוכנית השמורה לא השתנתה.",
    },
    "err_need_hours": {
        "en": "Set your free study hours first.",
        "he": "קודם צריך להגדיר את שעות הלימוד.",
    },
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
    "Set your free study hours first": "err_need_hours",
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


def day_label(day: date) -> str:
    """'Sun 1 Nov' in English; 'ראשון 1 נוב׳' in Hebrew."""
    if language() == "he":
        return f"{WEEKDAYS_HE[day.weekday()]} {day.day} {MONTHS_HE[day.month - 1]}"
    return f"{day:%a} {day.day} {day:%b}"


def duration(hours: float) -> str:
    """Hours in words: '1 hour', '2.5 hours'; 'שעה', 'שעתיים וחצי' in Hebrew."""
    if language() == "he":
        whole, half = int(hours), hours % 1 >= 0.5
        words = {0: "", 1: "שעה", 2: "שעתיים"}.get(whole, f"{whole} שעות")
        if not words:
            return "חצי שעה" if half else "0 שעות"
        return f"{words} וחצי" if half else words
    return "1 hour" if hours == 1 else f"{hours:g} hours"


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

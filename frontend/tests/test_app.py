"""AppTest runs streamlit_app.py in-process; respx fakes every backend call.

No browser and no backend are involved: each test decides what the backend
answers, so every state (empty, error, slow, expired session) can be produced
on demand. What these tests cannot see is whether the real backend still
answers in these shapes; the backend's own tests cover that side.
"""

import json
from datetime import date, timedelta

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

from api import BACKEND_URL

APP = "../streamlit_app.py"  # resolved relative to this test file
TOKEN = "test-token"
AUTOMATA = {"id": 1, "name": "Automata"}
ME = {"id": 1, "email": "student@example.com", "language": "en"}
STATISTICS = {"id": 2, "name": "Statistics"}


def task(task_id, title, course=AUTOMATA, type="homework", days=3, **fields):
    """A task as the backend returns it, due `days` from today at 23:59."""
    due = (date.today() + timedelta(days=days)).isoformat() + "T23:59:00"
    base = {
        "id": task_id,
        "title": title,
        "course_id": course["id"],
        "course": course,
        "type": type,
        "due_at": due,
        "estimated_hours": None,
        "status": None if type == "exam" else "todo",
        "link": None,
        "location": None,
        "notes": None,
    }
    return base | fields


@pytest.fixture
def backend():
    with respx.mock(base_url=BACKEND_URL, assert_all_called=False) as mock:
        yield mock


def logged_out() -> AppTest:
    # 30 s instead of the 3 s default: a cold first run can be slow.
    return AppTest.from_file(APP, default_timeout=30).run()


def logged_in(backend, courses, tasks=(), groups=None) -> AppTest:
    backend.get("/courses").mock(return_value=httpx.Response(200, json=courses))
    backend.get("/tasks").mock(return_value=httpx.Response(200, json=list(tasks)))
    by_course = (
        groups if groups is not None else [{"course": c, "tasks": []} for c in courses]
    )
    backend.get("/tasks/by-course").mock(
        return_value=httpx.Response(200, json=by_course)
    )
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["token"] = TOKEN
    at.session_state["email"] = "student@example.com"
    return at.run()


def sent_json(route) -> dict:
    return json.loads(route.calls.last.request.content)


# ---- Landing, log in, sign up ----


def test_landing_screen_when_logged_out(backend):
    at = logged_out()
    assert not at.exception
    assert [b.label for b in at.button] == ["Log in", "Sign up"]
    assert not backend.calls  # nothing is loaded before logging in


def test_log_in_keeps_the_token_and_uses_it(backend):
    login = backend.post("/auth/login").mock(
        return_value=httpx.Response(200, json={"access_token": "fresh-token"})
    )
    backend.get("/auth/me").mock(return_value=httpx.Response(200, json=ME))
    backend.get("/courses").mock(return_value=httpx.Response(200, json=[AUTOMATA]))
    tasks = backend.get("/tasks").mock(
        return_value=httpx.Response(200, json=[task(7, "Exercise 3")])
    )
    at = logged_out()
    at.button(key="go-login").click().run()
    at.text_input(key="auth-email").input("Student@Example.com")
    at.text_input(key="auth-password").input("a long password")
    at.button(key="auth-submit").click().run()

    assert not at.exception
    assert sent_json(login) == {
        "email": "Student@Example.com",
        "password": "a long password",
    }
    assert at.session_state["token"] == "fresh-token"
    assert tasks.calls.last.request.headers["Authorization"] == "Bearer fresh-token"
    assert "Exercise 3" in at.expander[0].label


def test_wrong_password_shows_the_backend_message(backend):
    backend.post("/auth/login").mock(
        return_value=httpx.Response(401, json={"detail": "Wrong email or password"})
    )
    at = logged_out()
    at.button(key="go-login").click().run()
    at.text_input(key="auth-email").input("student@example.com")
    at.text_input(key="auth-password").input("wrong password")
    at.button(key="auth-submit").click().run()
    assert at.error[0].value == "Wrong email or password"
    assert "token" not in at.session_state


def test_sign_up_validation_error_is_shown_in_words(backend):
    detail = [
        {"loc": ["body", "password"], "msg": "String should have at least 8 characters"}
    ]
    backend.post("/auth/signup").mock(
        return_value=httpx.Response(422, json={"detail": detail})
    )
    at = logged_out()
    at.button(key="go-signup").click().run()
    at.text_input(key="auth-email").input("student@example.com")
    at.text_input(key="auth-password").input("short")
    at.button(key="auth-submit").click().run()
    assert (
        at.error[0].value
        == "Please fix: password: String should have at least 8 characters"
    )


# ---- The two views ----


def test_urgency_view_is_numbered_in_the_backends_order(backend):
    at = logged_in(
        backend,
        [AUTOMATA, STATISTICS],
        [
            task(1, "Lab report", STATISTICS, days=-2),
            task(2, "Quiz 2", STATISTICS, days=1),
        ],
    )
    first, second = at.expander[0].label, at.expander[1].label
    assert "01" in first and "Lab report" in first and "overdue 2 days" in first
    assert "02" in second and "Quiz 2" in second and "tomorrow" in second


def test_welcome_message_before_the_first_course(backend):
    at = logged_in(backend, [])
    assert "Start by adding a course" in at.info[0].value
    assert len(at.expander) == 0


def test_by_course_lists_every_task_inside_its_course_card(backend):
    groups = [
        {
            "course": STATISTICS,
            "tasks": [
                task(1, "Quiz 2", STATISTICS, days=1),
                task(2, "Lab report", STATISTICS, days=5),
            ],
        },
        {"course": AUTOMATA, "tasks": []},
    ]
    at = logged_in(backend, [AUTOMATA, STATISTICS], groups=groups)
    at.button_group(key="view").set_value("course").run()

    headings = [m.value for m in at.markdown if m.value.startswith("####")]
    assert headings == ["#### Statistics", "#### Automata"]
    labels = [e.label for e in at.expander]
    assert "Quiz 2" in labels[0] and "Lab report" in labels[1]
    assert all(
        "Statistics" not in label for label in labels
    )  # the card says it already
    assert "No tasks yet" in " ".join(c.value for c in at.caption)
    assert at.button(key="new-course").label == "New course"


def test_add_task_from_a_course_card_preselects_that_course(backend):
    at = logged_in(
        backend, [AUTOMATA, STATISTICS], groups=[{"course": STATISTICS, "tasks": []}]
    )
    at.button_group(key="view").set_value("course").run()
    at.button(key="course-add-2").click().run()
    assert at.selectbox(key="add-course").value == 2


# ---- Failures ----


def test_backend_down_shows_the_next_step_not_a_traceback(backend):
    backend.get("/courses").mock(side_effect=httpx.ConnectError("refused"))
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["token"] = TOKEN
    at.session_state["email"] = "student@example.com"
    at.run()
    assert not at.exception
    assert "Cannot reach the backend" in at.error[0].value
    assert len(at.expander) == 0  # st.stop(): the rest of the page is not drawn


def test_expired_session_returns_to_the_landing_screen(backend):
    backend.get("/courses").mock(
        return_value=httpx.Response(
            401, json={"detail": "Not logged in, or the session has expired"}
        )
    )
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["token"] = "old-token"
    at.session_state["email"] = "student@example.com"
    at.run()
    assert not at.exception
    assert "token" not in at.session_state
    assert [b.label for b in at.button] == ["Log in", "Sign up"]


# ---- Changes are sent exactly, with the token ----


def test_mark_as_done_sends_the_status_and_the_token(backend):
    patch = backend.patch("/tasks/7").mock(
        return_value=httpx.Response(200, json=task(7, "Exercise 3", status="done"))
    )
    at = logged_in(backend, [AUTOMATA], [task(7, "Exercise 3")])
    at.button(key="done-7").click().run()
    assert sent_json(patch) == {"status": "done"}
    assert patch.calls.last.request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert at.success[0].value == "Marked Exercise 3 as done."


def test_lost_reply_after_a_write_says_the_outcome_is_unknown(backend):
    backend.patch("/tasks/7").mock(side_effect=httpx.ReadTimeout("no reply"))
    at = logged_in(backend, [AUTOMATA], [task(7, "Exercise 3")])
    at.button(key="done-7").click().run()
    assert not at.exception
    assert "may have been saved" in at.error[0].value  # not "cannot reach"


def test_add_task_sends_exactly_the_fields_of_its_type(backend):
    post = backend.post("/tasks").mock(
        return_value=httpx.Response(201, json=task(9, "Exercise 4"))
    )
    at = logged_in(backend, [AUTOMATA, STATISTICS])
    at.button(key="add-task").click().run()
    at.selectbox(key="add-type").set_value(
        "homework"
    ).run()  # the form redraws for homework
    at.text_input(key="add-title").input("Exercise 4")
    at.selectbox(key="add-course").set_value(2)
    at.number_input(key="add-hours").set_value(3.5)
    at.button(key="add-submit").click().run()

    assert sent_json(post) == {
        "type": "homework",
        "title": "Exercise 4",
        "course_id": 2,
        "due_at": f"{date.today().isoformat()}T23:59:00",  # homework defaults to 23:59
        "estimated_hours": 3.5,
        "status": "todo",
        "link": None,  # an empty optional field is sent as null
        "notes": None,
    }
    assert at.success[0].value == "Added Exercise 4."


def test_exam_form_has_location_and_no_status_or_link(backend):
    at = logged_in(backend, [AUTOMATA])
    at.button(key="add-task").click().run()  # an exam is the first type
    keys = {w.key for w in [*at.text_input, *at.selectbox]}
    assert "add-location" in keys
    assert not keys & {"add-status", "add-link"}


def test_add_task_without_a_course_warns_before_any_request(backend):
    post = backend.post("/tasks")
    at = logged_in(backend, [AUTOMATA])
    at.button(key="add-task").click().run()
    at.text_input(key="add-title").input("Final exam")
    at.button(key="add-submit").click().run()
    assert at.warning[0].value == "Choose a course before saving."
    assert not post.called


# ---- Language ----


def is_right_to_left(at: AppTest) -> bool:
    return any("direction: rtl" in element.proto.body for element in at.get("html"))


def test_switching_to_hebrew_on_the_landing_screen(backend):
    at = logged_out()
    assert not is_right_to_left(at)
    at.button_group(key="lang-picker").set_value("he").run()
    assert [b.label for b in at.button] == ["התחברות", "הרשמה"]
    assert is_right_to_left(at)
    assert not backend.calls  # nobody is logged in, so nothing is saved yet


def test_log_in_brings_back_the_accounts_language(backend):
    backend.post("/auth/login").mock(
        return_value=httpx.Response(200, json={"access_token": "fresh-token"})
    )
    backend.get("/auth/me").mock(
        return_value=httpx.Response(200, json=ME | {"language": "he"})
    )
    backend.get("/courses").mock(return_value=httpx.Response(200, json=[AUTOMATA]))
    backend.get("/tasks").mock(return_value=httpx.Response(200, json=[]))
    at = logged_out()  # in English
    at.button(key="go-login").click().run()
    at.text_input(key="auth-email").input("student@example.com")
    at.text_input(key="auth-password").input("a long password")
    at.button(key="auth-submit").click().run()
    assert at.session_state["lang"] == "he"
    assert at.button(key="add-task").label == "הוספת משימה"
    assert is_right_to_left(at)


def test_a_new_account_keeps_the_language_chosen_on_the_landing_screen(backend):
    backend.post("/auth/signup").mock(return_value=httpx.Response(201, json=ME))
    backend.post("/auth/login").mock(
        return_value=httpx.Response(200, json={"access_token": "fresh-token"})
    )
    saved = backend.patch("/auth/me").mock(
        return_value=httpx.Response(200, json=ME | {"language": "he"})
    )
    backend.get("/courses").mock(return_value=httpx.Response(200, json=[]))
    backend.get("/tasks").mock(return_value=httpx.Response(200, json=[]))
    at = logged_out()
    at.button_group(key="lang-picker").set_value("he").run()
    at.button(key="go-signup").click().run()
    at.text_input(key="auth-email").input("new@example.com")
    at.text_input(key="auth-password").input("a long password")
    at.button(key="auth-submit").click().run()
    assert sent_json(saved) == {"language": "he"}
    assert saved.calls.last.request.headers["Authorization"] == "Bearer fresh-token"


def test_switching_language_while_logged_in_saves_it_to_the_account(backend):
    saved = backend.patch("/auth/me").mock(
        return_value=httpx.Response(200, json=ME | {"language": "he"})
    )
    at = logged_in(backend, [AUTOMATA], [task(7, "Exercise 3", days=1)])
    at.button_group(key="lang-picker").set_value("he").run()
    assert sent_json(saved) == {"language": "he"}
    assert saved.calls.last.request.headers["Authorization"] == f"Bearer {TOKEN}"
    label = at.expander[0].label
    assert "Exercise 3" in label  # what the user typed is never translated
    assert "עבודת בית" in label and "מחר" in label
    assert at.button(key="add-task").label == "הוספת משימה"


def test_backend_errors_are_shown_in_hebrew(backend):
    backend.post("/auth/login").mock(
        return_value=httpx.Response(401, json={"detail": "Wrong email or password"})
    )
    at = logged_out()
    at.button_group(key="lang-picker").set_value("he").run()
    at.button(key="go-login").click().run()
    at.text_input(key="auth-email").input("student@example.com")
    at.text_input(key="auth-password").input("wrong password")
    at.button(key="auth-submit").click().run()
    assert at.error[0].value == "אימייל או סיסמה שגויים"


def test_log_out_keeps_the_language(backend):
    backend.post("/auth/logout").mock(return_value=httpx.Response(204))
    backend.patch("/auth/me").mock(
        return_value=httpx.Response(200, json=ME | {"language": "he"})
    )
    at = logged_in(backend, [AUTOMATA])
    at.button_group(key="lang-picker").set_value("he").run()
    at.button(key="log-out").click().run()
    assert "token" not in at.session_state
    assert [b.label for b in at.button] == ["התחברות", "הרשמה"]


def test_language_picked_before_logging_in_wins_and_is_saved(backend):
    backend.post("/auth/login").mock(
        return_value=httpx.Response(200, json={"access_token": "fresh-token"})
    )
    me = backend.get("/auth/me").mock(return_value=httpx.Response(200, json=ME))
    saved = backend.patch("/auth/me").mock(
        return_value=httpx.Response(200, json=ME | {"language": "he"})
    )
    backend.get("/courses").mock(return_value=httpx.Response(200, json=[]))
    backend.get("/tasks").mock(return_value=httpx.Response(200, json=[]))
    at = logged_out()
    at.button_group(key="lang-picker").set_value("he").run()
    at.button(key="go-login").click().run()
    at.text_input(key="auth-email").input("student@example.com")
    at.text_input(key="auth-password").input("a long password")
    at.button(key="auth-submit").click().run()
    assert at.session_state["lang"] == "he"  # not replaced by the account's "en"
    assert sent_json(saved) == {"language": "he"}
    assert not me.called


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", "The backend failed (500). Check its logs."),
        ("he", "השרת נכשל (500). כדאי לבדוק את הלוגים שלו."),
    ],
)
def test_a_server_error_is_shown_in_the_users_language(backend, language, expected):
    backend.post("/auth/login").mock(return_value=httpx.Response(500, text="boom"))
    at = logged_out()
    if language == "he":
        at.button_group(key="lang-picker").set_value("he").run()
    at.button(key="go-login").click().run()
    at.text_input(key="auth-email").input("student@example.com")
    at.text_input(key="auth-password").input("a long password")
    at.button(key="auth-submit").click().run()
    assert not at.exception
    assert at.error[0].value == expected


def test_hebrew_lines_keep_english_parts_in_order(backend):
    backend.patch("/auth/me").mock(return_value=httpx.Response(200, json=ME))
    at = logged_in(backend, [STATISTICS], [task(1, "Quiz 2", STATISTICS, days=1)])
    at.button_group(key="lang-picker").set_value("he").run()
    label = at.expander[0].label
    # Every separator carries right-to-left marks, so "Quiz 2" and "Statistics"
    # stay separate parts in the order they were written.
    assert label.count("\u200f  ·  \u200f") == 4
    assert label.index("Quiz 2") < label.index("Statistics")

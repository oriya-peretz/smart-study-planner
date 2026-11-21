"""The Weekly study plan page, with the backend faked by respx (see test_app.py)."""

import json
from datetime import date, timedelta

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

from api import BACKEND_URL, PLAN_TIMEOUT

APP = "../streamlit_app.py"
TOKEN = "test-token"
TODAY = date.today()
WEEKLY = {
    "sunday": 2,
    "monday": 2,
    "tuesday": 0,
    "wednesday": 3,
    "thursday": 0,
    "friday": 0,
    "saturday": 0,
}
SAVED = {"weekly_hours": WEEKLY, "blocked_dates": [], "note": "", "saved": True}
UNSAVED = {
    "weekly_hours": dict.fromkeys(WEEKLY, 0),
    "blocked_dates": [],
    "note": "",
    "saved": False,
}


def day(offset: int, free: float = 0, blocks=()) -> dict:
    return {
        "date": (TODAY + timedelta(days=offset)).isoformat(),
        "free_hours": free,
        "planned_hours": sum(block["hours"] for block in blocks),
        "blocks": list(blocks),
    }


def assessed(task_id, title, assessment, **numbers) -> dict:
    return {
        "task_id": task_id,
        "title": title,
        "course": "Automata",
        "type": "homework",
        "due_at": (TODAY + timedelta(days=5)).isoformat() + "T23:59:00",
        "assessment": assessment,
        "needed_hours": 3,
        "free_hours_before_due": 7,
        "slack_hours": 4,
        "planned_hours": 3,
        "planned_hours_this_week": 3,
        "missing_hours": 0,
    } | numbers


SHEET = {"task_id": 1, "title": "Sheet 3", "course": "Automata", "hours": 2}
PLAN = {
    "created_at": f"{TODAY.isoformat()}T09:30:00",
    "start_date": TODAY.isoformat(),
    "horizon_end": (TODAY + timedelta(days=55)).isoformat(),
    "source": "model",
    "fallback_reason": None,
    "all_fit": True,
    "outdated": False,
    "days": [day(0, 2, [SHEET])] + [day(i) for i in range(1, 7)],
    "tasks": [assessed(1, "Sheet 3", "on_track")],
}


@pytest.fixture
def backend():
    with respx.mock(base_url=BACKEND_URL, assert_all_called=False) as mock:
        yield mock


def my_plan(backend, constraints=SAVED, plan=PLAN) -> AppTest:
    """A logged-in user on the My plan page."""
    backend.get("/constraints").mock(return_value=httpx.Response(200, json=constraints))
    if plan is None:
        answer = httpx.Response(404, json={"detail": "No plan yet"})
    else:
        answer = httpx.Response(200, json=plan)
    backend.get("/plan").mock(return_value=answer)
    backend.get("/courses").mock(return_value=httpx.Response(200, json=[]))
    backend.get("/tasks").mock(return_value=httpx.Response(200, json=[]))
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["token"] = TOKEN
    at.session_state["email"] = "student@example.com"
    at.run()
    at.button_group(key="page").set_value("plan").run()
    return at


def text(at: AppTest) -> str:
    """Everything the page says in words, including expander labels."""
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [box.value for box in (*at.info, *at.warning, *at.success, *at.error)]
    parts += [e.label for e in at.expander]
    return "\n".join(parts)


def week(at: AppTest) -> str:
    """The day cards, which are drawn as HTML."""
    return "".join(e.proto.body for e in at.get("html") if "plan-week" in e.proto.body)


def primary(at: AppTest) -> list[str]:
    """The labels of the page's primary buttons."""
    return [b.label for b in at.button if b.proto.type == "primary"]


def test_before_any_free_time_setting_it_is_the_one_main_action(backend):
    build = backend.post("/plan")
    at = my_plan(backend, constraints=UNSAVED, plan=None)

    assert not at.exception
    assert "first set how much free study time" in at.info[0].value
    assert primary(at) == ["Free study time"]
    assert not [b for b in at.button if b.key == "build-plan"]  # nothing to click yet
    assert not build.called


def test_with_free_time_but_no_plan_the_main_action_is_create(backend):
    at = my_plan(backend, plan=None)

    assert primary(at) == ["Create study plan"]
    assert at.button(key="edit-hours").proto.type == "tertiary"  # quieter
    assert "No study plan yet." in text(at)


def test_the_plan_shows_the_week_as_day_cards(backend):
    at = my_plan(backend)
    cards = week(at)

    assert primary(at) == ["Update study plan"]
    assert cards.count('class="plan-day') == 7
    assert "Sheet 3" in cards and "Automata" in cards and "2 hours" in cards
    assert "Free: 2 hours" in cards
    assert cards.count("No free time") == 6
    assert "How your study time is split" in text(at)


def test_a_title_cannot_inject_html_into_the_week(backend):
    sneaky = SHEET | {"title": "<b>Sheet</b>"}
    at = my_plan(
        backend, plan=PLAN | {"days": [day(0, 2, [sneaky])] + PLAN["days"][1:]}
    )

    assert "&lt;b&gt;Sheet&lt;/b&gt;" in week(at)


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        pytest.param(
            assessed(1, "Sheet 3", "on_track"),
            "All the study time it needs is in the plan",
            id="planned",
        ),
        pytest.param(
            assessed(1, "Sheet 3", "shortfall", planned_hours=7.5, missing_hours=2.5),
            "The plan is still 2.5 hours short before the due date",
            id="shortfall",
        ),
        pytest.param(
            assessed(1, "Sheet 3", "no_estimate", needed_hours=None),
            "To plan study time for this task, enter the hours it needs",
            id="no-estimate-task",
        ),
        pytest.param(
            assessed(1, "Final", "no_estimate", needed_hours=None, type="exam"),
            "To plan study time for this exam, enter the hours it needs",
            id="no-estimate-exam",
        ),
        pytest.param(
            assessed(1, "Sheet 3", "overdue"),
            "Its due date has passed, so it is not in the plan",
            id="overdue",
        ),
        pytest.param(
            assessed(1, "Sheet 3", "later"),
            "Due more than 8 weeks ahead, so not in the plan yet",
            id="later",
        ),
    ],
)
def test_each_task_says_what_the_plan_checked(backend, item, expected):
    at = my_plan(backend, plan=PLAN | {"all_fit": False, "tasks": [item]})

    assert expected in at.expander[0].label
    # Planning words only: nothing that reads as the work being done.
    assert "on track" not in text(at).lower()


def test_opening_a_task_shows_the_full_breakdown(backend):
    item = assessed(
        1, "Lab report", "shortfall", needed_hours=10, planned_hours=7.5,
        planned_hours_this_week=3, missing_hours=2.5,
    )  # fmt: skip
    at = my_plan(backend, plan=PLAN | {"tasks": [item]})
    inside = " ".join(c.value for c in at.expander[0].caption)

    assert "Study time needed: 10 hours" in inside
    assert "In the plan before the due date: 7.5 hours (this week: 3 hours)" in inside
    assert "Still missing: 2.5 hours" in inside
    assert "add free study time or update the hours it needs" in inside


def test_an_outdated_plan_has_one_update_button_next_to_the_note(backend):
    at = my_plan(backend, plan=PLAN | {"outdated": True})

    assert "The plan is out of date" in text(at)
    assert primary(at) == ["Update study plan"]  # in the note, not twice


@pytest.mark.parametrize(
    ("source", "reason", "expected"),
    [
        pytest.param("model", None, "The AI model arranged this week", id="model"),
        pytest.param("baseline", None, "calculated by the planning rules.", id="rules"),
        pytest.param(
            "baseline",
            "timeout",
            "calculated by the planning rules, because the AI model took too long.",
            id="fallback",
        ),
    ],
)
def test_who_built_the_plan_is_in_the_details(backend, source, reason, expected):
    at = my_plan(backend, plan=PLAN | {"source": source, "fallback_reason": reason})
    details = at.expander[-1]

    assert details.label.endswith("Details")
    assert expected in " ".join(c.value for c in details.caption)
    assert "planned study time, not work already done" in " ".join(
        c.value for c in details.caption
    )


def test_creating_a_plan_waits_long_enough_and_shows_it(backend):
    build = backend.post("/plan").mock(return_value=httpx.Response(200, json=PLAN))
    at = my_plan(backend, plan=None)
    backend.get("/plan").mock(return_value=httpx.Response(200, json=PLAN))

    at.button(key="build-plan").click().run()

    assert not at.exception
    assert build.calls.last.request.headers["Authorization"] == f"Bearer {TOKEN}"
    timeout = build.calls.last.request.extensions["timeout"]
    assert timeout["read"] == PLAN_TIMEOUT.read == 100.0  # outlasts the backend's tries
    assert at.success[0].value == "Your study plan is ready."
    assert "Sheet 3" in week(at)


@pytest.mark.parametrize(
    ("status", "detail", "expected", "technical"),
    [
        pytest.param(
            503,
            "AI service unavailable",
            "Couldn't create a new plan right now. Your previous plan is kept. "
            "Try again in a few minutes.",
            "The AI service did not answer (503).",
            id="ai-down-503",
        ),
        pytest.param(
            502,
            "AI service returned invalid output",
            "Couldn't use the new plan. Your previous plan is kept.",
            "The AI service's answer failed the backend's checks (502).",
            id="bad-answer-502",
        ),
    ],
)
def test_a_failed_update_keeps_the_saved_plan(
    backend, status, detail, expected, technical
):
    backend.post("/plan").mock(
        return_value=httpx.Response(status, json={"detail": detail})
    )
    at = my_plan(backend)

    at.button(key="build-plan").click().run()

    assert not at.exception
    assert at.error[0].value == expected
    tech = next(e for e in at.expander if e.label == "Technical details")
    assert tech.caption[0].value == technical  # details only on demand
    assert "Sheet 3" in week(at)  # the saved plan is still shown


def test_backend_down_on_the_plan_page_shows_the_next_step(backend):
    backend.get("/courses").mock(return_value=httpx.Response(200, json=[]))
    backend.get("/tasks").mock(return_value=httpx.Response(200, json=[]))
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["token"] = TOKEN
    at.session_state["email"] = "student@example.com"
    at.run()
    backend.get("/constraints").mock(side_effect=httpx.ConnectError("refused"))

    at.button_group(key="page").set_value("plan").run()

    assert not at.exception
    assert "Cannot reach the backend" in at.error[0].value


def test_free_time_is_saved_as_the_backend_expects(backend):
    save = backend.put("/constraints").mock(
        return_value=httpx.Response(200, json=SAVED)
    )
    blocked = TODAY + timedelta(days=3)
    at = my_plan(backend, plan=None)
    at.button(key="edit-hours").click().run()

    at.number_input(key="hours-sunday").set_value(2.5)
    at.number_input(key="hours-wednesday").set_value(4.0)
    at.multiselect(key="hours-blocked").select(blocked)
    at.text_area(key="hours-note").input("Keep Thursday light")
    at.button(key="hours-submit").click().run()

    assert not at.exception
    assert json.loads(save.calls.last.request.content) == {
        "weekly_hours": WEEKLY | {"sunday": 2.5, "wednesday": 4.0},
        "blocked_dates": [blocked.isoformat()],
        "note": "Keep Thursday light",
    }
    assert at.success[0].value == "Saved your free study time."


def test_invalid_hours_are_shown_in_words(backend):
    detail = [
        {
            "loc": ["body", "weekly_hours", "monday"],
            "msg": "Input should be a multiple of 0.5",
        }
    ]
    backend.put("/constraints").mock(
        return_value=httpx.Response(422, json={"detail": detail})
    )
    at = my_plan(backend, plan=None)
    at.button(key="edit-hours").click().run()
    at.button(key="hours-submit").click().run()

    assert at.error[0].value == "Please fix: monday: Input should be a multiple of 0.5"


def test_the_plan_page_in_hebrew(backend):
    backend.post("/plan").mock(
        return_value=httpx.Response(503, json={"detail": "AI service unavailable"})
    )
    backend.patch("/auth/me").mock(
        return_value=httpx.Response(
            200, json={"id": 1, "email": "s@e.com", "language": "he"}
        )
    )
    short = assessed(
        1, "Sheet 3", "shortfall", needed_hours=10, planned_hours=7.5,
        missing_hours=2.5,
    )  # fmt: skip
    at = my_plan(backend, plan=PLAN | {"tasks": [short]})
    at.button_group(key="lang-picker").set_value("he").run()

    assert at.button_group(key="page").options == [
        "תוכנית לימוד שבועית",
        "מטלות ומבחנים",
    ]
    assert primary(at) == ["עדכון תוכנית הלימוד"]
    assert at.button(key="edit-hours").label == "זמן פנוי ללימודים"
    assert "חסרות בתוכנית עוד שעתיים וחצי לפני ההגשה" in at.expander[0].label
    assert "זמן פנוי: שעתיים" in week(at)
    # Bold that ends right before the separator's direction mark would not close
    # after a Hebrew date (it ends in ׳), and the ** would show on screen.
    assert not any("**\u200f" in e.label for e in at.expander)
    at.button(key="build-plan").click().run()
    assert at.error[0].value.startswith("לא הצלחנו ליצור תוכנית חדשה כרגע")


@pytest.mark.parametrize(
    ("hours", "words"),
    [(0.5, "חצי שעה"), (1, "שעה"), (1.5, "שעה וחצי"), (2, "שעתיים"), (3, "3 שעות")],
)
def test_hebrew_durations_read_naturally(hours, words):
    import streamlit as st

    from texts import duration

    st.session_state["lang"] = "he"
    try:
        assert duration(hours) == words
    finally:
        st.session_state.pop("lang", None)

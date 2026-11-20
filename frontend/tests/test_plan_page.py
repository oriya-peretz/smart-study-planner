"""The My plan page, with the backend faked by respx (see test_app.py)."""

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
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [box.value for box in (*at.info, *at.warning, *at.success, *at.error)]
    return "\n".join(parts)


def test_before_any_hours_the_page_asks_for_them_and_cannot_build(backend):
    build = backend.post("/plan")
    at = my_plan(backend, constraints=UNSAVED, plan=None)

    assert not at.exception
    assert "set how many hours you can study" in at.info[0].value
    assert at.button(key="build-plan").disabled
    assert not build.called


def test_with_hours_but_no_plan_yet(backend):
    at = my_plan(backend, plan=None)

    assert "No plan yet" in at.info[0].value
    assert at.button(key="build-plan").label == "Build my plan"
    assert not at.button(key="build-plan").disabled


def test_the_plan_shows_the_week_and_each_task(backend):
    at = my_plan(backend)
    page = text(at)

    assert "The AI model arranged this week" in page
    assert "Everything fits before its due date." in page
    assert "2 of 2 free hours planned" in page
    assert "Sheet 3  ·  Automata  ·  2 h" in page
    assert "No study time" in page  # the days with no free hours
    assert "On track: 3 of 3 h planned" in page
    assert "Hours are estimates" in page
    assert at.button(key="build-plan").label == "Rebuild plan"


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        pytest.param(
            assessed(1, "Sheet 3", "shortfall", missing_hours=1.5),
            "Short by 1.5 h before its due date",
            id="shortfall",
        ),
        pytest.param(
            assessed(1, "Sheet 3", "no_estimate", needed_hours=None),
            "No estimate: add the hours it needs to plan it",
            id="no-estimate",
        ),
        pytest.param(
            assessed(1, "Sheet 3", "overdue"), "Its due date has passed", id="overdue"
        ),
        pytest.param(
            assessed(1, "Sheet 3", "later"), "Due after the next 8 weeks", id="later"
        ),
    ],
)
def test_each_assessment_is_said_in_words(backend, item, expected):
    at = my_plan(backend, plan=PLAN | {"all_fit": False, "tasks": [item]})

    assert expected in text(at)
    assert "Everything fits" not in text(at)


def test_an_outdated_plan_says_why_to_rebuild(backend):
    at = my_plan(backend, plan=PLAN | {"outdated": True})

    assert "changed since this plan was made" in at.warning[0].value


@pytest.mark.parametrize(
    ("source", "reason", "expected"),
    [
        pytest.param("baseline", None, "Built by the planner rules.", id="rules"),
        pytest.param(
            "baseline",
            "timeout",
            "Built by the planner rules, because the AI model took too long.",
            id="fallback",
        ),
    ],
)
def test_the_page_says_who_built_the_plan(backend, source, reason, expected):
    at = my_plan(backend, plan=PLAN | {"source": source, "fallback_reason": reason})

    assert expected in text(at)


def test_building_a_plan_waits_long_enough_and_shows_it(backend):
    build = backend.post("/plan").mock(return_value=httpx.Response(200, json=PLAN))
    at = my_plan(backend, plan=None)
    backend.get("/plan").mock(return_value=httpx.Response(200, json=PLAN))

    at.button(key="build-plan").click().run()

    assert not at.exception
    assert build.calls.last.request.headers["Authorization"] == f"Bearer {TOKEN}"
    timeout = build.calls.last.request.extensions["timeout"]
    assert timeout["read"] == PLAN_TIMEOUT.read == 100.0  # outlasts the backend's tries
    assert at.success[0].value == "Your plan is ready."
    assert "Sheet 3  ·  Automata  ·  2 h" in text(at)


@pytest.mark.parametrize(
    ("status", "detail", "expected"),
    [
        pytest.param(
            503,
            "AI service unavailable",
            "The planning service is not available right now. "
            "Your saved plan is unchanged; try again in a minute.",
            id="ai-down-503",
        ),
        pytest.param(
            502,
            "AI service returned invalid output",
            "The planning service gave an answer that could not be used. "
            "Your saved plan is unchanged.",
            id="bad-answer-502",
        ),
    ],
)
def test_a_failed_build_keeps_the_saved_plan(backend, status, detail, expected):
    backend.post("/plan").mock(
        return_value=httpx.Response(status, json={"detail": detail})
    )
    at = my_plan(backend)

    at.button(key="build-plan").click().run()

    assert not at.exception
    assert at.error[0].value == expected
    assert "Sheet 3  ·  Automata  ·  2 h" in text(at)  # the saved plan is still shown


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


def test_study_hours_are_saved_as_the_backend_expects(backend):
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
    assert at.success[0].value == "Saved your study hours."


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
    at = my_plan(backend)
    at.button_group(key="lang-picker").set_value("he").run()

    assert at.button_group(key="page").options == ["התוכנית שלי", "משימות"]
    assert at.button(key="build-plan").label == "בנייה מחדש"
    assert "מודל ה-AI סידר את השבוע" in text(at)
    # Bold that ends right before the separator's direction mark would not close
    # after a Hebrew date (it ends in ׳), and the ** would show on screen.
    lines = [m.value for m in at.markdown if m.value.startswith("**")]
    assert lines and not any("**\u200f" in line for line in lines)
    at.button(key="build-plan").click().run()
    assert at.error[0].value.startswith("שירות התכנון לא זמין כרגע")

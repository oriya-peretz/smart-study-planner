"""Constraints and the study plan, with the AI service faked by httpx.MockTransport."""

import json
from collections.abc import Callable
from datetime import date, timedelta

import httpx
import pytest

from app.ai_client import TIMEOUT, AIClient, get_ai_client
from app.main import app
from app.planning import get_today

SUNDAY = date(2026, 11, 1)
HOURS = {"sunday": 2, "monday": 2, "tuesday": 2, "wednesday": 3, "thursday": 0}
LIMITS = {
    "weekly_hours": HOURS,
    "blocked_dates": ["2026-11-03"],
    "note": "Keep Thursday light",
}


@pytest.fixture(autouse=True)
def today():
    """The plan's first day is a fixed Sunday; set_today(...) moves it."""
    app.dependency_overrides[get_today] = lambda: SUNDAY

    def set_today(day: date) -> None:
        app.dependency_overrides[get_today] = lambda: day

    return set_today


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    # tenacity waits between attempts; make it instant in tests.
    monkeypatch.setattr(AIClient._post_plan.retry, "sleep", lambda seconds: None)


@pytest.fixture
def fake_ai():
    """fake_ai(handler) routes the backend's AI service calls to handler(request)."""
    calls: list[httpx.Request] = []

    def install(handler):
        def recording(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return handler(request)

        ai = AIClient("http://ai-service", transport=httpx.MockTransport(recording))
        app.dependency_overrides[get_ai_client] = lambda: ai
        return calls

    return install


def answer_for(sent: dict) -> dict:
    """A valid answer to a request: 1 h for the first task on the first free day."""
    start = date.fromisoformat(sent["start_date"])
    weekly = sent["constraints"]["weekly_hours"]
    blocked = sent["constraints"]["blocked_dates"]
    names = ("monday", "tuesday", "wednesday", "thursday", "friday")
    days = []
    for i in range(7):
        day = start + timedelta(days=i)
        name = (*names, "saturday", "sunday")[day.weekday()]
        free = 0 if day.isoformat() in blocked else weekly[name]
        days.append(
            {
                "date": day.isoformat(),
                "free_hours": free,
                "planned_hours": 0,
                "blocks": [],
            }
        )
    tasks = sent["tasks"]
    if tasks and days[0]["free_hours"] >= 1:
        days[0]["blocks"] = [{"task_id": tasks[0]["id"], "hours": 1}]
        days[0]["planned_hours"] = 1
    return {
        "start_date": sent["start_date"],
        "horizon_end": (start + timedelta(days=55)).isoformat(),
        "source": "model",
        "fallback_reason": None,
        "all_fit": True,
        "days": days,
        "tasks": [
            {
                "task_id": task["id"],
                "assessment": "on_track",
                "needed_hours": task["estimated_hours"],
                "free_hours_before_due": 10,
                "slack_hours": 5,
                "planned_hours": task["estimated_hours"] or 0,
                "planned_hours_this_week": 1,
                "missing_hours": 0,
            }
            for task in tasks
        ],
    }


def good(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=answer_for(json.loads(request.content)))


def changed(edit) -> Callable[[httpx.Request], httpx.Response]:
    """An AI service that answers validly, after edit(answer) changes the answer."""

    def handler(request: httpx.Request) -> httpx.Response:
        answer = answer_for(json.loads(request.content))
        edit(answer)
        return httpx.Response(200, json=answer)

    return handler


def add_course(client, name="Algorithms") -> int:
    return client.post("/courses", json={"name": name}).json()["id"]


def add_task(client, course_id, **fields) -> dict:
    body = {
        "title": "Sheet 3",
        "course_id": course_id,
        "type": "homework",
        "due_at": "2026-11-05T23:59:00",
        "estimated_hours": 3,
    } | fields
    response = client.post("/tasks", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def ready(client):
    """A user with constraints and one task, ready to ask for a plan."""
    assert client.put("/constraints", json=LIMITS).status_code == 200
    course = add_course(client)
    add_task(client, course)
    return client


# ---- Constraints ----


def test_constraints_start_empty_and_unsaved(client):
    response = client.get("/constraints")

    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is False
    assert set(body["weekly_hours"].values()) == {0}
    assert body["blocked_dates"] == []


def test_constraints_are_saved_tidied_and_private(client, make_client):
    limits = LIMITS | {
        "blocked_dates": ["2026-12-25", "2026-11-03", "2026-12-25"],
        "note": "  Keep Thursday light  ",
    }
    assert client.put("/constraints", json=limits).status_code == 200

    body = client.get("/constraints").json()
    assert body["saved"] is True
    assert body["weekly_hours"]["wednesday"] == 3
    assert body["weekly_hours"]["friday"] == 0  # left out, so the default
    assert body["blocked_dates"] == ["2026-11-03", "2026-12-25"]
    assert body["note"] == "Keep Thursday light"
    assert make_client("other@example.com").get("/constraints").json()["saved"] is False


@pytest.mark.parametrize(
    "limits",
    [
        pytest.param(LIMITS | {"weekly_hours": {"monday": 0.3}}, id="not-half-hours"),
        pytest.param(LIMITS | {"weekly_hours": {"monday": 16.5}}, id="over-16"),
        pytest.param(LIMITS | {"weekly_hours": {"funday": 1}}, id="unknown-day"),
        pytest.param(LIMITS | {"note": "x" * 501}, id="note-too-long"),
        pytest.param(LIMITS | {"blocked_dates": ["soon"]}, id="not-a-date"),
        pytest.param({"note": "no hours"}, id="no-weekly-hours"),
    ],
)
def test_invalid_constraints_are_422(client, limits):
    assert client.put("/constraints", json=limits).status_code == 422


def test_constraints_need_a_login(anon):
    assert anon.get("/constraints").status_code == 401
    assert anon.put("/constraints", json=LIMITS).status_code == 401


# ---- Making a plan ----


def test_a_plan_is_built_from_unfinished_tasks_and_saved(ready, fake_ai):
    course = ready.get("/courses").json()[0]["id"]
    add_task(ready, course, title="Done already", status="done")
    add_task(ready, course, title="Old exam", type="exam", due_at="2026-10-01T09:00")
    calls = fake_ai(good)

    response = ready.post("/plan")

    assert response.status_code == 200, response.text
    [sent] = calls
    assert (sent.method, sent.url.path) == ("POST", "/plan")
    body = json.loads(sent.content)
    assert body["start_date"] == "2026-11-01"
    assert body["constraints"] == {
        "weekly_hours": HOURS | {"friday": 0, "saturday": 0},
        "blocked_dates": ["2026-11-03"],
    }
    assert body["note"] == "Keep Thursday light"
    assert [task["title"] for task in body["tasks"]] == ["Sheet 3"]  # unfinished only
    assert body["tasks"][0]["course"] == "Algorithms"
    plan = response.json()
    assert plan["outdated"] is False
    assert plan["days"][0]["blocks"] == [
        {
            "task_id": body["tasks"][0]["id"],
            "title": "Sheet 3",
            "course": "Algorithms",
            "hours": 1,
        }
    ]
    assert plan["tasks"][0]["title"] == "Sheet 3"
    assert ready.get("/plan").json() == plan  # really stored


def test_no_plan_yet_is_404(client):
    response = client.get("/plan")

    assert response.status_code == 404
    assert response.json() == {"detail": "No plan yet"}


def test_a_plan_needs_constraints_first(client, fake_ai):
    calls = fake_ai(good)

    response = client.post("/plan")

    assert response.status_code == 409
    assert response.json() == {"detail": "Set your free study hours first."}
    assert calls == []  # rejected before any AI call


def test_plans_are_private(ready, fake_ai, make_client, anon):
    fake_ai(good)
    assert ready.post("/plan").status_code == 200

    assert make_client("other@example.com").get("/plan").status_code == 404
    assert anon.get("/plan").status_code == 401
    assert anon.post("/plan").status_code == 401


# ---- Outdated plans ----


def test_a_fresh_plan_is_not_outdated_and_reading_it_calls_no_ai(ready, fake_ai):
    calls = fake_ai(good)
    ready.post("/plan")

    assert ready.get("/plan").json()["outdated"] is False
    assert len(calls) == 1  # GET /plan never calls the AI service


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda c: add_task(c, c.get("/courses").json()[0]["id"], title="New"),
            id="new-task",
        ),
        pytest.param(
            lambda c: c.patch(
                f"/tasks/{c.get('/tasks').json()[0]['id']}", json={"estimated_hours": 5}
            ),
            id="edited-task",
        ),
        pytest.param(
            lambda c: c.patch(
                f"/tasks/{c.get('/tasks').json()[0]['id']}", json={"status": "done"}
            ),
            id="finished-task",
        ),
        pytest.param(
            lambda c: c.put("/constraints", json=LIMITS | {"note": "Mornings"}),
            id="new-note",
        ),
        pytest.param(
            lambda c: c.put("/constraints", json=LIMITS | {"blocked_dates": []}),
            id="new-blocked-dates",
        ),
    ],
)
def test_a_change_makes_the_plan_outdated(ready, fake_ai, change):
    fake_ai(good)
    ready.post("/plan")

    change(ready)

    assert ready.get("/plan").json()["outdated"] is True


def test_a_plan_is_outdated_once_its_first_day_passes(ready, fake_ai, today):
    fake_ai(good)
    ready.post("/plan")

    today(SUNDAY + timedelta(days=1))

    assert ready.get("/plan").json()["outdated"] is True


# ---- When the AI service fails ----


def refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def slow(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("model took too long", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        pytest.param(refuse, id="refused"),
        pytest.param(slow, id="read-timeout"),
        pytest.param(lambda request: httpx.Response(503), id="busy-503"),
        pytest.param(lambda request: httpx.Response(504), id="gateway-timeout-504"),
    ],
)
def test_transient_failures_are_retried_three_times_then_503(ready, fake_ai, handler):
    calls = fake_ai(handler)

    response = ready.post("/plan")

    assert response.status_code == 503
    assert response.json() == {"detail": "AI service unavailable"}
    assert len(calls) == 3  # bounded: one try and two retries
    assert ready.get("/plan").status_code == 404  # nothing half-saved


def test_a_retry_that_succeeds_saves_the_plan(ready, fake_ai):
    answers = iter([httpx.Response(503), None])

    def busy_then_good(request):
        return next(answers) or good(request)

    calls = fake_ai(busy_then_good)

    assert ready.post("/plan").status_code == 200
    assert len(calls) == 2


DETAIL = {502: "AI service returned invalid output", 503: "AI service unavailable"}


@pytest.mark.parametrize(
    ("ai_status", "expected"),
    [
        pytest.param(500, 503, id="crash-500"),  # fail fast: a retry rarely helps
        pytest.param(422, 502, id="our-bug-422"),  # we broke the contract
        pytest.param(404, 502, id="wrong-service-404"),
    ],
)
def test_other_errors_are_not_retried(ready, fake_ai, ai_status, expected):
    calls = fake_ai(lambda request: httpx.Response(ai_status))

    response = ready.post("/plan")

    assert response.status_code == expected
    assert response.json() == {"detail": DETAIL[expected]}
    assert len(calls) == 1


def overbook_sunday(answer):
    # Sunday has 2 free hours; give the task 3.
    task = answer["tasks"][0]["task_id"]
    answer["days"][0] |= {"planned_hours": 3, "blocks": [{"task_id": task, "hours": 3}]}


def zero_hour_block(answer):
    task = answer["tasks"][0]["task_id"]
    answer["days"][0] |= {"planned_hours": 0, "blocks": [{"task_id": task, "hours": 0}]}


def set_day(index: int, **fields):
    def edit(answer):
        answer["days"][index] |= fields

    return edit


@pytest.mark.parametrize(
    "handler",
    [
        pytest.param(
            lambda request: httpx.Response(200, json={"plan": "study hard"}),
            id="broken-contract",
        ),
        pytest.param(
            lambda request: httpx.Response(200, content=b"<html>oops</html>"),
            id="not-json",
        ),
        pytest.param(
            changed(lambda a: a.update(start_date="2026-11-02")), id="wrong-start"
        ),
        pytest.param(changed(lambda a: a["days"].pop()), id="six-days"),
        pytest.param(changed(set_day(0, free_hours=8)), id="free-hours-not-the-users"),
        pytest.param(changed(overbook_sunday), id="overbooked-day"),
        pytest.param(changed(zero_hour_block), id="block-without-hours"),
        pytest.param(
            changed(set_day(0, blocks=[{"task_id": 999, "hours": 1}])),
            id="task-not-sent",
        ),
        pytest.param(changed(set_day(0, planned_hours=2)), id="hours-do-not-add-up"),
        pytest.param(changed(lambda a: a["tasks"].clear()), id="task-not-assessed"),
        pytest.param(
            changed(lambda a: a["tasks"].append(a["tasks"][0])), id="task-twice"
        ),
    ],
)
def test_an_answer_the_backend_cannot_accept_is_502(ready, fake_ai, handler):
    calls = fake_ai(handler)

    response = ready.post("/plan")

    assert response.status_code == 502
    assert response.json() == {"detail": "AI service returned invalid output"}
    assert len(calls) == 1  # its output is wrong; asking again would not help
    assert ready.get("/plan").status_code == 404


def test_a_block_on_the_due_day_is_502(client, fake_ai):
    # Due Wednesday 4 Nov, which has 3 free hours; Tuesday is its last day.
    client.put("/constraints", json=LIMITS)
    add_task(client, add_course(client), due_at="2026-11-04T23:59:00")

    def wednesday_block(answer):
        task = answer["tasks"][0]["task_id"]
        answer["days"][3] |= {
            "planned_hours": 1,
            "blocks": [{"task_id": task, "hours": 1}],
        }

    fake_ai(changed(wednesday_block))

    assert client.post("/plan").status_code == 502
    fake_ai(changed(lambda answer: None))
    assert client.post("/plan").status_code == 200  # the same plan, without it


def test_a_failure_keeps_the_previous_plan(ready, fake_ai):
    fake_ai(good)
    before = ready.post("/plan").json()

    fake_ai(refuse)
    assert ready.post("/plan").status_code == 503

    assert ready.get("/plan").json() == before


def test_timeouts_are_explicit():
    phases = (TIMEOUT.connect, TIMEOUT.read, TIMEOUT.write, TIMEOUT.pool)
    assert phases == (2.0, 30.0, 5.0, 2.0)
    ai = AIClient()
    assert ai._http.timeout == TIMEOUT
    ai.close()

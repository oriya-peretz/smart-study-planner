import pytest

from tests.factories import body, task


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_plan(client):
    response = client.post("/plan", json=body([task(1, "2026-11-04", 3)]))

    assert response.status_code == 200
    plan = response.json()
    assert plan["source"] == "baseline"
    assert plan["start_date"] == "2026-11-01"
    assert len(plan["days"]) == 7
    assert plan["days"][0]["blocks"] == [{"task_id": 1, "hours": 2.0}]
    assert plan["tasks"][0]["assessment"] == "on_track"


def with_hours(hours) -> dict:
    request = body([])
    request["constraints"]["weekly_hours"]["monday"] = hours
    return request


def with_task(**fields) -> dict:
    return body([task(1, "2026-11-04", 3) | fields])


@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param(with_hours(0.3), id="not-whole-half-hours"),
        pytest.param(with_hours(16.5), id="more-than-16-hours"),
        pytest.param(with_hours(-1), id="negative-hours"),
        pytest.param(with_task(estimated_hours=0), id="zero-estimate"),
        pytest.param(with_task(title="   "), id="blank-title"),
        pytest.param(with_task(type="lecture"), id="unknown-type"),
        pytest.param(with_task(due_at="2026-11-04T09:00+02:00"), id="time-zone"),
        pytest.param(with_task(priority=1), id="unknown-task-field"),
        pytest.param(body([]) | {"note": "x"}, id="unknown-field"),
        pytest.param(
            body([task(1, "2026-11-04", 3), task(1, "2026-11-05", 1)]),
            id="duplicate-ids",
        ),
        pytest.param({"start_date": "2026-11-01", "tasks": []}, id="no-constraints"),
    ],
)
def test_invalid_requests_are_422(client, request_body):
    assert client.post("/plan", json=request_body).status_code == 422

"""Requests and tasks for the tests, as the backend would send them."""

from datetime import date, datetime

from app.schemas import WEEKDAYS, PlanRequest

SUNDAY = date(2026, 11, 1)  # a fixed start, so no test depends on today


def task(id: int, due: str, hours: float | None, **fields) -> dict:
    """`due` is a date (the task is due at 23:59) or a full date and time."""
    due_at = datetime.fromisoformat(due if "T" in due else f"{due}T23:59")
    return {
        "id": id,
        "title": f"Task {id}",
        "course": "EASS",
        "type": "homework",
        "due_at": due_at.isoformat(),
        "estimated_hours": hours,
        **fields,
    }


def body(tasks: list[dict], every_day: float = 2, **constraints) -> dict:
    """A request starting on SUNDAY, with the same free hours every day."""
    return {
        "start_date": SUNDAY.isoformat(),
        "constraints": {
            "weekly_hours": dict.fromkeys(WEEKDAYS, every_day),
            **constraints,
        },
        "tasks": tasks,
    }


def request(tasks: list[dict], every_day: float = 2, **constraints) -> PlanRequest:
    return PlanRequest.model_validate(body(tasks, every_day, **constraints))

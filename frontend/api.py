"""Every HTTP call to the backend lives here. The UI never sees httpx."""

import os
from typing import Any, TypedDict

import httpx

# 127.0.0.1, not localhost: on Windows, localhost tries IPv6 first and waits ~2 s per request.
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
TIMEOUT = httpx.Timeout(10.0, connect=2.0)
NOT_SENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.UnsupportedProtocol)


class Task(TypedDict):
    """One task as the backend returns it (TaskPublic)."""

    id: int
    title: str
    course: str
    type: str
    due_at: str
    estimated_hours: float | None
    status: str | None
    link: str | None
    location: str | None
    notes: str | None


class CourseTasks(TypedDict):
    course: str
    tasks: list[Task]


class BackendError(Exception):
    """Something went wrong; str(error) is a message you can show to a user."""


class BackendUnavailable(BackendError):
    """Nothing reached the backend (refused, DNS, connect timeout): safe to retry."""


class BackendNoAnswer(BackendError):
    """The request was sent but no full reply came back in time: outcome unknown."""


def _friendly(response: httpx.Response) -> str:
    match response.status_code:
        case 422:
            problems = []
            for err in response.json()["detail"]:
                field = err["loc"][-1] if len(err["loc"]) > 1 else ""
                message = err["msg"].removeprefix("Value error, ")
                problems.append(f"{field}: {message}" if field else message)
            return "Please fix: " + "; ".join(problems)
        case 404:
            return "That task no longer exists. Reload the page."
        case code:
            return f"The backend failed ({code}). Check its logs."


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    try:
        response = httpx.request(method, f"{BACKEND_URL}{path}", **kwargs)
    except NOT_SENT as exc:
        raise BackendUnavailable(
            f"Cannot reach the backend at {BACKEND_URL}. "
            "Start it (uv run fastapi dev in backend/) and reload the page."
        ) from exc
    except httpx.TransportError as exc:  # sent, but no complete reply
        if method == "GET":
            raise BackendNoAnswer(
                "The backend took too long to answer. Reload the page to try again."
            ) from exc
        raise BackendNoAnswer(
            "The backend did not answer in time. Your change may have been saved. "
            "Reload the page and check before trying again."
        ) from exc
    if response.is_error:
        raise BackendError(_friendly(response))
    return response


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:  # not JSON, e.g. an HTML page from another server
        raise BackendError(
            f"The service at {BACKEND_URL} did not answer like the Smart Study Planner API. "
            "Check BACKEND_URL."
        ) from exc


def list_tasks(include_done: bool = True) -> list[Task]:
    return _json(_request("GET", "/tasks", params={"include_done": include_done}))


def list_tasks_by_course(include_done: bool = True) -> list[CourseTasks]:
    return _json(
        _request("GET", "/tasks/by-course", params={"include_done": include_done})
    )


def create_task(task: dict) -> Task:
    return _json(_request("POST", "/tasks", json=task))


def update_task(task_id: int, changes: dict) -> Task:
    return _json(_request("PATCH", f"/tasks/{task_id}", json=changes))


def delete_task(task_id: int) -> None:
    _request("DELETE", f"/tasks/{task_id}")

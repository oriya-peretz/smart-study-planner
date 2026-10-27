from fastapi.testclient import TestClient

from app import db
from app.main import app
from tests.conftest import log_in


def test_tasks_survive_a_restart(tmp_path, monkeypatch):
    # A real SQLite file in a temporary folder, instead of data/app.db.
    monkeypatch.setattr(db, "engine", db.make_engine(f"sqlite:///{tmp_path / 'test.db'}"))
    with TestClient(app) as client:  # `with` runs the lifespan: tables are created
        log_in(client, "student@example.com")
        course = client.post("/courses", json={"name": "Automata"}).json()
        task = {"title": "Exercise 3", "course_id": course["id"], "type": "homework", "due_at": "2026-11-20T23:59:00"}
        created = client.post("/tasks", json=task).json()
        token = client.headers["Authorization"]

    with TestClient(app) as client:  # a fresh start on the same file
        client.headers["Authorization"] = token  # the session survives the restart too
        assert client.get(f"/tasks/{created['id']}").json() == created

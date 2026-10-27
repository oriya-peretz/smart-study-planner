import pytest

HOMEWORK = {
    "title": "Exercise 3",
    "type": "homework",
    "due_at": "2026-11-20T23:59:00",
}
EXAM = {
    "title": "Final exam",
    "type": "exam",
    "due_at": "2099-01-15T09:00:00",
    "location": "Building 2",
}


def add_course(client, name="Automata"):
    response = client.post("/courses", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def course_id(client):
    return add_course(client)


def create(client, **fields):
    fields.setdefault("course_id", 1)  # the course made by the course_id fixture
    response = client.post("/tasks", json=fields)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_returns_task_with_id_and_default_status(client, course_id):
    task = create(client, **HOMEWORK)
    assert task["id"] >= 1
    assert task["status"] == "todo"
    assert task["link"] is None
    assert client.get(f"/tasks/{task['id']}").json() == task


def test_create_exam_gets_status_from_date(client, course_id):
    assert create(client, **EXAM)["status"] == "todo"
    assert create(client, **{**EXAM, "due_at": "2020-01-15T09:00:00"})["status"] == "past"


def test_create_invalid_task_is_422_and_not_saved(client, course_id):
    response = client.post("/tasks", json={**EXAM, "link": "https://example.com"})
    assert response.status_code == 422
    assert client.get("/tasks").json() == []


def test_get_missing_task_is_404(client, course_id):
    assert client.get("/tasks/999").status_code == 404


def test_patch_changes_only_sent_fields(client, course_id):
    task = create(client, **HOMEWORK, notes="Question 2 is hard")
    response = client.patch(f"/tasks/{task['id']}", json={"status": "in_progress"})
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "in_progress"
    assert updated["notes"] == "Question 2 is hard"
    assert updated["title"] == task["title"]
    assert client.get(f"/tasks/{task['id']}").json() == updated


def test_patch_null_clears_optional_field(client, course_id):
    task = create(client, **HOMEWORK, link="https://github.com/me/ex3")
    updated = client.patch(f"/tasks/{task['id']}", json={"link": None}).json()
    assert updated["link"] is None


def test_patch_cannot_clear_required_field(client, course_id):
    task = create(client, **HOMEWORK)
    response = client.patch(f"/tasks/{task['id']}", json={"title": None})
    assert response.status_code == 422
    assert client.get(f"/tasks/{task['id']}").json()["title"] == "Exercise 3"


def test_patch_rejects_field_that_does_not_fit_stored_type(client, course_id):
    exam = create(client, **EXAM)
    response = client.patch(f"/tasks/{exam['id']}", json={"link": "https://example.com"})
    assert response.status_code == 422
    assert "an exam cannot have: link" in response.text


def test_patch_rejects_status_sent_for_an_exam(client, course_id):
    exam = create(client, **EXAM)
    response = client.patch(f"/tasks/{exam['id']}", json={"status": "done"})
    assert response.status_code == 422  # same answer as creating an exam with a status
    assert "an exam cannot have: status" in response.text
    assert client.get(f"/tasks/{exam['id']}").json()["status"] == "todo"


def test_patch_to_exam_with_a_status_is_rejected(client, course_id):
    task = create(client, **HOMEWORK)
    response = client.patch(
        f"/tasks/{task['id']}",
        json={"type": "exam", "due_at": "2099-02-01T09:00:00", "status": "in_progress"},
    )
    assert response.status_code == 422
    assert client.get(f"/tasks/{task['id']}").json()["type"] == "homework"  # unchanged


def test_patch_change_homework_to_exam(client, course_id):
    task = create(client, **HOMEWORK)
    response = client.patch(
        f"/tasks/{task['id']}", json={"type": "exam", "due_at": "2099-02-01T09:00:00"}
    )
    assert response.status_code == 200
    assert response.json()["type"] == "exam"
    assert response.json()["status"] == "todo"


def test_patch_missing_task_is_404(client, course_id):
    assert client.patch("/tasks/999", json={"title": "x"}).status_code == 404


def test_delete_removes_task(client, course_id):
    task = create(client, **HOMEWORK)
    assert client.delete(f"/tasks/{task['id']}").status_code == 204
    assert client.get(f"/tasks/{task['id']}").status_code == 404
    assert client.delete(f"/tasks/{task['id']}").status_code == 404


def test_list_is_ordered_by_urgency(client, course_id):
    later = create(client, **{**HOMEWORK, "title": "later", "due_at": "2026-12-01T10:00:00"})
    sooner = create(client, **{**HOMEWORK, "title": "sooner", "due_at": "2026-11-10T10:00:00"})
    done = create(client, **{**HOMEWORK, "title": "done", "due_at": "2026-11-01T10:00:00", "status": "done"})
    titles = [task["title"] for task in client.get("/tasks").json()]
    assert titles == ["sooner", "later", "done"]
    assert {later["id"], sooner["id"], done["id"]} == {t["id"] for t in client.get("/tasks").json()}
    create(client, **{**EXAM, "title": "past exam", "due_at": "2020-01-15T09:00:00"})
    open_titles = [task["title"] for task in client.get("/tasks?include_done=false").json()]
    assert open_titles == ["sooner", "later"]  # done tasks and past exams are hidden


def test_by_course_groups_and_orders(client, course_id):
    algorithms = add_course(client, "Algorithms")
    empty = add_course(client, "Empty course")
    create(client, **{**HOMEWORK, "title": "A later", "due_at": "2026-12-01T10:00:00"})
    create(client, **{**HOMEWORK, "course_id": algorithms, "title": "B soon", "due_at": "2026-11-05T10:00:00"})
    create(client, **{**HOMEWORK, "title": "A soon", "due_at": "2026-11-15T10:00:00"})
    groups = client.get("/tasks/by-course").json()
    assert [g["course"]["name"] for g in groups] == ["Algorithms", "Automata", "Empty course"]
    assert [t["title"] for t in groups[1]["tasks"]] == ["A soon", "A later"]
    assert groups[2] == {"course": {"id": empty, "name": "Empty course"}, "tasks": []}


def test_task_includes_its_course_name(client, course_id):
    task = create(client, **HOMEWORK)
    assert task["course"] == {"id": course_id, "name": "Automata"}


def test_create_task_in_missing_course_is_422(client, course_id):
    response = client.post("/tasks", json={**HOMEWORK, "course_id": 999})
    assert response.status_code == 422
    assert "no course with this id" in response.text


def test_patch_moves_task_to_another_course(client, course_id):
    task = create(client, **HOMEWORK)
    other = add_course(client, "Algorithms")
    moved = client.patch(f"/tasks/{task['id']}", json={"course_id": other}).json()
    assert moved["course"] == {"id": other, "name": "Algorithms"}
    assert client.patch(f"/tasks/{task['id']}", json={"course_id": 999}).status_code == 422

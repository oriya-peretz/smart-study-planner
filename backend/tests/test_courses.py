def add(client, name):
    return client.post("/courses", json={"name": name})


def test_create_and_list_courses_by_name(client):
    assert add(client, "Statistics").status_code == 201
    created = add(client, "  automata  ").json()
    assert created["name"] == "automata"  # spaces are trimmed
    assert [c["name"] for c in client.get("/courses").json()] == [
        "automata",
        "Statistics",
    ]


def test_duplicate_name_ignoring_case_is_409(client):
    add(client, "Automata")
    response = add(client, "AUTOMATA")
    assert response.status_code == 409
    assert len(client.get("/courses").json()) == 1


def test_empty_name_is_422(client):
    assert add(client, "   ").status_code == 422


def test_rename_course(client):
    course = add(client, "Automata").json()
    response = client.patch(
        f"/courses/{course['id']}", json={"name": "Automata and Formal Languages"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Automata and Formal Languages"


def test_rename_to_its_own_name_in_other_case_is_allowed(client):
    course = add(client, "automata").json()
    assert (
        client.patch(f"/courses/{course['id']}", json={"name": "Automata"}).status_code
        == 200
    )


def test_rename_to_another_courses_name_is_409(client):
    add(client, "Automata")
    other = add(client, "Statistics").json()
    assert (
        client.patch(f"/courses/{other['id']}", json={"name": "automata"}).status_code
        == 409
    )


def test_missing_course_is_404(client):
    assert client.patch("/courses/999", json={"name": "x"}).status_code == 404
    assert client.delete("/courses/999").status_code == 404


def test_delete_empty_course(client):
    course = add(client, "Automata").json()
    assert client.delete(f"/courses/{course['id']}").status_code == 204
    assert client.get("/courses").json() == []


def test_course_with_tasks_cannot_be_deleted(client):
    course = add(client, "Automata").json()
    task = {
        "title": "Ex 1",
        "course_id": course["id"],
        "type": "homework",
        "due_at": "2026-11-20T23:59",
    }
    assert client.post("/tasks", json=task).status_code == 201
    response = client.delete(f"/courses/{course['id']}")
    assert response.status_code == 409
    assert len(client.get("/courses").json()) == 1

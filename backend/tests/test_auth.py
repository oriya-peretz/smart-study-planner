from datetime import datetime, timedelta

from sqlmodel import select

from app.auth import check_password, hash_password
from app.models import AuthToken, User
from tests.conftest import PASSWORD

HOMEWORK = {"title": "Exercise 3", "type": "homework", "due_at": "2026-11-20T23:59"}


def credentials(email="new@example.com", password=PASSWORD):
    return {"email": email, "password": password}


# ---- Passwords ----


def test_password_hash_is_salted_and_checkable():
    first, second = hash_password("secret pass"), hash_password("secret pass")
    assert first != second  # a different random salt each time
    assert "secret pass" not in first
    assert check_password("secret pass", first)
    assert not check_password("wrong pass", first)


def test_password_is_never_stored(anon, session):
    anon.post("/auth/signup", json=credentials())
    user = session.exec(select(User)).one()
    assert PASSWORD not in user.password_hash


# ---- Sign up ----


def test_sign_up_returns_the_user_without_password(anon):
    response = anon.post("/auth/signup", json=credentials("New@Example.com"))
    assert response.status_code == 201
    # The email is stored in lower case; a new account starts in English.
    assert response.json() == {"id": 1, "email": "new@example.com", "language": "en"}


def test_email_is_taken_ignoring_case(anon):
    anon.post("/auth/signup", json=credentials("new@example.com"))
    response = anon.post("/auth/signup", json=credentials("NEW@example.com"))
    assert response.status_code == 409


def test_invalid_sign_up_is_422(anon):
    assert (
        anon.post("/auth/signup", json=credentials(email="not-an-email")).status_code
        == 422
    )
    assert (
        anon.post("/auth/signup", json=credentials(password="short")).status_code == 422
    )


# ---- Log in ----


def test_log_in_gives_a_working_token(anon):
    anon.post("/auth/signup", json=credentials())
    response = anon.post("/auth/login", json=credentials())
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = anon.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "new@example.com"


def test_wrong_password_and_unknown_email_look_the_same(anon):
    anon.post("/auth/signup", json=credentials())
    wrong_password = anon.post(
        "/auth/login", json=credentials(password="wrong password")
    )
    unknown_email = anon.post(
        "/auth/login", json=credentials(email="nobody@example.com")
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


# ---- Protected routes ----


def test_routes_need_a_token(anon):
    for path in ["/courses", "/tasks", "/tasks/by-course", "/auth/me"]:
        assert anon.get(path).status_code == 401, path
    assert anon.post("/courses", json={"name": "Automata"}).status_code == 401


def test_a_made_up_token_is_rejected(anon):
    assert (
        anon.get("/courses", headers={"Authorization": "Bearer made-up"}).status_code
        == 401
    )


def test_health_needs_no_token(anon):
    assert anon.get("/health").status_code == 200


def test_log_out_ends_the_session(client):
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/courses").status_code == 401


def test_expired_token_is_rejected(client, session):
    token = session.exec(select(AuthToken)).one()
    token.expires_at = datetime.now() - timedelta(minutes=1)
    session.add(token)
    session.commit()
    assert client.get("/courses").status_code == 401


# ---- One user cannot see or change another user's data ----


def test_users_see_only_their_own_data(make_client):
    alice, bob = make_client("alice@example.com"), make_client("bob@example.com")
    course = alice.post("/courses", json={"name": "Automata"}).json()
    task = alice.post("/tasks", json={**HOMEWORK, "course_id": course["id"]}).json()

    assert bob.get("/courses").json() == []
    assert bob.get("/tasks").json() == []
    assert bob.get("/tasks/by-course").json() == []
    assert len(alice.get("/tasks").json()) == 1

    # 404, not 403: a stranger cannot even tell that the id exists.
    assert bob.get(f"/tasks/{task['id']}").status_code == 404
    assert (
        bob.patch(f"/tasks/{task['id']}", json={"title": "Mine now"}).status_code == 404
    )
    assert bob.delete(f"/tasks/{task['id']}").status_code == 404
    assert (
        bob.patch(f"/courses/{course['id']}", json={"name": "Mine now"}).status_code
        == 404
    )
    assert bob.delete(f"/courses/{course['id']}").status_code == 404
    assert alice.get(f"/tasks/{task['id']}").json() == task  # untouched


def test_cannot_add_a_task_to_another_users_course(make_client):
    alice, bob = make_client("alice@example.com"), make_client("bob@example.com")
    course = alice.post("/courses", json={"name": "Automata"}).json()
    response = bob.post("/tasks", json={**HOMEWORK, "course_id": course["id"]})
    assert response.status_code == 422
    assert alice.get("/tasks").json() == []


def test_cannot_move_a_task_into_another_users_course(make_client):
    alice, bob = make_client("alice@example.com"), make_client("bob@example.com")
    alices_course = alice.post("/courses", json={"name": "Automata"}).json()
    bobs_course = bob.post("/courses", json={"name": "Statistics"}).json()
    task = bob.post("/tasks", json={**HOMEWORK, "course_id": bobs_course["id"]}).json()
    response = bob.patch(
        f"/tasks/{task['id']}", json={"course_id": alices_course["id"]}
    )
    assert response.status_code == 422


def test_two_users_may_have_courses_with_the_same_name(make_client):
    alice, bob = make_client("alice@example.com"), make_client("bob@example.com")
    assert alice.post("/courses", json={"name": "Automata"}).status_code == 201
    assert bob.post("/courses", json={"name": "Automata"}).status_code == 201


# ---- Language ----


def test_language_defaults_to_english(client):
    assert client.get("/auth/me").json()["language"] == "en"


def test_language_can_be_changed_and_is_kept(client):
    response = client.patch("/auth/me", json={"language": "he"})
    assert response.status_code == 200
    assert response.json()["language"] == "he"
    assert client.get("/auth/me").json()["language"] == "he"


def test_unknown_language_or_other_fields_are_rejected(client):
    assert client.patch("/auth/me", json={"language": "fr"}).status_code == 422
    assert client.patch("/auth/me", json={"email": "x@example.com"}).status_code == 422


def test_changing_language_needs_a_token(anon):
    assert anon.patch("/auth/me", json={"language": "he"}).status_code == 401


def test_each_user_has_their_own_language(make_client):
    alice, bob = make_client("alice@example.com"), make_client("bob@example.com")
    alice.patch("/auth/me", json={"language": "he"})
    assert bob.get("/auth/me").json()["language"] == "en"

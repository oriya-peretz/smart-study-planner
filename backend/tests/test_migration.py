"""An older database, made before users had a language, keeps working and keeps its data."""

import sqlite3
from contextlib import closing

from fastapi.testclient import TestClient

from app import db
from app.main import app
from tests.conftest import PASSWORD


def test_old_database_gains_the_language_column(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    # The user table exactly as it was before the language column existed.
    # closing(): sqlite3's own `with` commits but does not close the connection.
    with closing(sqlite3.connect(path)) as old, old:
        old.execute(
            'CREATE TABLE "user" (id INTEGER PRIMARY KEY, email VARCHAR NOT NULL UNIQUE,'
            " password_hash VARCHAR NOT NULL)"
        )
        old.execute(
            "INSERT INTO \"user\" (email, password_hash) VALUES ('kept@example.com', 'x$y')"
        )
    monkeypatch.setattr(db, "engine", db.make_engine(f"sqlite:///{path}"))

    with TestClient(app) as client:  # the lifespan runs create_db_and_tables
        credentials = {"email": "new@example.com", "password": PASSWORD}
        assert client.post("/auth/signup", json=credentials).status_code == 201
        token = client.post("/auth/login", json=credentials).json()["access_token"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["language"] == "en"

    with closing(sqlite3.connect(path)) as conn:
        columns = [row[1] for row in conn.execute('PRAGMA table_info("user")')]
        kept = conn.execute(
            "SELECT language FROM \"user\" WHERE email = 'kept@example.com'"
        ).fetchone()
    assert columns.count("language") == 1
    assert kept == ("en",)  # the existing user is kept and gets the default


def test_starting_twice_does_not_add_the_column_again(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db, "engine", db.make_engine(f"sqlite:///{tmp_path / 'new.db'}")
    )
    db.create_db_and_tables()
    db.create_db_and_tables()  # a restart must not fail with "duplicate column"
    db.engine.dispose()

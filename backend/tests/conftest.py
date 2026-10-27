from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app

PASSWORD = "correct horse battery"


@pytest.fixture
def session() -> Iterator[Session]:
    # One in-memory database per test. StaticPool keeps a single connection,
    # otherwise every connection would see its own empty database.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def log_in(client: TestClient, email: str) -> TestClient:
    """Sign up, log in, and send the token with every later request of this client."""
    assert client.post("/auth/signup", json={"email": email, "password": PASSWORD}).status_code == 201
    token = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
def make_client(session: Session) -> Iterator[Callable[..., TestClient]]:
    """make_client() is a stranger; make_client("a@b.com") is a logged-in user."""
    app.dependency_overrides[get_session] = lambda: session

    def make(email: str | None = None) -> TestClient:
        client = TestClient(app)  # without `with`, the lifespan (and the real file) is never used
        return log_in(client, email) if email else client

    yield make
    app.dependency_overrides.clear()


@pytest.fixture
def client(make_client) -> TestClient:
    """A logged-in student; most tests need nothing more."""
    return make_client("student@example.com")


@pytest.fixture
def anon(make_client) -> TestClient:
    """A visitor who has not logged in."""
    return make_client()

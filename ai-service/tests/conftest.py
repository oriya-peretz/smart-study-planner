import pytest
from fastapi.testclient import TestClient
from pydantic_ai import models

from app.main import app

# Safety net: a real model call anywhere in the tests raises instead of costing money.
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

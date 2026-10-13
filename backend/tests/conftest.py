import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """A test client that does not require a running database."""
    return TestClient(app)

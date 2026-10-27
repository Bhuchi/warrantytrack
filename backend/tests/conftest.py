import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import engine
from app.main import app


@pytest.fixture
def client() -> TestClient:
    """A test client that does not require a running database."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """A session whose writes are thrown away when the test ends.

    Pure logic should be tested without this (see test_warranty_status.py), but
    an aggregate query IS the thing being tested — counting in SQL cannot be
    checked with mocks.

    How the rollback works: the test runs inside one outer transaction that is
    never committed. `join_transaction_mode="create_savepoint"` means a
    `commit()` inside the code under test lands on a savepoint instead of
    ending that outer transaction, so even write endpoints leave no trace. Your
    dev database is safe to run this against.

    Skipped rather than failed when there is no database, so `pytest` still
    works for teammates who haven't started Docker. CI always has Postgres, so
    these tests do run on every PR.
    """
    try:
        connection = engine.connect()
    except OperationalError:  # pragma: no cover - depends on the environment
        pytest.skip("needs a database: docker compose up db")

    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace
from app.db.session import engine, get_db
from app.main import app
from app.models.workspace import Workspace, WorkspaceType


@pytest.fixture
def client() -> TestClient:
    """A test client that does not require a running database."""
    return TestClient(app)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """A session inside a transaction that is rolled back when the test ends.

    Nothing a test writes survives it, so tests can run in any order against
    the same database without cleaning up after themselves — and without
    dropping and recreating tables, which would be far slower.

    The session is bound to one connection held open for the test, so the rows
    a test flushes are visible to the request it then makes (the route is
    handed this same session via the `get_db` override below) while staying
    invisible to everything else.

    `join_transaction_mode="create_savepoint"` is what lets this survive a
    route that commits: the session's commit releases a SAVEPOINT instead of
    committing the connection's transaction, so the rollback below still undoes
    everything. Without it, the first write endpoint under test would leave its
    rows behind for every later test to trip over.

    Needs a database. Tests that do not touch one should use `client`.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def workspace(db: Session) -> Workspace:
    """The tenant a request acts inside."""
    workspace = Workspace(name="Test Workspace", type=WorkspaceType.personal)
    db.add(workspace)
    db.flush()
    return workspace


@pytest.fixture
def other_workspace(db: Session) -> Workspace:
    """A second tenant.

    Exists so tests can prove the thing that matters most in a multi-tenant
    app: rows created here must never appear in a response for `workspace`.
    """
    workspace = Workspace(name="Other Workspace", type=WorkspaceType.organization)
    db.add(workspace)
    db.flush()
    return workspace


@pytest.fixture
def api(db: Session, workspace: Workspace) -> Generator[TestClient, None, None]:
    """A client whose requests run on `db` and act inside `workspace`.

    Overriding the dependencies rather than the functions themselves is what
    lets a test choose the caller: `get_db` hands the route the test's
    transaction, and `get_current_workspace` stands in for auth, which is
    still a stub (see app/api/deps.py).

    When the real Cognito dependency lands, only the override changes — the
    tests and the routes stay as they are.
    """
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_workspace] = lambda: workspace.id
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()

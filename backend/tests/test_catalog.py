"""GET /categories, /vendors, /departments, /locations.

The four lists are identical in shape, so every test runs against all four via
parametrize: a rule that holds for categories has to hold for locations too,
and writing it once means a fifth list cannot be added with the checks quietly
missing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.catalog import Category, Department, Location, Vendor
from app.models.workspace import Workspace

CATALOG = [
    ("/categories", Category),
    ("/vendors", Vendor),
    ("/departments", Department),
    ("/locations", Location),
]


@pytest.mark.parametrize("path, model", CATALOG)
def test_empty_workspace_returns_no_items(
    api: TestClient, path: str, model: type
) -> None:
    """A new workspace starts with empty lists, and that is not an error.

    The catalog is per-workspace, so there is nothing to inherit. The frontend
    renders an empty dropdown, not a failure.
    """
    response = api.get(path)

    assert response.status_code == 200
    assert response.json() == {"items": []}


@pytest.mark.parametrize("path, model", CATALOG)
def test_returns_rows_sorted_by_name(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    """Rows come back A-Z regardless of insert order — dropdowns expect it."""
    db.add_all(
        [
            model(workspace_id=workspace.id, name="Beta"),
            model(workspace_id=workspace.id, name="Alpha"),
        ]
    )
    db.flush()

    items = api.get(path).json()["items"]

    assert [item["name"] for item in items] == ["Alpha", "Beta"]


@pytest.mark.parametrize("path, model", CATALOG)
def test_rows_from_another_workspace_are_never_returned(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    other_workspace: Workspace,
    path: str,
    model: type,
) -> None:
    """The one that matters: no leak across tenants.

    Both workspaces hold a row. The response must contain only the caller's.
    See docs/architecture.md — a nullable or unfiltered workspace_id is how
    one organization ends up reading another's data.
    """
    db.add_all(
        [
            model(workspace_id=other_workspace.id, name="Theirs"),
            model(workspace_id=workspace.id, name="Ours"),
        ]
    )
    db.flush()

    items = api.get(path).json()["items"]

    assert [item["name"] for item in items] == ["Ours"]


@pytest.mark.parametrize("path, model", CATALOG)
def test_item_shape_is_id_and_name(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    """The contract shape, so a stray column cannot leak into the response."""
    row = model(workspace_id=workspace.id, name="Laptop")
    db.add(row)
    db.flush()

    item = api.get(path).json()["items"][0]

    assert item == {"id": str(row.id), "name": "Laptop"}

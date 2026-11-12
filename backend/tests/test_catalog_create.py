"""POST /categories, /vendors, /departments, /locations.

Parametrised across all four, like the list tests: the four tables are
identical in shape, so a rule that holds for categories has to hold for
locations too.

Before these existed there was no way to create a department or a location at
all — `POST /assets` takes a `department_id` but never makes the row — which
left the dashboard's `by_department` breakdown permanently empty.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Category, Department, Location, Vendor
from app.models.membership import Membership, MembershipRole
from app.models.workspace import Workspace

CATALOG = [
    ("/categories", Category),
    ("/vendors", Vendor),
    ("/departments", Department),
    ("/locations", Location),
]


@pytest.mark.parametrize("path, model", CATALOG)
def test_creates_a_row(api: TestClient, path: str, model: type) -> None:
    response = api.post(path, json={"name": "Laptop"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Laptop"
    assert "id" in body


@pytest.mark.parametrize("path, model", CATALOG)
def test_the_new_row_appears_in_the_list(
    api: TestClient, path: str, model: type
) -> None:
    """The two halves of the same feature, so they are tested together."""
    api.post(path, json={"name": "Laptop"})

    items = api.get(path).json()["items"]

    assert [item["name"] for item in items] == ["Laptop"]


@pytest.mark.parametrize("path, model", CATALOG)
def test_the_name_is_trimmed(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    """Otherwise " Laptop" and "Laptop" become two rows that look identical."""
    api.post(path, json={"name": "  Laptop  "})

    row = db.scalars(select(model).where(model.workspace_id == workspace.id)).one()
    assert row.name == "Laptop"


# --- duplicates -------------------------------------------------------------


@pytest.mark.parametrize("path, model", CATALOG)
def test_a_duplicate_name_is_409(api: TestClient, path: str, model: type) -> None:
    api.post(path, json={"name": "Laptop"})

    response = api.post(path, json={"name": "Laptop"})

    assert response.status_code == 409
    assert "Laptop" in response.json()["detail"]


@pytest.mark.parametrize("path, model", CATALOG)
def test_a_duplicate_ignoring_case_is_also_409(
    api: TestClient, path: str, model: type
) -> None:
    """The unique constraint is case-sensitive; the rule must not be.

    Otherwise "laptop" sits beside "Laptop" and the dashboard counts them as
    two different things.
    """
    api.post(path, json={"name": "Laptop"})

    assert api.post(path, json={"name": "laptop"}).status_code == 409


@pytest.mark.parametrize("path, model", CATALOG)
def test_the_same_name_in_another_workspace_is_fine(
    api: TestClient, db: Session, other_workspace: Workspace, path: str, model: type
) -> None:
    """These lists are per-workspace: one organization's "IT" is not another's."""
    db.add(model(workspace_id=other_workspace.id, name="Laptop"))
    db.flush()

    assert api.post(path, json={"name": "Laptop"}).status_code == 201


# --- validation -------------------------------------------------------------


@pytest.mark.parametrize("path, model", CATALOG)
@pytest.mark.parametrize("name", ["", "   "], ids=["empty", "whitespace"])
def test_a_blank_name_is_rejected(
    api: TestClient, path: str, model: type, name: str
) -> None:
    assert api.post(path, json={"name": name}).status_code == 422


@pytest.mark.parametrize("path, model", CATALOG)
def test_an_over_long_name_is_rejected(
    api: TestClient, path: str, model: type
) -> None:
    """Caught as a 422 naming the field, rather than a database error."""
    assert api.post(path, json={"name": "x" * 121}).status_code == 422


# --- permissions ------------------------------------------------------------


@pytest.mark.parametrize("path, model", CATALOG)
def test_an_employee_may_not_create(
    api: TestClient, db: Session, membership: Membership, path: str, model: type
) -> None:
    """403, not 404 — they belong to the workspace, they are just not allowed.

    Managing these lists is the organization administrator's job in the
    requirements.
    """
    membership.role = MembershipRole.employee
    db.flush()

    response = api.post(path, json={"name": "Laptop"})

    assert response.status_code == 403
    assert db.scalars(select(model)).all() == []


@pytest.mark.parametrize("path, model", CATALOG)
@pytest.mark.parametrize("role", [MembershipRole.owner, MembershipRole.admin])
def test_owners_and_admins_may_create(
    api: TestClient,
    db: Session,
    membership: Membership,
    path: str,
    model: type,
    role: MembershipRole,
) -> None:
    membership.role = role
    db.flush()

    assert api.post(path, json={"name": "Laptop"}).status_code == 201


@pytest.mark.parametrize("path, model", CATALOG)
def test_employees_can_still_read_the_list(
    api: TestClient, db: Session, membership: Membership, path: str, model: type
) -> None:
    """Reading stays open: an employee filling in Add Asset needs the pickers."""
    api.post(path, json={"name": "Laptop"})
    membership.role = MembershipRole.employee
    db.flush()

    response = api.get(path)

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["Laptop"]

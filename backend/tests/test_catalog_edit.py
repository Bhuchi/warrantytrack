"""PATCH and DELETE on /categories, /vendors, /departments, /locations.

Parametrised across all four, like the create and list tests — the tables are
identical in shape, so a rule proved for categories must hold for locations.

The part worth care is what deleting a row does to the assets pointing at it:
nothing. Every catalog foreign key on `assets` is ON DELETE SET NULL, because
docs/erd.md says "deleting a category or a user must not delete assets".
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.catalog import Category, Department, Location, Vendor
from app.models.membership import Membership, MembershipRole
from app.models.workspace import Workspace

CATALOG = [
    ("/categories", Category),
    ("/vendors", Vendor),
    ("/departments", Department),
    ("/locations", Location),
]
MANAGERS = [MembershipRole.owner, MembershipRole.admin]


def add_row(db: Session, model: type, workspace: Workspace, name: str):
    row = model(workspace_id=workspace.id, name=name)
    db.add(row)
    db.flush()
    return row


# --- renaming ---------------------------------------------------------------


@pytest.mark.parametrize("path, model", CATALOG)
def test_renames_a_row(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    row = add_row(db, model, workspace, "Laptop")

    response = api.patch(f"{path}/{row.id}", json={"name": "Notebook"})

    assert response.status_code == 200
    assert response.json() == {"id": str(row.id), "name": "Notebook"}
    assert [item["name"] for item in api.get(path).json()["items"]] == ["Notebook"]


@pytest.mark.parametrize("path, model", CATALOG)
def test_the_new_name_is_trimmed(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    row = add_row(db, model, workspace, "Laptop")

    body = api.patch(f"{path}/{row.id}", json={"name": "  Notebook  "}).json()

    assert body["name"] == "Notebook"


@pytest.mark.parametrize("path, model", CATALOG)
def test_renaming_to_a_name_another_row_has_is_409(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    add_row(db, model, workspace, "Laptop")
    other = add_row(db, model, workspace, "Monitor")

    response = api.patch(f"{path}/{other.id}", json={"name": "Laptop"})

    assert response.status_code == 409
    assert other.name == "Monitor"


@pytest.mark.parametrize("path, model", CATALOG)
def test_renaming_to_an_existing_name_ignoring_case_is_409(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    add_row(db, model, workspace, "Laptop")
    other = add_row(db, model, workspace, "Monitor")

    assert api.patch(f"{path}/{other.id}", json={"name": "laptop"}).status_code == 409


@pytest.mark.parametrize("path, model", CATALOG)
def test_renaming_a_row_to_its_own_name_succeeds(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    """A row does not clash with itself.

    A form that submits every field should not fail because the name happens
    not to have changed.
    """
    row = add_row(db, model, workspace, "Laptop")

    assert api.patch(f"{path}/{row.id}", json={"name": "Laptop"}).status_code == 200


@pytest.mark.parametrize("path, model", CATALOG)
def test_renaming_to_a_blank_name_is_422(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    row = add_row(db, model, workspace, "Laptop")

    assert api.patch(f"{path}/{row.id}", json={"name": "   "}).status_code == 422


# --- deleting ---------------------------------------------------------------


@pytest.mark.parametrize("path, model", CATALOG)
def test_deletes_a_row(
    api: TestClient, db: Session, workspace: Workspace, path: str, model: type
) -> None:
    row = add_row(db, model, workspace, "Laptop")

    response = api.delete(f"{path}/{row.id}")

    assert response.status_code == 204
    assert api.get(path).json()["items"] == []


def test_deleting_a_category_leaves_its_assets_alone(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """ON DELETE SET NULL — "deleting a category must not delete assets"."""
    category = add_row(db, Category, workspace, "Laptop")
    asset = Asset(
        workspace_id=workspace.id,
        name="Dell Latitude",
        serial_number="ABC123",
        condition="new",
        purchase_date=date(2025, 3, 1),
        currency="THB",
        category_id=category.id,
    )
    db.add(asset)
    db.flush()

    api.delete(f"/categories/{category.id}")
    db.expire_all()

    survivor = db.get(Asset, asset.id)
    assert survivor is not None
    assert survivor.category_id is None


def test_deleting_a_vendor_leaves_its_assets_alone(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    vendor = add_row(db, Vendor, workspace, "Power Buy")
    asset = Asset(
        workspace_id=workspace.id,
        name="Dell Latitude",
        serial_number="ABC123",
        condition="new",
        purchase_date=date(2025, 3, 1),
        currency="THB",
        vendor_id=vendor.id,
    )
    db.add(asset)
    db.flush()

    api.delete(f"/vendors/{vendor.id}")
    db.expire_all()

    survivor = db.get(Asset, asset.id)
    assert survivor is not None
    assert survivor.vendor_id is None


# --- tenancy ----------------------------------------------------------------


@pytest.mark.parametrize("path, model", CATALOG)
def test_renaming_a_row_in_another_workspace_is_404(
    api: TestClient,
    db: Session,
    other_workspace: Workspace,
    path: str,
    model: type,
) -> None:
    theirs = add_row(db, model, other_workspace, "Theirs")

    response = api.patch(f"{path}/{theirs.id}", json={"name": "Hijacked"})

    assert response.status_code == 404
    assert theirs.name == "Theirs"


@pytest.mark.parametrize("path, model", CATALOG)
def test_deleting_a_row_in_another_workspace_is_404(
    api: TestClient,
    db: Session,
    other_workspace: Workspace,
    path: str,
    model: type,
) -> None:
    theirs = add_row(db, model, other_workspace, "Theirs")

    response = api.delete(f"{path}/{theirs.id}")

    assert response.status_code == 404
    assert db.scalars(select(model).where(model.id == theirs.id)).first() is not None


@pytest.mark.parametrize("path, model", CATALOG)
def test_an_unknown_id_is_404(api: TestClient, path: str, model: type) -> None:
    unknown = "00000000-0000-0000-0000-0000000000ff"

    assert api.patch(f"{path}/{unknown}", json={"name": "X"}).status_code == 404
    assert api.delete(f"{path}/{unknown}").status_code == 404


# --- permissions ------------------------------------------------------------


@pytest.mark.parametrize("path, model", CATALOG)
def test_an_employee_may_not_rename_or_delete(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    membership: Membership,
    path: str,
    model: type,
) -> None:
    """403, not 404 — they belong to the workspace, they are just not allowed."""
    row = add_row(db, model, workspace, "Laptop")
    membership.role = MembershipRole.employee
    db.flush()

    assert api.patch(f"{path}/{row.id}", json={"name": "Nope"}).status_code == 403
    assert api.delete(f"{path}/{row.id}").status_code == 403
    db.expire_all()
    assert db.scalars(select(model).where(model.id == row.id)).first() is not None


@pytest.mark.parametrize("path, model", CATALOG)
@pytest.mark.parametrize("role", MANAGERS)
def test_owners_and_admins_may_rename_and_delete(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    membership: Membership,
    path: str,
    model: type,
    role: MembershipRole,
) -> None:
    row = add_row(db, model, workspace, "Laptop")
    membership.role = role
    db.flush()

    assert api.patch(f"{path}/{row.id}", json={"name": "Notebook"}).status_code == 200
    assert api.delete(f"{path}/{row.id}").status_code == 204

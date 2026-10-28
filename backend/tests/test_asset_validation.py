"""Server-side validation of the ids an asset points at (CLOUDAPPG5-118).

Task 4 requires Vendor and Category to be "present and **valid**". Valid means
in the caller's own workspace: nothing stops a request sending another
organization's `vendor_id`, and the foreign key does not stop it either —
`assets.vendor_id` references `vendors.id` with no tenant predicate.

Left unchecked, an asset attaches to another workspace's vendor and
`GET /assets/{id}` hands that organization's vendor name back. Tenancy is
enforced in queries (docs/architecture.md); a write that takes an id on trust
walks around it.

Every test here is a direct API call with no frontend involved, which is also
the acceptance criterion "apply validation server-side even when the frontend
validates first".
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.catalog import Category, Department, Location, Vendor
from app.models.user import User
from app.models.workspace import Workspace

#: (payload field, model, the label the message uses)
REFERENCES = [
    ("category_id", Category, "category"),
    ("vendor_id", Vendor, "vendor"),
    ("department_id", Department, "department"),
    ("location_id", Location, "location"),
]


def body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Dell Latitude 5540",
        "serial_number": "ABC123",
        "condition": "new",
        "purchase_date": "2025-03-01",
        "price": "32900.00",
        "vendor_name": "Power Buy",
    }
    payload.update(overrides)
    return payload


def fields_in(response) -> set[str]:
    """The field names a 422 blames, read out of FastAPI's `loc`."""
    return {entry["loc"][1] for entry in response.json()["detail"]}


# --- a reference belonging to another workspace -----------------------------


@pytest.mark.parametrize("field, model, label", REFERENCES)
def test_a_reference_from_another_workspace_is_rejected(
    api: TestClient,
    db: Session,
    other_workspace: Workspace,
    field: str,
    model: type,
    label: str,
) -> None:
    """The leak this module exists to close."""
    theirs = model(workspace_id=other_workspace.id, name="Theirs")
    db.add(theirs)
    db.flush()

    response = api.post("/assets", json=body(**{field: str(theirs.id)}))

    assert response.status_code == 422
    assert field in fields_in(response)


@pytest.mark.parametrize("field, model, label", REFERENCES)
def test_the_message_does_not_reveal_that_the_row_exists(
    api: TestClient,
    db: Session,
    other_workspace: Workspace,
    field: str,
    model: type,
    label: str,
) -> None:
    """A missing id and someone else's id must read identically.

    Saying "that belongs to another workspace" would confirm the id is real,
    which is the same leak 404-not-403 exists to prevent elsewhere.
    """
    theirs = model(workspace_id=other_workspace.id, name="Theirs")
    db.add(theirs)
    db.flush()

    theirs_response = api.post("/assets", json=body(**{field: str(theirs.id)}))
    unknown_response = api.post(
        "/assets", json=body(**{field: "00000000-0000-0000-0000-0000000000ff"})
    )

    assert theirs_response.json()["detail"] == unknown_response.json()["detail"]


@pytest.mark.parametrize("field, model, label", REFERENCES)
def test_an_unknown_reference_is_rejected(
    api: TestClient, field: str, model: type, label: str
) -> None:
    response = api.post(
        "/assets", json=body(**{field: "00000000-0000-0000-0000-0000000000ff"})
    )

    assert response.status_code == 422
    assert field in fields_in(response)


@pytest.mark.parametrize("field, model, label", REFERENCES)
def test_a_reference_in_the_callers_own_workspace_is_accepted(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    field: str,
    model: type,
    label: str,
) -> None:
    """The check must not reject the ordinary case."""
    ours = model(workspace_id=workspace.id, name="Ours")
    db.add(ours)
    db.flush()

    assert api.post("/assets", json=body(**{field: str(ours.id)})).status_code == 201


# --- the assignee -----------------------------------------------------------


def test_assigning_to_a_user_outside_the_workspace_is_rejected(
    api: TestClient, db: Session
) -> None:
    """A user who exists but is not a member here."""
    stranger = User(
        cognito_sub="stranger-sub",
        email="stranger@warrantytrack.local",
        display_name="Stranger",
    )
    db.add(stranger)
    db.flush()

    response = api.post(
        "/assets", json=body(assigned_to_user_id=str(stranger.id))
    )

    assert response.status_code == 422
    assert "assigned_to_user_id" in fields_in(response)


def test_assigning_to_a_member_is_accepted(
    api: TestClient, user: User
) -> None:
    response = api.post("/assets", json=body(assigned_to_user_id=str(user.id)))

    assert response.status_code == 201
    assert response.json()["assigned_to"]["user_id"] == str(user.id)


# --- several problems at once -----------------------------------------------


def test_every_bad_reference_is_reported_together(
    api: TestClient, db: Session, other_workspace: Workspace
) -> None:
    """A form with two bad pickers should not need two round trips to find out."""
    their_vendor = Vendor(workspace_id=other_workspace.id, name="Theirs")
    their_category = Category(workspace_id=other_workspace.id, name="Theirs")
    db.add_all([their_vendor, their_category])
    db.flush()

    response = api.post(
        "/assets",
        json=body(
            vendor_id=str(their_vendor.id),
            category_id=str(their_category.id),
            department_id="00000000-0000-0000-0000-0000000000ff",
        ),
    )

    assert response.status_code == 422
    assert fields_in(response) == {"vendor_id", "category_id", "department_id"}


# --- nothing is written on rejection ----------------------------------------


def test_a_rejected_save_writes_nothing_at_all(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """Including the vendor that `vendor_name` would otherwise create.

    Validation runs before the find-or-create lookup, so a rejected request
    must not leave a half-made catalog row behind.
    """
    response = api.post(
        "/assets",
        json=body(
            vendor_name="Brand New Vendor",
            category_id="00000000-0000-0000-0000-0000000000ff",
        ),
    )

    assert response.status_code == 422
    assert db.scalars(select(Asset)).all() == []
    assert db.scalars(select(Vendor)).all() == []


# --- the same rules on edit -------------------------------------------------


def test_patch_cannot_move_an_asset_to_another_workspaces_vendor(
    api: TestClient, db: Session, other_workspace: Workspace
) -> None:
    """An edit must not be a side door into the same leak."""
    created = api.post("/assets", json=body()).json()
    theirs = Vendor(workspace_id=other_workspace.id, name="Theirs")
    db.add(theirs)
    db.flush()

    response = api.patch(
        f"/assets/{created['id']}", json={"vendor_id": str(theirs.id)}
    )

    assert response.status_code == 422
    db.expire_all()
    asset = db.get(Asset, uuid.UUID(created["id"]))
    assert asset is not None
    assert asset.vendor_id != theirs.id


def test_patch_accepts_a_reference_in_the_callers_workspace(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    created = api.post("/assets", json=body()).json()
    ours = Category(workspace_id=workspace.id, name="Laptop")
    db.add(ours)
    db.flush()

    response = api.patch(
        f"/assets/{created['id']}", json={"category_id": str(ours.id)}
    )

    assert response.status_code == 200
    assert response.json()["category"]["name"] == "Laptop"


def test_patch_can_still_clear_a_reference(api: TestClient) -> None:
    """`null` means "clear it", not "an id to check"."""
    created = api.post("/assets", json=body(category_name="Laptop")).json()

    updated = api.patch(f"/assets/{created['id']}", json={"category_id": None})

    assert updated.status_code == 200
    assert updated.json()["category"] is None


# --- the error shape --------------------------------------------------------


def test_errors_use_fastapis_own_422_shape(api: TestClient) -> None:
    """Indistinguishable from a Pydantic failure, so one client path reads both.

    `lib/api.ts` reads `detail`; a form showing errors inline reads `loc[1]`.
    Inventing a different shape here would need a second code path for no
    extra information.
    """
    response = api.post(
        "/assets", json=body(vendor_id="00000000-0000-0000-0000-0000000000ff")
    )

    entry = response.json()["detail"][0]
    assert entry["loc"] == ["body", "vendor_id"]
    assert entry["type"] == "value_error"
    assert isinstance(entry["msg"], str) and entry["msg"]


def test_a_schema_error_and_a_reference_error_look_the_same(
    api: TestClient,
) -> None:
    payload = body(vendor_id="00000000-0000-0000-0000-0000000000ff")
    del payload["vendor_name"]
    payload["name"] = ""

    schema_only = api.post("/assets", json=body(name=""))
    reference_only = api.post("/assets", json=payload)

    for response in (schema_only, reference_only):
        for entry in response.json()["detail"]:
            assert set(entry).issuperset({"type", "loc", "msg"})
            assert entry["loc"][0] == "body"

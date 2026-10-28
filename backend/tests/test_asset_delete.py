"""DELETE /assets/{id}.

Owners and admins only (docs/api.md). The interesting part is not the delete
itself but which code comes back to whom: 404 when the caller is outside the
workspace, 403 when they are inside it but not allowed.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.document import AssetDocument, Document
from app.models.membership import Membership, MembershipRole
from app.models.warranty import Warranty
from app.models.workspace import Workspace


def create(api: TestClient, **overrides: object) -> dict:
    payload: dict[str, object] = {
        "name": "Dell Latitude 5540",
        "serial_number": "ABC123",
        "condition": "new",
        "purchase_date": "2025-03-01",
        "price": "32900.00",
        "vendor_name": "Power Buy",
        "warranty": {
            "provider": "Dell",
            "start_date": "2025-03-01",
            "duration_months": 36,
        },
    }
    payload.update(overrides)
    return api.post("/assets", json=payload).json()


# --- the happy path ---------------------------------------------------------


def test_deletes_the_asset(api: TestClient) -> None:
    asset = create(api)

    response = api.delete(f"/assets/{asset['id']}")

    assert response.status_code == 204
    assert api.get(f"/assets/{asset['id']}").status_code == 404
    assert api.get("/assets").json()["total"] == 0


def test_an_admin_may_delete(
    api: TestClient, db: Session, membership: Membership
) -> None:
    membership.role = MembershipRole.admin
    db.flush()
    asset = create(api)

    assert api.delete(f"/assets/{asset['id']}").status_code == 204


# --- what goes with it, and what does not -----------------------------------


def test_the_warranty_goes_with_the_asset(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """Cascade, per the schema — a warranty cannot outlive its asset."""
    asset = create(api)

    api.delete(f"/assets/{asset['id']}")

    remaining = db.scalars(
        select(Warranty).where(Warranty.workspace_id == workspace.id)
    ).all()
    assert remaining == []


def test_document_links_go_but_the_documents_stay(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """One invoice can back several assets, and the S3 object outlives any one.

    So the join row goes and the document row does not — deleting an asset
    must not strand another asset's receipt.
    """
    document = Document(workspace_id=workspace.id, s3_key="ws/receipt.jpg")
    db.add(document)
    db.flush()
    asset = create(api, document_ids=[str(document.id)])

    api.delete(f"/assets/{asset['id']}")

    assert db.scalars(select(AssetDocument)).all() == []
    assert db.get(Document, document.id) is not None


def test_the_vendor_is_not_deleted_with_the_asset(api: TestClient) -> None:
    """Catalog rows outlive the assets pointing at them (docs/erd.md)."""
    asset = create(api)

    api.delete(f"/assets/{asset['id']}")

    assert [item["name"] for item in api.get("/vendors").json()["items"]] == [
        "Power Buy"
    ]


# --- permissions ------------------------------------------------------------


def test_an_employee_may_not_delete(
    api: TestClient, db: Session, membership: Membership
) -> None:
    """403, not 404: they belong to this workspace, they are just not allowed."""
    asset = create(api)
    membership.role = MembershipRole.employee
    db.flush()

    response = api.delete(f"/assets/{asset['id']}")

    assert response.status_code == 403
    # Checked against the row, not against GET /assets: an employee cannot see
    # an unassigned asset through the API, so an empty list would prove
    # nothing about whether the delete went through.
    assert db.get(Asset, uuid.UUID(asset["id"])) is not None


def test_an_employee_is_refused_before_the_asset_is_looked_up(
    api: TestClient, db: Session, membership: Membership
) -> None:
    """A forbidden caller must not be able to probe for which ids exist.

    The role is checked first, so a real id and a made-up one give the same
    answer.
    """
    membership.role = MembershipRole.employee
    db.flush()

    response = api.delete("/assets/00000000-0000-0000-0000-0000000000ff")

    assert response.status_code == 403


@pytest.mark.parametrize("role", [MembershipRole.owner, MembershipRole.admin])
def test_deleting_an_asset_in_another_workspace_is_404(
    api: TestClient,
    db: Session,
    membership: Membership,
    other_workspace: Workspace,
    role: MembershipRole,
) -> None:
    """404 even for an owner — of a different workspace."""
    membership.role = role
    theirs = Asset(
        workspace_id=other_workspace.id,
        name="Theirs",
        serial_number="THEIRS-1",
        condition="new",
        purchase_date=date(2025, 3, 1),
        currency="THB",
    )
    db.add(theirs)
    db.flush()

    response = api.delete(f"/assets/{theirs.id}")

    assert response.status_code == 404
    assert db.get(Asset, theirs.id) is not None


def test_deleting_an_unknown_id_is_404(api: TestClient) -> None:
    response = api.delete("/assets/00000000-0000-0000-0000-0000000000ff")

    assert response.status_code == 404


def test_a_caller_with_no_membership_gets_404(
    api: TestClient, db: Session, membership: Membership
) -> None:
    """Not 403 — a 403 would confirm the workspace exists."""
    asset = create(api)
    db.delete(membership)
    db.flush()

    assert api.delete(f"/assets/{asset['id']}").status_code == 404

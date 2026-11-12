"""Assignment is an organization concept (CLOUDAPPG5-93).

Three sources say so:

- `docs/architecture.md`: "type = 'personal' -> exactly one member, role
  owner" — so a personal workspace has no employees.
- `docs/api.md`: assign hands an asset "to an employee (admin only)" — a
  personal workspace has neither.
- The proposed schema says it with a constraint:
  `assets_org_only_fields CHECK (organization_id IS NOT NULL OR
  (assigned_to_user_id IS NULL AND department_id IS NULL AND
  location_id IS NULL))`.

Without this rule the only possible assignee in a personal workspace is
yourself — which passes the membership check and produces a meaningless
"assigned to me" state.

Unassigning stays allowed everywhere. Clearing a field is never the dangerous
direction, and refusing it would strand any asset assigned before this rule.
"""

from __future__ import annotations

import uuid

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_user, get_current_workspace
from app.db.session import get_db
from app.main import app
from app.models.asset import Asset
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace


def body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Dell Latitude 5540",
        "serial_number": "ABC123",
        "condition": "new",
        "purchase_date": "2025-03-01",
        "price": "32900.00",
        "vendor_name": "Power Buy",
        "category_name": "Laptop",
        "invoice_number": "INV-2025-001",
        "warranty": {
            "provider": "Dell",
            "start_date": "2025-03-01",
            "duration_months": 36,
        },
    }
    payload.update(overrides)
    return payload


def fields_in(response) -> set[str]:
    return {entry["loc"][1] for entry in response.json()["detail"]}


@pytest.fixture
def personal_api(
    db: Session, personal_workspace: Workspace, user: User
) -> Generator[TestClient, None, None]:
    """A client acting as the sole owner of a personal workspace.

    Built here rather than in conftest because only this file needs it: the
    shared `api` fixture is an organization, which is what every other rule
    cares about.
    """
    membership = Membership(
        user_id=user.id,
        workspace_id=personal_workspace.id,
        role=MembershipRole.owner,
    )
    db.add(membership)
    db.flush()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_workspace] = lambda: personal_workspace.id
    app.dependency_overrides[get_current_user] = lambda: user.id
    app.dependency_overrides[get_current_membership] = lambda: membership
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --- the rule ---------------------------------------------------------------


def test_assigning_in_a_personal_workspace_is_rejected(
    personal_api: TestClient, user: User
) -> None:
    """Even to yourself — especially to yourself, since that is the only option."""
    asset = personal_api.post("/assets", json=body()).json()

    response = personal_api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(user.id)},
    )

    assert response.status_code == 422
    assert "assigned_to_user_id" in fields_in(response)


def test_creating_an_assigned_asset_in_a_personal_workspace_is_rejected(
    personal_api: TestClient, db: Session, user: User
) -> None:
    """The other door into the same field — POST accepts it too."""
    response = personal_api.post(
        "/assets", json=body(assigned_to_user_id=str(user.id))
    )

    assert response.status_code == 422
    assert "assigned_to_user_id" in fields_in(response)


def test_the_message_explains_why_rather_than_blaming_the_user(
    personal_api: TestClient, user: User
) -> None:
    """"Not a member" would be wrong and confusing — they are the owner."""
    response = personal_api.post(
        "/assets", json=body(assigned_to_user_id=str(user.id))
    )

    message = response.json()["detail"][0]["msg"]
    assert "personal workspace" in message.lower()


# --- what still works -------------------------------------------------------


def test_a_personal_workspace_can_still_create_assets(
    personal_api: TestClient,
) -> None:
    """The rule is about assignment only, not about personal workspaces."""
    response = personal_api.post("/assets", json=body())

    assert response.status_code == 201
    assert response.json()["assigned_to"] is None


def test_unassigning_is_still_allowed_in_a_personal_workspace(
    personal_api: TestClient, db: Session, personal_workspace: Workspace
) -> None:
    """Clearing is never the dangerous direction.

    An asset assigned before this rule existed must not be stuck that way.
    """
    created = personal_api.post("/assets", json=body()).json()
    stored = db.get(Asset, uuid.UUID(created["id"]))
    assert stored is not None
    stored.assigned_to_user_id = None
    db.flush()

    response = personal_api.post(
        f"/assets/{created['id']}/assign", json={"assigned_to_user_id": None}
    )

    assert response.status_code == 200
    assert response.json()["assigned_to"] is None


def test_an_organization_workspace_is_unaffected(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """The ordinary path keeps working — this is the regression guard."""
    colleague = User(
        cognito_sub="colleague-sub",
        email="colleague@warrantytrack.local",
        display_name="Colleague",
    )
    db.add(colleague)
    db.flush()
    db.add(
        Membership(
            user_id=colleague.id,
            workspace_id=workspace.id,
            role=MembershipRole.employee,
        )
    )
    db.flush()
    asset = api.post("/assets", json=body()).json()

    response = api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(colleague.id)},
    )

    assert response.status_code == 200
    assert response.json()["assigned_to"]["display_name"] == "Colleague"

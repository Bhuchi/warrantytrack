"""Shared request dependencies for routes.

Authentication (Amazon Cognito) is Chaitawat's foundation work. Until the real
token-verification dependency lands, every leg develops against a STUB that
returns a fixed dev workspace/user — the same IDs that `scripts/seed_dev.py`
inserts.

API-First in practice: routes depend on `get_current_workspace` /
`get_current_user` by NAME. When the real auth arrives, only the *body* of
these functions changes (verify the JWT -> look up the membership); every route
keeps working untouched. That is why a route never reads a token itself.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.membership import Membership, MembershipRole

# Deterministic IDs so the stub and the seed script always agree on "who".
DEV_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _forbid_stub_in_prod() -> None:
    # A loud failure is better than silently serving one hard-coded user in prod.
    if settings.environment == "production":
        raise RuntimeError(
            "Auth stub is active in production. Replace app.api.deps with the "
            "real Cognito dependency before deploying."
        )


def get_current_workspace() -> uuid.UUID:
    """STUB — the workspace the request acts in.

    Real version: read `workspace_id` from the verified token / active
    membership. Signature stays `() -> uuid.UUID`, so routes don't change.
    """
    _forbid_stub_in_prod()
    return DEV_WORKSPACE_ID


def get_current_user() -> uuid.UUID:
    """STUB — the signed-in user. Real version: derive from Cognito `sub`."""
    _forbid_stub_in_prod()
    return DEV_USER_ID


def get_current_membership(
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
    user_id: uuid.UUID = Depends(get_current_user),
) -> Membership:
    """The caller's role inside the workspace the request acts in.

    This one is NOT a stub. Identity is stubbed above (who you are), but
    authorization is read from the `memberships` table on every request, which
    is exactly how it works once Cognito lands — see docs/architecture.md,
    Decision 2. Roles are never taken from a token.

    No membership in that workspace -> **404, not 403**. A 403 would confirm
    the workspace exists, which leaks across tenants (docs/api.md).
    """
    membership = db.scalars(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status_code=404, detail="Not found")
    return membership


def employee_scope(membership: Membership) -> uuid.UUID | None:
    """The user id a query must be narrowed to, or None for the whole workspace.

    Employees may only see assets assigned to them (docs/architecture.md);
    owners and admins see everything. Returning None rather than a boolean
    keeps the caller's query to one `if`, and keeps the rule in one place
    instead of in every endpoint that lists assets.
    """
    if membership.role is MembershipRole.employee:
        return membership.user_id
    return None


def require_manager(
    membership: Membership = Depends(get_current_membership),
) -> Membership:
    """Allow owners and admins through; refuse employees with 403.

    The guard for everything an employee may not do at all: deleting an asset,
    and managing the catalog lists an organization's admin owns (departments,
    locations, vendors, categories).

    **403 here, not 404.** The caller does belong to this workspace — they are
    simply not allowed — so there is nothing to hide. That is the opposite of
    `get_current_membership`, which returns 404 precisely because a stranger
    must not learn the workspace exists.

    Used as the dependency instead of `get_current_membership` so the check
    runs before the route body, and before any lookup that could otherwise
    reveal whether an id exists.
    """
    if membership.role is MembershipRole.employee:
        raise HTTPException(
            status_code=403, detail="Only an owner or admin can do this."
        )
    return membership

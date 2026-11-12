"""Dashboard routes (Leg B). Contract: docs/api.md -> Dashboard."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import employee_scope, get_current_membership
from app.db.session import get_db
from app.models.membership import Membership
from app.schemas.dashboard import DashboardSummary, ExpiringList
from app.services import dashboard as dashboard_service
from app.services.warranty import EXPIRING_SOON_DAYS

# No prefix here — main.py mounts this router at "/dashboard".
router = APIRouter(tags=["dashboard"])


def _today() -> date:
    """The day the request is answered for.

    Read at the edge and passed down, so services stay clock-free and testable.
    UTC: if the team wants Bangkok-local day boundaries (which would move the
    expiry cut-off by 7 hours), this is the one line to change.
    """
    return datetime.now(timezone.utc).date()


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> DashboardSummary:
    """GET /dashboard/summary — counts by status and by department (D04).

    An employee sees only the assets assigned to them, so the numbers are
    theirs, not the organization's — `employee_scope()` decides that, not this
    route.
    """
    data = dashboard_service.summary(
        db,
        membership.workspace_id,
        _today(),
        assigned_to_user_id=employee_scope(membership),
    )
    return DashboardSummary(**data)


@router.get("/expiring", response_model=ExpiringList)
def dashboard_expiring(
    days: int = Query(
        EXPIRING_SOON_DAYS,
        ge=1,
        le=365,
        description="How far ahead to look. Bounded so one request cannot ask "
        "for the whole table.",
    ),
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> ExpiringList:
    """GET /dashboard/expiring?days=30 — what lapses next, soonest first."""
    items = dashboard_service.expiring(
        db,
        membership.workspace_id,
        _today(),
        days=days,
        assigned_to_user_id=employee_scope(membership),
    )
    return ExpiringList(items=items)

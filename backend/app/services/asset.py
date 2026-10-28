"""Query logic for the Assets endpoints.

Routes stay thin: they say who is asking and what they are filtering by, and
hand off here. All SQL lives in services, so it is testable without HTTP and
reusable — the dashboard and the bulk importer will call into this module too.

Every query starts by narrowing to one workspace. That is not a convenience:
it is the whole tenancy boundary (docs/architecture.md). An asset in another
workspace is simply not in the result set, which is what makes
`GET /assets/{id}` return 404 rather than 403 without the route having to think
about it.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.models.asset import Asset
from app.models.warranty import Warranty
from app.services import warranty as warranty_service
from app.services.warranty import WarrantyStatus


def _status_condition(status: WarrantyStatus, today: date) -> ColumnElement[bool]:
    """Express one warranty status as SQL, matching compute_status() exactly.

    The two have to agree: this decides which rows come back, and
    `compute_status` decides what each row is then labelled. If they drifted,
    a filter for "expired" could return a row the response then calls
    "expiring_soon".

    The boundaries are therefore the same ones that function documents:
    `end_date == today` is not yet past, so it is expiring_soon; exactly
    EXPIRING_SOON_DAYS away is still expiring_soon.

    `unknown` is the absence of a warranty row, which is why the caller must
    outer-join rather than inner-join — an inner join would drop exactly the
    rows this status is about.
    """
    soon = today + timedelta(days=warranty_service.EXPIRING_SOON_DAYS)

    if status is WarrantyStatus.unknown:
        return Warranty.id.is_(None)
    if status is WarrantyStatus.expired:
        return Warranty.end_date < today
    if status is WarrantyStatus.expiring_soon:
        return and_(Warranty.end_date >= today, Warranty.end_date <= soon)
    return Warranty.end_date > soon


def _conditions(
    workspace_id: uuid.UUID,
    q: str | None,
    status: WarrantyStatus | None,
    category_id: uuid.UUID | None,
    vendor_id: uuid.UUID | None,
    today: date,
) -> list[ColumnElement[bool]]:
    """The WHERE clause, built once and used by both the count and the page.

    Sharing it is what keeps `total` honest: if the two queries could drift,
    the screen would say "1-20 of 128" while filtering down to 40.
    """
    conditions: list[ColumnElement[bool]] = [Asset.workspace_id == workspace_id]

    if category_id is not None:
        conditions.append(Asset.category_id == category_id)
    if vendor_id is not None:
        conditions.append(Asset.vendor_id == vendor_id)
    if q:
        # Name, serial and invoice number — what a user has in front of them
        # when hunting for one asset. ilike so case does not matter.
        like = f"%{q}%"
        conditions.append(
            or_(
                Asset.name.ilike(like),
                Asset.serial_number.ilike(like),
                Asset.invoice_number.ilike(like),
            )
        )
    if status is not None:
        conditions.append(_status_condition(status, today))

    return conditions


def list_assets(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    q: str | None = None,
    status: WarrantyStatus | None = None,
    category_id: uuid.UUID | None = None,
    vendor_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    today: date | None = None,
) -> tuple[int, list[Asset]]:
    """Return (total matching, one page of assets) for the Assets List.

    `today` is injectable so tests can pin the clock when checking the status
    filter's boundaries; callers pass nothing in production.

    Two queries rather than one: a COUNT over every match, then the page. The
    screen needs both numbers and a window function would compute the total
    once per row.

    Ordering is newest-first with `id` as a tiebreaker. The tiebreaker is not
    cosmetic — without a deterministic sort, two assets created in the same
    transaction could swap places between page 1 and page 2, so one would
    appear twice and another not at all.
    """
    today = today or date.today()
    conditions = _conditions(workspace_id, q, status, category_id, vendor_id, today)

    total = db.scalar(
        select(func.count())
        .select_from(Asset)
        .outerjoin(Warranty, Warranty.asset_id == Asset.id)
        .where(*conditions)
    )

    items = (
        db.scalars(
            select(Asset)
            # Outer, not inner: assets without a warranty are `unknown`, not
            # missing. The same join backs both the filter and the eager load.
            .outerjoin(Warranty, Warranty.asset_id == Asset.id)
            .options(
                contains_eager(Asset.warranty),
                # Loaded here so building each row does not fire two more
                # queries per asset for the names the table draws.
                joinedload(Asset.category),
                joinedload(Asset.vendor),
            )
            .where(*conditions)
            .order_by(Asset.created_at.desc(), Asset.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .all()
    )

    return total or 0, list(items)


def get_asset(
    db: Session, workspace_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset | None:
    """One asset with everything the detail screen draws, or None.

    None covers both "no such asset" and "exists, but in a workspace you are
    not in" — the caller turns both into 404. Telling them apart would confirm
    the record exists to someone who should not know, which is the leak
    docs/api.md warns against.
    """
    return (
        db.scalars(
            select(Asset)
            .options(
                joinedload(Asset.warranty),
                joinedload(Asset.category),
                joinedload(Asset.vendor),
                joinedload(Asset.department),
                joinedload(Asset.assigned_to),
                joinedload(Asset.documents),
            )
            .where(Asset.id == asset_id, Asset.workspace_id == workspace_id)
        )
        .unique()
        .one_or_none()
    )

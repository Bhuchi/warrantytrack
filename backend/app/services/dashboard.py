"""Dashboard aggregates (CLOUDAPPG5-130).

Both endpoints answer the same question — "how are this workspace's warranties
doing?" — at two zoom levels: counts for the cards and charts, and the rows for
the expiring table.

The rule for what counts as expired / expiring soon is NOT repeated here. It
comes from app/services/warranty.py as a boundary date (`soon_cutoff`) that
goes straight into SQL, so Postgres does the counting while the rule stays
defined in one module. tests/test_warranty_status.py walks the boundaries to
prove the SQL comparisons below and `compute_status()` agree.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.catalog import Department, Vendor
from app.models.warranty import Warranty
from app.services.warranty import (
    EXPIRING_SOON_DAYS,
    WarrantyStatus,
    compute_status,
    soon_cutoff,
)

# The summary reports "no warranty" where the status rule says "unknown". Same
# thing, two audiences: `unknown` is the asset's status, `no_warranty` is the
# card's label in docs/api.md. Renamed once, here, rather than teaching SQL a
# second vocabulary.
_SUMMARY_FIELD = {
    WarrantyStatus.active: "active",
    WarrantyStatus.expiring_soon: "expiring_soon",
    WarrantyStatus.expired: "expired",
    WarrantyStatus.unknown: "no_warranty",
}


def _scoped_to(stmt: Select, assigned_to_user_id: uuid.UUID | None) -> Select:
    """Narrow a query to one employee's own assets, if that is who is asking.

    Pass `None` for owners and admins — they see the whole workspace. See
    `employee_scope()` in app/api/deps.py.
    """
    if assigned_to_user_id is None:
        return stmt
    return stmt.where(Asset.assigned_to_user_id == assigned_to_user_id)


def summary(
    db: Session,
    workspace_id: uuid.UUID,
    today: date,
    assigned_to_user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Counts by warranty status, plus a count per department (D04).

    Two queries, both aggregating in the database. Loading the assets and
    counting them in Python would work today and get slower every week.
    """
    cutoff = soon_cutoff(today)

    # The status rule, as SQL. Mirrors compute_status() exactly.
    status = case(
        (Warranty.end_date.is_(None), WarrantyStatus.unknown.value),
        (Warranty.end_date < today, WarrantyStatus.expired.value),
        (Warranty.end_date <= cutoff, WarrantyStatus.expiring_soon.value),
        else_=WarrantyStatus.active.value,
    ).label("status")

    by_status = (
        select(status, func.count().label("count"))
        .select_from(Asset)
        # OUTER join: an asset with no warranty row must still be counted (as
        # no_warranty). An inner join would drop it from `total` entirely.
        .outerjoin(
            Warranty,
            and_(
                Warranty.asset_id == Asset.id,
                # Redundant — asset_id already implies the workspace — but the
                # house rule is that every query names the tenant it is in.
                Warranty.workspace_id == workspace_id,
            ),
        )
        .where(Asset.workspace_id == workspace_id)
    )
    rows = db.execute(_scoped_to(by_status, assigned_to_user_id).group_by(status)).all()

    counts = {field: 0 for field in _SUMMARY_FIELD.values()}
    for status_value, count in rows:
        counts[_SUMMARY_FIELD[WarrantyStatus(status_value)]] = count

    # Assets with no department are counted in `total` but have no row here:
    # inviting the API to invent a label like "Others" would make the server
    # decide presentation. The frontend can show the remainder if it wants.
    by_department = (
        select(Department.id, Department.name, func.count().label("count"))
        .select_from(Asset)
        .join(Department, Asset.department_id == Department.id)
        .where(Asset.workspace_id == workspace_id)
    )
    department_rows = db.execute(
        _scoped_to(by_department, assigned_to_user_id)
        .group_by(Department.id, Department.name)
        .order_by(func.count().desc(), Department.name)
    ).all()

    return {
        "total": sum(counts.values()),
        **counts,
        "by_department": [
            {"department_id": dept_id, "name": name, "count": count}
            for dept_id, name, count in department_rows
        ],
    }


def expiring(
    db: Session,
    workspace_id: uuid.UUID,
    today: date,
    days: int = EXPIRING_SOON_DAYS,
    assigned_to_user_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Assets whose cover lapses within `days`, soonest first (D04 table).

    `days` decides which rows appear; it does NOT change what `status` means.
    Asked for 60 days, a warranty 45 days out is listed but still reports
    `active`, because that is what the asset list and detail screens say about
    it. One word, one meaning, on every screen.

    Already-expired assets are excluded: "expiring within N days" is a window
    on the future. They are still counted in `summary()["expired"]`.
    """
    stmt = (
        select(
            Asset.id,
            Asset.name,
            Vendor.name.label("vendor"),
            Department.name.label("department"),
            Warranty.end_date,
        )
        .select_from(Asset)
        # INNER join here: no warranty means no expiry date to list.
        .join(
            Warranty,
            and_(
                Warranty.asset_id == Asset.id,
                Warranty.workspace_id == workspace_id,
            ),
        )
        # OUTER: vendor and department are optional on an asset.
        .outerjoin(Vendor, Asset.vendor_id == Vendor.id)
        .outerjoin(Department, Asset.department_id == Department.id)
        .where(
            Asset.workspace_id == workspace_id,
            Warranty.end_date >= today,
            Warranty.end_date <= soon_cutoff(today, days),
        )
    )
    rows = db.execute(
        _scoped_to(stmt, assigned_to_user_id).order_by(Warranty.end_date, Asset.name)
    ).all()

    return [
        {
            "asset_id": asset_id,
            "name": name,
            "vendor": vendor,
            "department": department,
            # Default window on purpose — see the docstring above.
            "status": compute_status(end_date, today),
            "end_date": end_date,
        }
        for asset_id, name, vendor, department, end_date in rows
    ]

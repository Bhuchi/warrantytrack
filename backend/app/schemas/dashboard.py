"""Response shapes for the Dashboard endpoints.

Mirrors `GET /dashboard/summary` and `GET /dashboard/expiring` in docs/api.md.
The Dashboard screen (D04) is already built against these names in
frontend/src/features/dashboard/getDashboard.ts, so the field names here are
the contract — change them in api.md and the TypeScript types in the same PR.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.services.warranty import WarrantyStatus


class DepartmentCount(BaseModel):
    """One slice of the by-department chart."""

    department_id: uuid.UUID
    name: str
    count: int


class DashboardSummary(BaseModel):
    """The cards and the chart in one response.

    `no_warranty` is the same set of assets the status rule calls `unknown` —
    see the rename note in app/services/dashboard.py.
    """

    total: int
    active: int
    expiring_soon: int
    expired: int
    no_warranty: int
    by_department: list[DepartmentCount]


class ExpiringAsset(BaseModel):
    """One row of the expiring table. `vendor`/`department` are names, not ids.

    The table shows text, so the join is done once in SQL rather than making
    the browser resolve ids. Both are optional because an asset need not have
    either.
    """

    asset_id: uuid.UUID
    name: str
    vendor: str | None
    department: str | None
    end_date: date
    status: WarrantyStatus


class ExpiringList(BaseModel):
    items: list[ExpiringAsset]

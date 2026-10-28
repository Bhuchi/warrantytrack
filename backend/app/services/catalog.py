"""Query logic for the four catalog lists.

Routes stay thin: they say *which* list and *whose* workspace, and hand off
here. All SQL lives in services, so the logic is testable without HTTP and
reusable — the bulk importer will call the same lookup to turn a spreadsheet's
"Laptop" into a category_id.

The four models are structurally identical (app/models/catalog.py), so this is
one generic function rather than four copies. The TypeVar is what keeps that
generic without losing the return type: pass `Category`, get `list[Category]`.
"""

from __future__ import annotations

import uuid
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Category, Department, Location, Vendor

# Constrained to the four lookup tables — anything else is a mistake, and
# naming them here means a new catalog table has to be added deliberately.
CatalogModel = TypeVar("CatalogModel", Category, Vendor, Department, Location)


def list_for_workspace(
    db: Session, model: type[CatalogModel], workspace_id: uuid.UUID
) -> list[CatalogModel]:
    """Every row of one catalog list in one workspace, A-Z.

    Scoped by `workspace_id` — the house rule from docs/architecture.md, and
    the reason one organization never sees another's department names. The
    filter matches `ix_<table>_workspace_id`, so Postgres uses that index.

    Sorted by name because the only consumer is a dropdown, where alphabetical
    is what a user expects. Sorting in SQL rather than in Python keeps it
    correct if this ever needs a LIMIT.
    """
    return list(
        db.scalars(
            select(model)
            .where(model.workspace_id == workspace_id)
            .order_by(model.name)
        )
    )

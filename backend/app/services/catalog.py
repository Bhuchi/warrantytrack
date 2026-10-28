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

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import Category, Department, Location, Vendor

# Constrained to the four lookup tables — anything else is a mistake, and
# naming them here means a new catalog table has to be added deliberately.
CatalogModel = TypeVar("CatalogModel", Category, Vendor, Department, Location)


class DuplicateCatalogName(Exception):
    """This workspace already has a row with that name in that list."""


def _find_by_name(
    db: Session, model: type[CatalogModel], workspace_id: uuid.UUID, name: str
) -> CatalogModel | None:
    """Case-insensitive lookup within one workspace.

    The unique constraint is case-sensitive, so "power buy" and "Power Buy"
    could both be stored — and the dashboard would then count them as two
    vendors. Matching without case is what stops that, both here and in
    `get_or_create`.
    """
    return db.scalars(
        select(model).where(
            model.workspace_id == workspace_id,
            func.lower(model.name) == name.lower(),
        )
    ).first()


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


def get_or_create(
    db: Session, model: type[CatalogModel], workspace_id: uuid.UUID, name: str
) -> CatalogModel:
    """Find a catalog row by name in this workspace, or create it.

    This is what lets `POST /assets` accept a vendor *name*. The Add Asset form
    collects free text and OCR returns "Power Buy", not a UUID
    (frontend/src/features/add-asset/draft.ts), and bulk import will read the
    same names out of a spreadsheet — so the backend has to be able to turn a
    name into a row.

    The lookup is **case-insensitive** but the row is created with the caller's
    capitalisation. The unique constraint is case-sensitive, so without this
    "power buy" from a receipt would happily become a second vendor alongside
    "Power Buy" and the dashboard would count them separately.

    The INSERT runs in a savepoint: if another request creates the same name
    between our SELECT and our INSERT, the constraint fires, we roll back just
    that savepoint rather than the caller's whole transaction, and return the
    row that won.
    """
    cleaned = name.strip()

    existing = _find_by_name(db, model, workspace_id, cleaned)
    if existing is not None:
        return existing

    row = model(workspace_id=workspace_id, name=cleaned)
    try:
        with db.begin_nested():
            db.add(row)
    except IntegrityError:
        # Lost the race — the other writer's row is the one that exists.
        winner = _find_by_name(db, model, workspace_id, cleaned)
        if winner is None:  # pragma: no cover - the constraint just fired
            raise
        return winner

    return row


def create(
    db: Session, model: type[CatalogModel], workspace_id: uuid.UUID, name: str
) -> CatalogModel:
    """Add a row to one catalog list, or raise if the name is taken.

    Deliberately not `get_or_create`. That one is for the asset write path,
    where "Power Buy" arriving on a receipt should quietly attach to the vendor
    that already exists. Here the user is explicitly adding to a list they can
    see, so a name already on it is a mistake worth telling them about — the
    route turns this into 409.
    """
    cleaned = name.strip()

    if _find_by_name(db, model, workspace_id, cleaned) is not None:
        raise DuplicateCatalogName(cleaned)

    row = model(workspace_id=workspace_id, name=cleaned)
    db.add(row)
    db.flush()
    return row

"""Catalog routes (Leg A) — the lists the asset pickers are built from.

Four resources, one file, because the four tables are identical in shape. Each
gets its own router so main.py keeps defining every path in exactly one place,
the same way /notifications does.

Reading is open to everyone in the workspace — an employee filling in the Add
Asset form needs the same pickers as an admin. Writing is owner/admin only,
matching "Organization Administrator ... manages departments, locations,
vendors, asset categories" in the requirements.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace, require_manager
from app.db.session import get_db
from app.models.catalog import Category, Department, Location, Vendor
from app.models.membership import Membership
from app.schemas.catalog import (
    CatalogCreate,
    CatalogItem,
    CatalogList,
    CatalogUpdate,
)
from app.services import catalog as catalog_service
from app.services.catalog import DuplicateCatalogName

#: The four interchangeable lookup models these routes operate on.
CatalogType = type[Category] | type[Vendor] | type[Department] | type[Location]

# No prefix here — main.py mounts each router at its own path, so the
# collection root is "".
categories_router = APIRouter(tags=["catalog"])
vendors_router = APIRouter(tags=["catalog"])
departments_router = APIRouter(tags=["catalog"])
locations_router = APIRouter(tags=["catalog"])


def _taken(name: str) -> HTTPException:
    """The 409 raised when a name is already on this workspace's list."""
    return HTTPException(
        status_code=http_status.HTTP_409_CONFLICT,
        detail=f"'{name}' is already in this list.",
    )


def _load(
    db: Session, model: CatalogType, membership: Membership, row_id: uuid.UUID
) -> Category | Vendor | Department | Location:
    """Fetch one row in the caller's workspace, or 404.

    One lookup for both PATCH and DELETE, so neither can forget the workspace
    filter — which is the only thing standing between a stray id and another
    tenant's data.
    """
    row = catalog_service.get(db, model, membership.workspace_id, row_id)
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found"
        )
    return row


def _create(
    db: Session, model: CatalogType, membership: Membership, data: CatalogCreate
) -> CatalogItem:
    """Shared body for the four POST routes.

    The routes stay separate so each gets its own path, docstring and OpenAPI
    entry; only the part that would be copied four times verbatim lives here.
    """
    try:
        row = catalog_service.create(db, model, membership.workspace_id, data.name)
    except DuplicateCatalogName as error:
        raise _taken(error.args[0]) from None

    db.commit()
    return CatalogItem.model_validate(row)


def _rename(
    db: Session,
    model: CatalogType,
    membership: Membership,
    row_id: uuid.UUID,
    data: CatalogUpdate,
) -> CatalogItem:
    """Shared body for the four PATCH routes."""
    row = _load(db, model, membership, row_id)

    try:
        catalog_service.rename(db, model, row, data.name)
    except DuplicateCatalogName as error:
        raise _taken(error.args[0]) from None

    db.commit()
    return CatalogItem.model_validate(row)


def _delete(
    db: Session, model: CatalogType, membership: Membership, row_id: uuid.UUID
) -> None:
    """Shared body for the four DELETE routes."""
    catalog_service.delete(db, _load(db, model, membership, row_id))
    db.commit()


@categories_router.get("", response_model=CatalogList)
def list_categories(
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
) -> CatalogList:
    """GET /categories — what kind of thing an asset is ("Laptop", "Monitor").

    FastAPI resolves the two Depends() first (a session, which workspace the
    caller is acting in), then runs this body. `response_model` validates the
    output against the contract, so drifting from CatalogList is a 500 here
    rather than a silent surprise in the frontend.
    """
    return CatalogList(
        items=catalog_service.list_for_workspace(db, Category, workspace_id)
    )


@categories_router.post(
    "", response_model=CatalogItem, status_code=http_status.HTTP_201_CREATED
)
def create_category(
    data: CatalogCreate,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> CatalogItem:
    """POST /categories — add a category. Owner or admin only.

    409 if the name is already on this workspace's list, matched without
    regard to case so "laptop" cannot join "Laptop".
    """
    return _create(db, Category, membership, data)


@vendors_router.get("", response_model=CatalogList)
def list_vendors(
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
) -> CatalogList:
    """GET /vendors — who the asset was bought from ("Power Buy", "JIB")."""
    return CatalogList(
        items=catalog_service.list_for_workspace(db, Vendor, workspace_id)
    )


@vendors_router.post(
    "", response_model=CatalogItem, status_code=http_status.HTTP_201_CREATED
)
def create_vendor(
    data: CatalogCreate,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> CatalogItem:
    """POST /vendors — add a vendor. Owner or admin only.

    Note that `POST /assets` also creates vendors, by name, when the Add Asset
    form sends one that does not exist yet. This endpoint is for managing the
    list directly rather than as a side effect of saving an asset.
    """
    return _create(db, Vendor, membership, data)


@departments_router.get("", response_model=CatalogList)
def list_departments(
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
) -> CatalogList:
    """GET /departments — which part of the organization holds the asset.

    A personal workspace will simply have none of these, which is why the
    response is an empty list rather than an error.
    """
    return CatalogList(
        items=catalog_service.list_for_workspace(db, Department, workspace_id)
    )


@departments_router.post(
    "", response_model=CatalogItem, status_code=http_status.HTTP_201_CREATED
)
def create_department(
    data: CatalogCreate,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> CatalogItem:
    """POST /departments — add a department. Owner or admin only.

    Until this existed there was no way to create one at all: `POST /assets`
    takes a `department_id` but never makes the row. That left the dashboard's
    `by_department` breakdown permanently empty, since it joins this table.
    """
    return _create(db, Department, membership, data)


@locations_router.get("", response_model=CatalogList)
def list_locations(
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
) -> CatalogList:
    """GET /locations — the site picker ("HQ Floor 3").

    Not the same as `assets.location`, which is free text for the spot inside
    a site ("Shelf B2"). See docs/erd.md.
    """
    return CatalogList(
        items=catalog_service.list_for_workspace(db, Location, workspace_id)
    )


@locations_router.post(
    "", response_model=CatalogItem, status_code=http_status.HTTP_201_CREATED
)
def create_location(
    data: CatalogCreate,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> CatalogItem:
    """POST /locations — add a site. Owner or admin only.

    A site ("HQ Floor 3"), not the free-text spot inside it ("Shelf B2") that
    lives on the asset as `location`. See docs/erd.md.
    """
    return _create(db, Location, membership, data)


@categories_router.patch("/{row_id}", response_model=CatalogItem)
def rename_category(
    row_id: uuid.UUID,
    data: CatalogUpdate,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> CatalogItem:
    """PATCH /categories/{id} — rename a category. Owner or admin only.

    409 if another row already has that name. Re-sending the row's own name
    succeeds: it does not clash with itself.
    """
    return _rename(db, Category, membership, row_id, data)


@categories_router.delete("/{row_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_category(
    row_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> None:
    """DELETE /categories/{id} — remove a category. Owner or admin only.

    Assets in this category keep working — `assets.category_id` is
    `ON DELETE SET NULL`, so they simply become uncategorised.
    """
    _delete(db, Category, membership, row_id)


@vendors_router.patch("/{row_id}", response_model=CatalogItem)
def rename_vendor(
    row_id: uuid.UUID,
    data: CatalogUpdate,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> CatalogItem:
    """PATCH /vendors/{id} — rename a vendor. Owner or admin only.

    409 if another row already has that name. Re-sending the row's own name
    succeeds: it does not clash with itself.
    """
    return _rename(db, Vendor, membership, row_id, data)


@vendors_router.delete("/{row_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_vendor(
    row_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> None:
    """DELETE /vendors/{id} — remove a vendor. Owner or admin only.

    Assets bought from this vendor keep working; they simply lose the
    vendor. `POST /assets` will recreate it by name if a later receipt
    mentions it again.
    """
    _delete(db, Vendor, membership, row_id)


@departments_router.patch("/{row_id}", response_model=CatalogItem)
def rename_department(
    row_id: uuid.UUID,
    data: CatalogUpdate,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> CatalogItem:
    """PATCH /departments/{id} — rename a department. Owner or admin only.

    409 if another row already has that name. Re-sending the row's own name
    succeeds: it does not clash with itself.
    """
    return _rename(db, Department, membership, row_id, data)


@departments_router.delete("/{row_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_department(
    row_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> None:
    """DELETE /departments/{id} — remove a department. Owner or admin only.

    Assets in this department keep working, and the dashboard's
    `by_department` breakdown stops listing it.
    """
    _delete(db, Department, membership, row_id)


@locations_router.patch("/{row_id}", response_model=CatalogItem)
def rename_location(
    row_id: uuid.UUID,
    data: CatalogUpdate,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> CatalogItem:
    """PATCH /locations/{id} — rename a site. Owner or admin only.

    409 if another row already has that name. Re-sending the row's own name
    succeeds: it does not clash with itself.
    """
    return _rename(db, Location, membership, row_id, data)


@locations_router.delete("/{row_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_location(
    row_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> None:
    """DELETE /locations/{id} — remove a site. Owner or admin only.

    Assets at this site keep working. Their free-text `location`
    ("Shelf B2") is a separate column and is untouched.
    """
    _delete(db, Location, membership, row_id)

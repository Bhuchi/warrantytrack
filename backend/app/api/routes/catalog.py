"""Catalog routes (Leg A) — the lists the asset pickers are built from.

Four resources, one file, because the four tables are identical in shape. Each
gets its own router so main.py keeps defining every path in exactly one place,
the same way /notifications does.

Read-only for now. Nothing in the frontend creates or edits these yet — there
is no catalog-management screen — so the write half is deliberately left for
the ticket that needs it (bulk import, which has to create missing rows).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace
from app.db.session import get_db
from app.models.catalog import Category, Department, Location, Vendor
from app.schemas.catalog import CatalogList
from app.services import catalog as catalog_service

# No prefix here — main.py mounts each router at its own path, so the
# collection root is "".
categories_router = APIRouter(tags=["catalog"])
vendors_router = APIRouter(tags=["catalog"])
departments_router = APIRouter(tags=["catalog"])
locations_router = APIRouter(tags=["catalog"])


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


@vendors_router.get("", response_model=CatalogList)
def list_vendors(
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
) -> CatalogList:
    """GET /vendors — who the asset was bought from ("Power Buy", "JIB")."""
    return CatalogList(
        items=catalog_service.list_for_workspace(db, Vendor, workspace_id)
    )


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

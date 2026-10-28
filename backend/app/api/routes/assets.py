"""Asset routes (Leg A). Contract: docs/api.md -> Assets.

Read endpoints only for now. The write half (POST / PATCH / DELETE) waits on
three decisions that are still open — who computes `warranty.end_date`,
whether POST accepts a vendor name or an id, and which fields are truly
required — so it lands in a later PR rather than being guessed at here.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace
from app.db.session import get_db
from app.schemas.asset import AssetDetail, AssetList, AssetListItem
from app.services import asset as asset_service
from app.services.warranty import WarrantyStatus

# No prefix here — main.py mounts this router at "/assets", so the collection
# root is "".
router = APIRouter(tags=["assets"])


@router.get("", response_model=AssetList)
def list_assets(
    q: str | None = Query(
        None, description="Matches name, serial number or invoice number."
    ),
    warranty_status: WarrantyStatus | None = Query(
        None,
        alias="status",
        description="Filter by computed warranty status.",
    ),
    category_id: uuid.UUID | None = Query(None),
    vendor_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
) -> AssetList:
    """GET /assets — one page of the Assets List (D05).

    The query parameter is `status`, matching the contract; it is named
    `warranty_status` in Python because `status` is also the name of
    FastAPI's status module, which this file imports.

    `page_size` is capped at 100 so a single request cannot ask for the whole
    table and tie up a worker.
    """
    total, assets = asset_service.list_assets(
        db,
        workspace_id,
        q=q,
        status=warranty_status,
        category_id=category_id,
        vendor_id=vendor_id,
        page=page,
        page_size=page_size,
    )

    return AssetList(
        items=[AssetListItem.from_asset(asset) for asset in assets],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{asset_id}", response_model=AssetDetail)
def get_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
) -> AssetDetail:
    """GET /assets/{id} — one asset in full (D08).

    404 covers both "no such asset" and "in a workspace you do not belong
    to". That is deliberate and there is a test for it: a 403 would confirm
    the record exists to someone who should not know. See docs/api.md.
    """
    asset = asset_service.get_asset(db, workspace_id, asset_id)

    if asset is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )

    return AssetDetail.from_asset(asset)

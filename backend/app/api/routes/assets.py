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

from app.api.deps import (
    employee_scope,
    get_current_membership,
    get_current_user,
    get_current_workspace,
)
from app.models.membership import Membership, MembershipRole
from app.db.session import get_db
from app.schemas.asset import (
    AssetCreate,
    AssetDetail,
    AssetList,
    AssetListItem,
    AssetUpdate,
)
from app.services import asset as asset_service
from app.services.asset import DuplicateSerialNumber, UnknownDocument
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
    membership: Membership = Depends(get_current_membership),
) -> AssetList:
    """GET /assets — one page of the Assets List (D05).

    An employee sees only the assets assigned to them, so their `total` is
    their own count rather than the organization's. `employee_scope()` decides
    that, not this route — the same way the dashboard does it.

    The query parameter is `status`, matching the contract; it is named
    `warranty_status` in Python because `status` is also the name of
    FastAPI's status module, which this file imports.

    `page_size` is capped at 100 so a single request cannot ask for the whole
    table and tie up a worker.
    """
    total, assets = asset_service.list_assets(
        db,
        membership.workspace_id,
        q=q,
        status=warranty_status,
        category_id=category_id,
        vendor_id=vendor_id,
        page=page,
        page_size=page_size,
        assigned_to_user_id=employee_scope(membership),
    )

    return AssetList(
        items=[AssetListItem.from_asset(asset) for asset in assets],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=AssetDetail, status_code=http_status.HTTP_201_CREATED)
def create_asset(
    data: AssetCreate,
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
    user_id: uuid.UUID = Depends(get_current_user),
) -> AssetDetail:
    """POST /assets — manual entry (D06) or a confirmed single OCR result.

    `workspace_id` and `created_by_user_id` come from the dependencies, never
    from the request body: a caller must not be able to file an asset into
    someone else's workspace by sending its id.

    Returns the same shape as `GET /assets/{id}`, so the wizard can show the
    saved asset without a second round trip.
    """
    try:
        asset = asset_service.create_asset(db, workspace_id, user_id, data)
    except DuplicateSerialNumber:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"An asset with serial number {data.serial_number} already exists.",
        ) from None
    except UnknownDocument as error:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown document_ids: {', '.join(error.args[0])}",
        ) from None

    db.commit()

    # Read back after the commit so the response reflects what is actually
    # stored, with every relationship the detail shape needs loaded.
    created = asset_service.get_asset(db, workspace_id, asset.id)
    if created is None:  # pragma: no cover - it was just committed
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Asset could not be read back after creation.",
        )

    return AssetDetail.from_asset(created)


@router.get("/{asset_id}", response_model=AssetDetail)
def get_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> AssetDetail:
    """GET /assets/{id} — one asset in full (D08).

    404 covers "no such asset", "in a workspace you do not belong to" and, for
    an employee, "not assigned to you". That is deliberate and there is a test
    for it: a 403 would confirm the record exists to someone who should not
    know. See docs/api.md.
    """
    asset = asset_service.get_asset(
        db,
        membership.workspace_id,
        asset_id,
        assigned_to_user_id=employee_scope(membership),
    )

    if asset is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )

    return AssetDetail.from_asset(asset)


@router.delete("/{asset_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> None:
    """DELETE /assets/{id} — owners and admins only (docs/api.md).

    The two failure codes mean different things and the order they are checked
    in matters:

    - `get_current_membership` raises **404** if the caller has no membership
      in this workspace at all. Not 403 — that would confirm the workspace
      exists.
    - An employee who *is* a member gets **403**: they belong here, they are
      just not allowed to delete. This is checked before the asset is looked
      up, so the answer does not depend on whether the id exists and cannot be
      used to probe for one.
    - A missing asset, or one in another workspace, is **404**.

    Deletion is permanent — there is no soft-delete column anywhere in the
    schema (docs/erd.md). If the team wants assets archived instead, that is a
    migration and a contract change, not a flag here.
    """
    if membership.role is MembershipRole.employee:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only an owner or admin can delete an asset.",
        )

    asset = asset_service.get_asset(db, membership.workspace_id, asset_id)

    if asset is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )

    asset_service.delete_asset(db, asset)
    db.commit()


@router.patch("/{asset_id}", response_model=AssetDetail)
def update_asset(
    asset_id: uuid.UUID,
    data: AssetUpdate,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> AssetDetail:
    """PATCH /assets/{id} — change any subset of the create fields.

    Fetching through the same scope as `GET` is what makes an asset belonging
    to someone else a 404 rather than an edit: there is no path here that
    reaches a row the caller cannot already read. For an employee that means
    they may edit the assets assigned to them and nothing else —
    docs/architecture.md says they "may only touch" those, and editing is
    touching.
    """
    workspace_id = membership.workspace_id
    asset = asset_service.get_asset(
        db, workspace_id, asset_id, assigned_to_user_id=employee_scope(membership)
    )

    if asset is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )

    try:
        asset_service.update_asset(db, asset, data)
    except DuplicateSerialNumber:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"An asset with serial number {data.serial_number} already exists.",
        ) from None

    db.commit()

    updated = asset_service.get_asset(db, workspace_id, asset_id)
    if updated is None:  # pragma: no cover - it was just committed
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Asset could not be read back after update.",
        )

    return AssetDetail.from_asset(updated)

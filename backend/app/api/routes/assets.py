"""Asset routes (Leg A). Contract: docs/api.md -> Assets.

Read endpoints only for now. The write half (POST / PATCH / DELETE) waits on
three decisions that are still open — who computes `warranty.end_date`,
whether POST accepts a vendor name or an id, and which fields are truly
required — so it lands in a later PR rather than being guessed at here.
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status as http_status,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import (
    employee_scope,
    get_current_membership,
    get_current_user,
    get_current_workspace,
    require_manager,
)
from app.models.membership import Membership
from app.db.session import get_db
from app.schemas.asset import (
    AssetAssign,
    AssetCreate,
    AssetDetail,
    AssetList,
    AssetListItem,
    AssetUpdate,
    PhotoPresignRequest,
    PhotoPresignResponse,
)
from app.schemas.asset_import import (
    ImportCommitResponse,
    ImportMode,
    ImportValidateResponse,
)
from app.schemas.serial_scan import SerialScanResponse
from app.services import asset as asset_service
from app.services import asset_import
from app.services import asset_photo, ocr, storage
from app.services import asset_validation
from app.services.asset import DuplicateSerialNumber, UnknownDocument
from app.services.asset_validation import AssetValidationError
from app.core.config import settings
from app.services.warranty import WarrantyStatus

# No prefix here — main.py mounts this router at "/assets", so the collection
# root is "".
router = APIRouter(tags=["assets"])

_MAX_SERIAL_SCAN_BYTES = 10 * 1024 * 1024
_SERIAL_SCAN_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/scan-serial", response_model=SerialScanResponse)
async def scan_serial_number(
    request: Request,
    _membership: Membership = Depends(get_current_membership),
) -> SerialScanResponse:
    """POST /assets/scan-serial — read a device's serial label with Bedrock.

    The photo is sent as the raw request body to avoid a multipart dependency.
    It is used for this request only and is not stored. Auth and workspace
    membership are required because each inference call can incur AWS cost.
    """
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in _SERIAL_SCAN_CONTENT_TYPES:
        raise HTTPException(
            status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Use a JPEG, PNG, or WebP photo of the serial label.",
        )

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > _MAX_SERIAL_SCAN_BYTES:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Photo must be 10 MB or smaller.",
        )

    photo = bytearray()
    async for chunk in request.stream():
        photo.extend(chunk)
        if len(photo) > _MAX_SERIAL_SCAN_BYTES:
            raise HTTPException(
                status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Photo must be 10 MB or smaller.",
            )
    if not photo:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Choose a photo of the serial label.",
        )

    try:
        serial = await run_in_threadpool(ocr.extract_serial_number, bytes(photo))
    except ocr.InvalidImage as error:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="We could not read that image. Try a clear JPEG, PNG, or WebP photo.",
        ) from error
    except ocr.BedrockUnavailable as error:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except ocr.OcrError as error:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Bedrock could not read the serial label. Please enter it manually.",
        ) from error

    if serial is None:
        return SerialScanResponse(
            serial=None,
            error="No clear serial number found. Try a closer photo of the whole label or enter it manually.",
        )
    return SerialScanResponse(serial=serial)


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
    except AssetValidationError as error:
        # Handed through in FastAPI's own 422 shape, so a caller cannot tell
        # these from the schema's own errors — `loc[1]` names the field either
        # way, which is what the form needs to show it inline.
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.detail,
        ) from None
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


#: Same ceiling as receipts (PUT /documents/{id}/dev-upload).
_MAX_DEV_PHOTO_BYTES = 15 * 1024 * 1024


@router.post("/photos/presign", response_model=PhotoPresignResponse)
def presign_photo(
    data: PhotoPresignRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> PhotoPresignResponse:
    """POST /assets/photos/presign — somewhere to upload a box / storage photo.

    Then PUT the photo to `upload_url` and send `key` as `location_image_key`
    on POST or PATCH /assets. Images only.
    """
    try:
        key, upload_url = asset_photo.reserve(
            db, membership.workspace_id, membership.user_id, data.filename, data.content_type
        )
    except asset_photo.NotAPhoto:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{
                "type": "value_error",
                "loc": ["body", "content_type"],
                "msg": "Upload a JPG, PNG, WEBP or HEIC photo.",
            }],
        ) from None
    except storage.StorageError as error:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from None
    return PhotoPresignResponse(upload_url=upload_url, key=key)


@router.put("/photos/dev-upload", status_code=http_status.HTTP_204_NO_CONTENT)
async def dev_upload_photo(
    request: Request,
    key: str = Query(max_length=1024),
    membership: Membership = Depends(get_current_membership),
) -> Response:
    """Accept a photo directly. **Development only**, like the receipt one.

    404 on any other backend: in production the browser PUTs to S3.
    """
    if settings.storage_backend != "local":
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")
    if not asset_photo.owns(membership.workspace_id, key):
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Empty upload.")
    if len(body) > _MAX_DEV_PHOTO_BYTES:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Photo is larger than 15MB.",
        )
    await run_in_threadpool(storage.write_local, key, body)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.get("/photos/dev-view")
def dev_view_photo(
    key: str = Query(max_length=1024),
    expires: int = Query(),
    signature: str = Query(max_length=128),
) -> Response:
    """Serve a photo from local storage. **Development only.**

    The local twin of the presigned S3 GET in `location_image_url`. No login,
    because an `<img>` sends no auth headers; the signed, expiring query
    string stands in for it, as S3's own signature does in production.
    """
    if settings.storage_backend != "local":
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")
    if not asset_photo.dev_view_allowed(key, expires, signature):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="This link has expired or is not valid.",
        )
    try:
        body = storage.read_bytes(key)
    except storage.StorageError:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found") from None
    return Response(content=body, media_type=asset_photo.content_type_of(key))


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


#: The same ceiling PUT /documents/{id}/dev-upload uses. A spreadsheet that
#: large is not a spreadsheet, and the body is held in memory while it parses.
_MAX_IMPORT_BYTES = 15 * 1024 * 1024


@router.post("/import")
async def import_assets(
    request: Request,
    mode: ImportMode = Query(
        ...,
        description="validate runs a dry run and writes nothing; commit creates "
        "the rows that pass.",
    ),
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> ImportValidateResponse | ImportCommitResponse:
    """POST /assets/import — create many assets from a spreadsheet.

    Owner/admin only, per the requirements: bulk import is an organization
    administrator's job.

    The file arrives as the **raw request body**, not multipart, following
    `PUT /documents/{id}/dev-upload`: FastAPI's `UploadFile` needs
    `python-multipart`, which is not a dependency, and the repo already chose
    to avoid it once for the same reason.

    CSV or `.xlsx`, told apart by the bytes rather than by `Content-Type` —
    which browsers and curl get wrong constantly, and which a raw-body upload
    gives no filename to fall back on.

    Two modes over one implementation. `validate` is `commit` with the writes
    skipped, so a dry run cannot report a row as valid that the real run then
    rejects.

    Rows are judged by the same rules as `POST /assets` — this endpoint owns
    no validation of its own. A row rejected here would have been rejected
    there, with the same wording.

    A whole-file problem (not UTF-8, missing a required column, past the row
    limit) is a **422 with a plain message**: there is no row to blame.
    """
    raw = await request.body()

    if not raw:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail="Empty upload."
        )
    if len(raw) > _MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is larger than 15MB.",
        )

    try:
        rows = asset_import.parse(raw)
    except asset_import.ImportError_ as error:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from None

    # Off the event loop: the session is synchronous and a thousand rows is a
    # few thousand queries, which would otherwise stall every other request
    # for the duration. Starlette runs sync dependencies this way already.
    report = await run_in_threadpool(
        asset_import.run_import,
        db,
        membership.workspace_id,
        membership.user_id,
        rows,
        commit=mode is ImportMode.commit,
    )
    errors = [error.as_dict() for error in report.errors]

    if mode is ImportMode.commit:
        db.commit()
        return ImportCommitResponse(
            created=report.created, skipped=report.skipped, errors=errors
        )

    return ImportValidateResponse(
        total_rows=report.total_rows, valid=report.valid, errors=errors
    )


@router.post("/{asset_id}/assign", response_model=AssetDetail)
def assign_asset(
    asset_id: uuid.UUID,
    data: AssetAssign,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> AssetDetail:
    """POST /assets/{id}/assign — give an asset to an employee, or take it back.

    Owners and admins only; `null` unassigns. Reassigning is the same call with
    a different id, so assign, reassign and unassign cannot drift apart.

    Three different answers for three different problems:

    - **403** — an employee: they belong to this workspace but may not hand
      assets around. Settled by `require_manager` before the asset is looked
      up, so it cannot be used to probe for ids.
    - **404** — no such asset, or one in another workspace.
    - **422** — the proposed assignee is not a member of this workspace.
      Checked through the same `validate_references` the create and edit paths
      use, so "who may hold an asset" has one definition.
    """
    asset = asset_service.get_asset(db, membership.workspace_id, asset_id)

    if asset is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )

    try:
        asset_validation.validate_references(db, membership.workspace_id, data)
    except AssetValidationError as error:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.detail,
        ) from None

    asset_service.assign_asset(db, asset, data.assigned_to_user_id)
    db.commit()

    updated = asset_service.get_asset(db, membership.workspace_id, asset_id)
    if updated is None:  # pragma: no cover - it was just committed
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Asset could not be read back after assignment.",
        )

    return AssetDetail.from_asset(updated)


@router.delete("/{asset_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(require_manager),
) -> None:
    """DELETE /assets/{id} — owners and admins only (docs/api.md).

    The two failure codes mean different things and the order they are checked
    in matters:

    - **404** if the caller has no membership in this workspace at all. Not
      403 — that would confirm the workspace exists.
    - **403** for an employee who *is* a member: they belong here, they are
      just not allowed to delete. `require_manager` is a dependency, so this
      is settled before the route body runs and before the asset is looked up
      — the answer cannot be used to probe for which ids exist.
    - A missing asset, or one in another workspace, is **404**.

    Deletion is permanent — there is no soft-delete column anywhere in the
    schema (docs/erd.md). If the team wants assets archived instead, that is a
    migration and a contract change, not a flag here.
    """
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
    except AssetValidationError as error:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.detail,
        ) from None
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

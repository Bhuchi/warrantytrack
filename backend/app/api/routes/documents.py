"""Documents and OCR routes (Leg B). Contract: docs/api.md -> Documents and OCR."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.api.deps import employee_scope, get_current_membership
from app.core.config import settings
from app.db.session import get_db
from app.models.membership import Membership
from app.schemas.document import (
    ConfirmRequest,
    ConfirmResponse,
    DocumentDownload,
    DocumentRead,
    PresignRequest,
    PresignResponse,
)
from app.services import document as document_service
from app.services import storage
from app.services.asset_validation import AssetValidationError

# No prefix here — main.py mounts this router at "/documents".
router = APIRouter(tags=["documents"])

# Uploads are capped so a dev-mode PUT cannot fill the container's disk. The
# real path is presigned S3, where the limit belongs in the bucket policy.
_MAX_DEV_UPLOAD_BYTES = 15 * 1024 * 1024


@router.post(
    "/presign", response_model=PresignResponse, status_code=http_status.HTTP_200_OK
)
def presign_upload(
    data: PresignRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> PresignResponse:
    """POST /documents/presign — reserve a key and hand back an upload URL.

    The row is created now, before the file exists, so the key is claimed by
    this workspace and this user. Nothing else can later submit it.
    """
    document = document_service.create_for_upload(
        db,
        membership.workspace_id,
        membership.user_id,
        filename=data.filename,
        content_type=data.content_type,
        kind=data.kind,
    )
    db.commit()
    return PresignResponse(
        document_id=document.id,
        upload_url=document_service.upload_url_for(document),
        s3_key=document.s3_key,
    )


@router.put("/{document_id}/dev-upload", status_code=http_status.HTTP_204_NO_CONTENT)
async def dev_upload(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> Response:
    """Accept the file directly. **Development only.**

    Exists so the upload → OCR → confirm flow can be run and demoed without an
    AWS account, which is also why `STORAGE_BACKEND` defaults to `local`. In
    production the browser PUTs to S3 and this route refuses to answer at all —
    a file passing through the API is exactly what Decision 3 avoids.
    """
    if settings.storage_backend != "local":
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found"
        )

    document = _visible_or_404(db, membership, document_id)

    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail="Empty upload."
        )
    if len(body) > _MAX_DEV_UPLOAD_BYTES:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is larger than 15MB.",
        )

    storage.write_local(document.s3_key, body)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.post(
    "/{document_id}/submit",
    response_model=DocumentRead,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def submit_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> DocumentRead:
    """POST /documents/{id}/submit — the upload is finished, start extraction.

    202 with the current row, then the browser polls `GET /documents/{id}`.
    Extraction is still synchronous (see the service), so the first poll will
    usually already say `extracted` — the contract is written for the async
    version that replaces it.

    A failed extraction is **not** an error here: the row carries `failed` and
    the reason, which is what the review screen shows. Only a file that was
    never uploaded is a 4xx, because that is the client's mistake.
    """
    document = _visible_or_404(db, membership, document_id)
    try:
        document = document_service.submit(db, document)
    except document_service.DocumentNotUploaded:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Nothing has been uploaded for this document yet.",
        ) from None
    except storage.StorageError as error:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from None

    db.commit()
    return DocumentRead(**document_service.as_api_dict(document))


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> DocumentRead:
    """GET /documents/{id} — poll OCR status and read the extracted fields."""
    document = _visible_or_404(db, membership, document_id)
    return DocumentRead(**document_service.as_api_dict(document))


@router.get("/{document_id}/download", response_model=DocumentDownload)
def download_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> DocumentDownload:
    """GET /documents/{id}/download — a short-lived link to open the file.

    Same visibility as `GET /documents/{id}`, so an employee cannot open a
    colleague's receipt. 404 also when nothing was ever uploaded, because
    there is nothing to open.
    """
    document = _visible_or_404(db, membership, document_id)
    try:
        url = document_service.download_url_for(document)
    except document_service.DocumentFileMissing:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Nothing has been uploaded for this document.",
        ) from None
    except storage.StorageError as error:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from None
    return DocumentDownload(url=url, expires_in=settings.presigned_url_ttl_seconds)


@router.get("/{document_id}/dev-download")
def dev_download(
    document_id: uuid.UUID,
    expires: int = Query(),
    signature: str = Query(max_length=128),
    db: Session = Depends(get_db),
) -> Response:
    """Serve the file from local storage. **Development only.**

    The local-backend twin of a presigned S3 GET, so the download button can
    be tried with docker compose. There is no login here because a new browser
    tab sends no auth headers; the signed, expiring query string from
    `GET /documents/{id}/download` stands in for it, exactly as S3's own
    signature does in production. Refuses to answer on any other backend.
    """
    if settings.storage_backend != "local":
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found"
        )
    if not document_service.dev_download_allowed(document_id, expires, signature):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="This link has expired or is not valid.",
        )

    try:
        document, body = document_service.read_for_dev_download(db, document_id)
    except (document_service.DocumentNotFound, document_service.DocumentFileMissing):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from None

    headers = {}
    disposition = storage.inline_disposition(document.filename)
    if disposition:
        headers["Content-Disposition"] = disposition
    return Response(
        content=body,
        media_type=document.content_type or "application/octet-stream",
        headers=headers,
    )


@router.post(
    "/{document_id}/confirm",
    response_model=ConfirmResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def confirm_document(
    document_id: uuid.UUID,
    data: ConfirmRequest,
    db: Session = Depends(get_db),
    membership: Membership = Depends(get_current_membership),
) -> ConfirmResponse:
    """POST /documents/{id}/confirm — create the assets the user approved.

    One entry per asset kept, so a three-line invoice creates three assets, all
    linked to this receipt. Each one goes through Leg A's
    `asset_service.create_asset()`; this route never writes the Asset table.

    All or nothing: the first entry that fails raises, nothing is committed,
    and the error names which entry and which field so the review screen can
    mark that row.
    """
    document = _visible_or_404(db, membership, document_id)
    try:
        created = document_service.confirm(
            db,
            document,
            membership.workspace_id,
            membership.user_id,
            data.assets,
        )
    except document_service.DocumentNotReviewable as error:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail=str(error)
        ) from None
    except document_service.ConfirmRejected as rejection:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_confirm_detail(rejection),
        ) from None

    db.commit()
    return ConfirmResponse(created_asset_ids=created, document_id=document.id)


def _visible_or_404(
    db: Session, membership: Membership, document_id: uuid.UUID
):
    """The document, or 404 — including when it belongs to another workspace.

    Employees are narrowed to their own uploads (CLOUDAPPG5-96): a receipt
    shows what the company paid, which is not an employee's business even for
    an asset assigned to them.
    """
    try:
        return document_service.get_visible(
            db,
            membership.workspace_id,
            document_id,
            uploaded_by_user_id=employee_scope(membership),
        )
    except document_service.DocumentNotFound:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from None


def _confirm_detail(rejection: document_service.ConfirmRejected) -> list[dict]:
    """FastAPI's 422 shape, with the failing asset's position in `loc`.

    `["body", "assets", 2, "serial_number"]` tells the review screen which row
    and which field to mark. A five-line invoice with one bad serial should not
    show a single error with no idea where it came from.
    """
    prefix: list[object] = ["body", "assets", rejection.index]
    cause = rejection.cause

    if isinstance(cause, AssetValidationError):
        return [
            {
                "type": error.type,
                # The field errors already carry ["body", <field>]; swap the
                # prefix for this entry's position so `loc` stays truthful.
                "loc": [*prefix, *error.as_detail()["loc"][1:]],
                "msg": error.message,
            }
            for error in cause.errors
        ]

    return [{"type": "value_error", "loc": prefix, "msg": str(cause)}]

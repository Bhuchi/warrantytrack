"""The life of one uploaded receipt (CLOUDAPPG5-95, CLOUDAPPG5-96).

    presign ──▶ (browser PUTs to S3) ──▶ submit ──▶ extracted ──▶ confirm
                                            │
                                            └──▶ failed

The row is created by `presign`, **before** the file exists and before any
asset does, because the key has to be recorded somewhere to be claimed later.
That is why `documents` has no `asset_id` column: one invoice can become
several assets, and the link lives in `asset_documents` (docs/erd.md).

**Confirm never writes the Asset table.** It calls Leg A's
`asset_service.create_asset()` once per asset the user kept, which is the rule
in docs/api.md — so the required fields, the vendor-by-name lookup and the
warranty end-date calculation cannot drift between manual entry, OCR and bulk
import.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentKind, DocumentStatus
from app.schemas.asset import AssetCreate
from app.services import asset as asset_service
from app.services import ocr, storage
from app.services.asset import DuplicateSerialNumber, UnknownDocument
from app.services.asset_validation import AssetValidationError


class DocumentNotFound(Exception):
    """No such document **in this workspace**, or not one this caller may see.

    One exception for both, deliberately: the route answers 404 either way, so
    a caller cannot tell a document in someone else's workspace from one that
    does not exist (docs/api.md).
    """


class DocumentNotUploaded(Exception):
    """Submit was called but nothing was ever PUT to the storage key."""


class DocumentNotReviewable(Exception):
    """Confirm was called on a document that is not waiting to be reviewed."""

    def __init__(self, status: DocumentStatus) -> None:
        super().__init__(f"Document is {status.value}, not extracted.")
        self.status = status


class ConfirmRejected(Exception):
    """One of the assets in a confirm could not be created.

    Carries which entry failed so the review screen can mark that row rather
    than showing a single unattributable error for a five-line invoice.
    """

    def __init__(self, index: int, cause: Exception) -> None:
        super().__init__(str(cause))
        self.index = index
        self.cause = cause


def create_for_upload(
    db: Session,
    workspace_id: uuid.UUID,
    uploaded_by_user_id: uuid.UUID | None,
    filename: str,
    content_type: str | None,
    kind: DocumentKind = DocumentKind.invoice,
) -> Document:
    """Reserve a storage key and a document row for an upload about to happen."""
    document = Document(
        workspace_id=workspace_id,
        uploaded_by_user_id=uploaded_by_user_id,
        s3_key=storage.object_key(workspace_id, filename),
        filename=filename,
        content_type=content_type,
        kind=kind,
        status=DocumentStatus.pending,
    )
    db.add(document)
    db.flush()
    return document


def upload_url_for(document: Document) -> str:
    """Where the browser should PUT the file.

    A presigned S3 URL normally. On `STORAGE_BACKEND=local` there is no bucket
    to presign, so it points at this API's dev-only upload route instead — the
    one case where a file passes through the API, and it cannot happen in
    production (see app/core/config.py).
    """
    presigned = storage.presigned_put_url(document.s3_key, document.content_type)
    if presigned is not None:
        return presigned
    return f"{settings.api_base_url.rstrip('/')}/documents/{document.id}/dev-upload"


def get_visible(
    db: Session,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    uploaded_by_user_id: uuid.UUID | None = None,
) -> Document:
    """One document, or DocumentNotFound.

    `uploaded_by_user_id` is the employee scope (CLOUDAPPG5-96): an employee
    sees only the receipts they uploaded themselves, because a receipt shows
    what the company paid for things that are none of their business. Owners
    and admins pass None and see the workspace's documents.
    """
    conditions = [
        Document.id == document_id,
        Document.workspace_id == workspace_id,
    ]
    if uploaded_by_user_id is not None:
        conditions.append(Document.uploaded_by_user_id == uploaded_by_user_id)

    document = db.scalars(select(Document).where(*conditions)).first()
    if document is None:
        raise DocumentNotFound(str(document_id))
    return document


def submit(db: Session, document: Document) -> Document:
    """Run extraction on an uploaded file and record what came back.

    Synchronous for now, which is the limitation docs/architecture.md already
    records: a slow Textract call holds the request open, and a crash can
    strand a row in `processing`. `attempts` is incremented here so a stuck job
    can be found and retried, and the documented next step (S3 event ->
    Lambda) replaces only this function.

    Re-submitting a failed document is allowed on purpose — a retry is the
    whole point of recording `attempts`.
    """
    if not storage.exists(document.s3_key):
        raise DocumentNotUploaded(document.s3_key)

    document.status = DocumentStatus.processing
    document.attempts = (document.attempts or 0) + 1
    document.error = None
    db.flush()

    try:
        extracted = ocr.extract(
            document.s3_key, document.filename, document.content_type
        )
    except ocr.OcrError as exc:
        # Kept, not raised at the client: the browser is polling GET
        # /documents/{id} and reads the reason from `error` there.
        document.status = DocumentStatus.failed
        document.error = str(exc)
        db.flush()
        return document

    document.extracted_json = extracted
    document.status = DocumentStatus.extracted
    db.flush()
    return document


def confirm(
    db: Session,
    document: Document,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    assets: list[AssetCreate],
) -> list[uuid.UUID]:
    """Create one asset per entry the user kept. Returns the new asset ids.

    This is the multi-line invoice case (CLOUDAPPG5-96): one receipt with three
    laptops on it becomes three assets, each linked back to this document, so
    the detail screen can show the receipt it came from.

    Either every asset is created or none is, and this function guarantees
    that itself rather than relying on the caller. `create_asset()` flushes
    each asset as it goes, so without the SAVEPOINT below a five-line invoice
    failing on line four would leave three assets pending in the transaction —
    harmless only for as long as nobody commits that session afterwards. The
    nested transaction makes the guarantee local and unconditional.
    """
    if document.status is not DocumentStatus.extracted:
        raise DocumentNotReviewable(document.status)
    if not assets:
        raise ConfirmRejected(0, ValueError("No assets to create."))

    created: list[uuid.UUID] = []
    # One SAVEPOINT around the whole invoice: an exception escaping this block
    # undoes every asset already written inside it.
    with db.begin_nested():
        for index, entry in enumerate(assets):
            # Link the asset to this receipt without trusting the client to
            # have said so.
            document_ids = list(dict.fromkeys([*entry.document_ids, document.id]))
            payload = entry.model_copy(update={"document_ids": document_ids})
            try:
                asset = asset_service.create_asset(
                    db, workspace_id, created_by_user_id, payload
                )
            except (AssetValidationError, DuplicateSerialNumber, UnknownDocument) as exc:
                raise ConfirmRejected(index, exc) from exc
            created.append(asset.id)

        # What the user approved, kept next to the raw `extracted_json`. The
        # pair is how the review screen shows what changed, and how OCR
        # accuracy gets reported in the final presentation (docs/api.md).
        document.confirmed_json = {
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "assets": [entry.model_dump(mode="json") for entry in assets],
            "created_asset_ids": [str(asset_id) for asset_id in created],
        }
        document.status = DocumentStatus.confirmed
        db.flush()

    return created


def as_api_dict(document: Document) -> dict[str, Any]:
    """The GET /documents/{id} body, as docs/api.md defines it."""
    return {
        "id": document.id,
        "status": document.status,
        "extracted": document.extracted_json,
        "error": document.error,
    }

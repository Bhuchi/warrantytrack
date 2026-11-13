"""Request and response shapes for the Documents endpoints.

Mirrors `docs/api.md` -> "Documents and OCR". The OCR Review screen (D07) is
built against these names.

`ConfirmRequest` reuses `AssetCreate` rather than defining its own asset
shape. That is not laziness: confirm has to produce exactly what `POST /assets`
produces, because both end up in `asset_service.create_asset()`. A second
shape here would be a second set of required fields to keep in step.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.models.document import DocumentKind, DocumentStatus
from app.schemas.asset import AssetCreate


class PresignRequest(BaseModel):
    """POST /documents/presign."""

    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=100)
    # What kind of paper this is. Defaults to invoice because that is what the
    # Add Asset flow uploads; a warranty card is the other common one.
    kind: DocumentKind = DocumentKind.invoice


class PresignResponse(BaseModel):
    """The id to poll, the URL to PUT to, and the key that was reserved.

    `upload_url` is a presigned S3 URL in production. The browser PUTs the file
    there directly — it never passes through this API.
    """

    document_id: uuid.UUID
    upload_url: str
    s3_key: str


class DocumentRead(BaseModel):
    """GET /documents/{id} — what the review screen polls.

    `extracted` is deliberately untyped (`dict`): it is whatever OCR read, and
    the review screen treats every field as optional and editable. Typing it
    strictly here would mean a receipt OCR read badly could fail
    serialisation instead of reaching the human who can fix it.
    """

    id: uuid.UUID
    status: DocumentStatus
    extracted: dict[str, Any] | None = None
    error: str | None = None


class ConfirmRequest(BaseModel):
    """POST /documents/{id}/confirm — one entry per asset the user kept.

    A single invoice can hold several assets, so this is a list. Each entry is
    the OCR reading plus the user's edits.
    """

    assets: list[AssetCreate] = Field(min_length=1)


class ConfirmResponse(BaseModel):
    created_asset_ids: list[uuid.UUID]
    document_id: uuid.UUID

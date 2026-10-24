from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User

if TYPE_CHECKING:
    from app.models.asset import Asset


class DocumentStatus(str, enum.Enum):
    """The OCR job state machine from docs/architecture.md.

        pending ──▶ processing ──▶ extracted ──▶ confirmed
                        │
                        └──▶ failed
    """

    pending = "pending"
    processing = "processing"
    extracted = "extracted"
    confirmed = "confirmed"
    failed = "failed"


class DocumentKind(str, enum.Enum):
    invoice = "invoice"
    receipt = "receipt"
    warranty_card = "warranty_card"
    other = "other"


class Document(Base):
    """An uploaded file, and the OCR job that reads it.

    The row is created by `POST /documents/presign` — **before** any asset
    exists and before the file has been uploaded, because the presigned S3 key
    has to be recorded somewhere to be claimed later. So a document can exist
    with no asset attached, which is why the link lives in `asset_documents`
    and not in a column here.

    The file itself is never in the database and never passes through the API:
    the browser PUTs it straight to a private S3 bucket and this row keeps the
    key.
    """

    __tablename__ = "documents"
    __table_args__ = (
        # The retry sweep looks for jobs stuck in `processing` — see
        # `attempts` and `updated_at` below.
        Index("ix_documents_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Unique: one row owns one object in the bucket. Two rows pointing at the
    # same key would let one upload be claimed by two workspaces.
    s3_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kind: Mapped[DocumentKind] = mapped_column(
        SAEnum(DocumentKind, name="document_kind"),
        server_default=DocumentKind.other.value,
        nullable=False,
    )

    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status"),
        server_default=DocumentStatus.pending.value,
        nullable=False,
    )
    # Raw Textract output, exactly as it came back. Kept after confirmation so
    # the review screen (D07) can show what the user changed, and so we can
    # report OCR accuracy in the final presentation — see docs/api.md.
    extracted_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # What the user actually approved. The pair of columns is the accuracy
    # measurement: extracted vs confirmed.
    confirmed_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Extraction runs in-process, so a crash can strand a job in `processing`.
    # These two columns are how a stuck job is found and retried.
    attempts: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when Textract's async API is used for multi-page PDFs.
    textract_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    assets: Mapped[list[Asset]] = relationship(
        secondary="asset_documents", back_populates="documents", viewonly=True
    )
    uploaded_by: Mapped[User | None] = relationship()


class AssetDocument(Base):
    """Which documents back which asset.

    Many-to-many, not a column on either side, because both directions really
    happen: one asset can have an invoice *and* a warranty card, and one
    invoice with several line items becomes several assets that all cite it
    (`POST /documents/{id}/confirm` returns `created_asset_ids`).

    `workspace_id` is carried here too. It is redundant — both sides already
    have it — but the house rule in docs/architecture.md is that every
    tenant-scoped table has it, and the rule holds precisely because
    exceptions are where leaks start.
    """

    __tablename__ = "asset_documents"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

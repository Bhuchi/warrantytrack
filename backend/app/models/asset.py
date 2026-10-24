from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.catalog import Category, Department, Location, Vendor
from app.models.user import User

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.warranty import Warranty


class AssetCondition(str, enum.Enum):
    new = "new"
    good = "good"
    fair = "fair"
    damaged = "damaged"


class Asset(Base):
    """One tracked product: a laptop, a monitor, a phone.

    The centre of the application — warranties, documents and notifications
    all hang off it. Created three ways, all through
    `asset_service.create_asset()`: manual entry, confirmed OCR, or bulk
    import. See docs/api.md for why OCR never writes this table directly.

    `assigned_to_user_id` is what employees are filtered by: an employee may
    only see assets assigned to them, so this column is part of nearly every
    query and is indexed with `workspace_id`.
    """

    __tablename__ = "assets"
    __table_args__ = (
        # Two assets in one workspace cannot share a serial number — this is
        # what makes the bulk importer's "duplicate" error possible. Scoped to
        # the workspace, never global: two organizations can legitimately own
        # hardware with the same serial.
        UniqueConstraint(
            "workspace_id", "serial_number", name="uq_assets_workspace_serial"
        ),
        # Every list query starts with the workspace and then narrows, so the
        # indexes lead with workspace_id.
        Index("ix_assets_workspace_assigned_to", "workspace_id", "assigned_to_user_id"),
        Index("ix_assets_workspace_category", "workspace_id", "category_id"),
        Index("ix_assets_workspace_vendor", "workspace_id", "vendor_id"),
        Index("ix_assets_workspace_department", "workspace_id", "department_id"),
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

    # --- Required on manual entry (CLOUDAPPG5-118) ---
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(120), nullable=False)
    condition: Mapped[AssetCondition] = mapped_column(
        SAEnum(AssetCondition, name="asset_condition"), nullable=False
    )
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)

    # --- Purchase information ---
    # Numeric, not Float: money in binary floating point does not add up.
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), server_default="THB", nullable=False)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Classification. All optional, all SET NULL on delete: removing a
    # category must not take the assets with it. ---
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )

    # --- Where it physically sits, and photos of it ---
    # Free text on purpose: "Shelf B2", "the box under my desk". Picking a
    # `location_id` is for the site; this is the spot inside it.
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # S3 object keys, never URLs: the bucket is private and the API hands out
    # short-lived presigned GETs. A stored URL would expire in the database.
    image_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    location_image_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # --- People. SET NULL so deleting a user never deletes assets. ---
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Zero or one warranty. `uselist=False` is what makes it one — the unique
    # constraint on warranties.asset_id is what enforces it.
    warranty: Mapped[Warranty | None] = relationship(
        back_populates="asset", uselist=False, cascade="all, delete-orphan"
    )
    # Many-to-many: one invoice can back several assets. See
    # app/models/document.py. Read-only here — links are written as explicit
    # AssetDocument rows so the join row gets its own workspace_id.
    documents: Mapped[list[Document]] = relationship(
        secondary="asset_documents", back_populates="assets", viewonly=True
    )

    category: Mapped[Category | None] = relationship()
    vendor: Mapped[Vendor | None] = relationship()
    department: Mapped[Department | None] = relationship()
    location_ref: Mapped[Location | None] = relationship()
    # Two columns point at users, so each relationship has to say which one.
    assigned_to: Mapped[User | None] = relationship(
        foreign_keys=[assigned_to_user_id]
    )
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])

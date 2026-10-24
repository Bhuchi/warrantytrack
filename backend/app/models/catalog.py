from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# The four lookup tables an asset points at: category, vendor, department and
# location. They are identical in shape, so they live in one file instead of
# four near-empty ones.
#
# They are workspace-scoped, not global: one organization's "IT" department is
# not another's, and a shared list would leak names across tenants. The cost is
# that every workspace starts empty and fills its own lists.


class Category(Base):
    """What kind of thing an asset is — "Laptop", "Monitor", "Phone"."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_categories_workspace_name"),
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
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Vendor(Base):
    """Who the asset was bought from — "Power Buy", "JIB"."""

    __tablename__ = "vendors"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_vendors_workspace_name"),
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
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Department(Base):
    """Which part of the organization holds the asset — "IT", "Marketing".

    The dashboard groups by this, so it is a table and not a free-text column:
    `GET /dashboard/summary` returns one row per department and a typo would
    show up as a department of its own.
    """

    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_departments_workspace_name"),
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
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Location(Base):
    """A site or room the picker on the asset form offers — "HQ Floor 3".

    Separate from `assets.location`, which is the free-text spot *within* a
    location ("Shelf B2"). See docs/erd.md.
    """

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_locations_workspace_name"),
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
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

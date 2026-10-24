from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.asset import Asset


class Warranty(Base):
    """The cover on one asset.

    One row per asset at most — `asset_id` is unique. An asset with no row
    here has warranty status `unknown`.

    **There is no `status` column, and there must not be one.** Status is a
    function of `end_date` and today, so a stored copy is wrong the moment the
    clock moves past it. `warranty_service` computes it on read; the rules are
    in docs/architecture.md.

    `end_date` is stored rather than derived from `start_date +
    duration_months` because that is what every query filters and sorts on —
    the dashboard, the expiring list, and the nightly e-mail job all ask "whose
    end_date falls in this window". `duration_months` is kept alongside it only
    because the form collects it and the detail screen shows it back.
    """

    __tablename__ = "warranties"
    __table_args__ = (
        UniqueConstraint("asset_id", name="uq_warranties_asset"),
        # The one index that matters for Leg B: both /dashboard/expiring and
        # the scheduled e-mail job scan a date window inside one workspace.
        Index("ix_warranties_workspace_end_date", "workspace_id", "end_date"),
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
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )

    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    asset: Mapped[Asset] = relationship(back_populates="warranty")

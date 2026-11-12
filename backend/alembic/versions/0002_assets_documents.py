"""Asset, warranty, document and notification tables.

Revision ID: 0002_assets_documents
Revises: 0001_initial_tenancy
Create Date: 2026-10-24

The feature schema, on top of the tenancy tables from 0001. Written as one
migration because the tables reference each other — assets needs the catalog
tables, warranties and documents need assets — and half of it applied is not a
usable database.

Every table here carries `workspace_id NOT NULL` with its indexes leading on
that column, per docs/architecture.md.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_assets_documents"
down_revision = "0001_initial_tenancy"
branch_labels = None
depends_on = None


def _catalog_table(name: str) -> None:
    """The four lookup tables are the same shape, so build them the same way."""
    op.create_table(
        name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "name", name=f"uq_{name}_workspace_name"),
    )
    op.create_index(f"ix_{name}_workspace_id", name, ["workspace_id"])


def upgrade() -> None:
    for table in ("categories", "vendors", "departments", "locations"):
        _catalog_table(table)

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("serial_number", sa.String(length=120), nullable=False),
        sa.Column(
            "condition",
            sa.Enum("new", "good", "fair", "damaged", name="asset_condition"),
            nullable=False,
        ),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "currency", sa.String(length=3), server_default="THB", nullable=False
        ),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("image_key", sa.String(length=1024), nullable=True),
        sa.Column("location_image_key", sa.String(length=1024), nullable=True),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        # SET NULL, not CASCADE: deleting a category or a user must never take
        # assets with it.
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "workspace_id", "serial_number", name="uq_assets_workspace_serial"
        ),
    )
    op.create_index("ix_assets_workspace_id", "assets", ["workspace_id"])
    op.create_index(
        "ix_assets_workspace_assigned_to", "assets", ["workspace_id", "assigned_to_user_id"]
    )
    op.create_index("ix_assets_workspace_category", "assets", ["workspace_id", "category_id"])
    op.create_index("ix_assets_workspace_vendor", "assets", ["workspace_id", "vendor_id"])
    op.create_index(
        "ix_assets_workspace_department", "assets", ["workspace_id", "department_id"]
    )

    op.create_table(
        "warranties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        # Unique, not just indexed: at most one warranty per asset.
        sa.UniqueConstraint("asset_id", name="uq_warranties_asset"),
    )
    op.create_index("ix_warranties_workspace_id", "warranties", ["workspace_id"])
    op.create_index(
        "ix_warranties_workspace_end_date", "warranties", ["workspace_id", "end_date"]
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column(
            "kind",
            sa.Enum("invoice", "receipt", "warranty_card", "other", name="document_kind"),
            server_default="other",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "extracted",
                "confirmed",
                "failed",
                name="document_status",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("extracted_json", postgresql.JSONB(), nullable=True),
        sa.Column("confirmed_json", postgresql.JSONB(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("textract_job_id", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        # One row owns one object in the bucket.
        sa.UniqueConstraint("s3_key"),
    )
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])
    op.create_index("ix_documents_workspace_status", "documents", ["workspace_id", "status"])

    op.create_table(
        "asset_documents",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_asset_documents_document_id", "asset_documents", ["document_id"]
    )
    op.create_index(
        "ix_asset_documents_workspace_id", "asset_documents", ["workspace_id"]
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "warranty_expiring",
                "warranty_expired",
                "asset_assigned",
                name="notification_type",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # SET NULL: the notification outlives the asset, it just stops linking.
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_notifications_workspace_id", "notifications", ["workspace_id"])
    op.create_index(
        "ix_notifications_workspace_user_created",
        "notifications",
        ["workspace_id", "user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("asset_documents")
    op.drop_table("documents")
    op.drop_table("warranties")
    op.drop_table("assets")
    for table in ("locations", "departments", "vendors", "categories"):
        op.drop_table(table)

    # Dropping a table does not drop the enum types it used.
    bind = op.get_bind()
    for enum_name in (
        "notification_type",
        "document_status",
        "document_kind",
        "asset_condition",
    ):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)

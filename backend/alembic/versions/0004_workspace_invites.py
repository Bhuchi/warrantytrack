"""Store pending organization invitations independently of users.

Revision ID: 0004_workspace_invites
Revises: 0003_optional_condition
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_workspace_invites"
down_revision = "0003_optional_condition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", postgresql.ENUM(name="membership_role", create_type=False), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"]),
    )
    op.create_index("uq_workspace_invite_email", "workspace_invites", ["workspace_id", "email"], unique=True)
    op.create_index("ix_workspace_invites_email", "workspace_invites", ["email"])


def downgrade() -> None:
    op.drop_table("workspace_invites")

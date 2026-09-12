"""Initial tenancy tables: workspaces, users, memberships.

Revision ID: 0001_initial_tenancy
Revises:
Create Date: 2026-09-12

These three tables are the foundation every feature builds on, so they land
before any feature branch is cut. See docs/architecture.md for why a personal
account is modelled as a workspace.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial_tenancy"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "type",
            sa.Enum("personal", "organization", name="workspace_type"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cognito_sub", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    # Unique index (not a separate constraint) so it matches
    # User.cognito_sub, which declares unique=True + index=True.
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"], unique=True)

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "admin", "employee", name="membership_role"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id", "workspace_id", name="uq_membership_user_workspace"
        ),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_workspace_id", "memberships", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("memberships")
    op.drop_index("ix_users_cognito_sub", table_name="users")
    op.drop_table("users")
    op.drop_table("workspaces")
    sa.Enum(name="membership_role").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="workspace_type").drop(op.get_bind(), checkfirst=True)

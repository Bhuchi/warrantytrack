"""Make assets.condition optional.

Revision ID: 0003_optional_condition
Revises: 0002_assets_documents
Create Date: 2026-11-11

Issue #34: the final CLOUDAPPG5-118 acceptance criteria no longer ask for the
physical condition and the ERD postpones it, so an asset may be saved without
one. Existing rows keep their value; only the NOT NULL rule is dropped.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_optional_condition"
down_revision = "0002_assets_documents"
branch_labels = None
depends_on = None

_CONDITION = sa.Enum("new", "good", "fair", "damaged", name="asset_condition")


def upgrade() -> None:
    op.alter_column("assets", "condition", existing_type=_CONDITION, nullable=True)


def downgrade() -> None:
    # Fails if any asset has no condition: the database refuses NOT NULL while a
    # NULL exists. That is deliberate. Guessing a condition for those assets
    # would invent data, so fill them in by hand first if you really need this.
    op.alter_column("assets", "condition", existing_type=_CONDITION, nullable=False)

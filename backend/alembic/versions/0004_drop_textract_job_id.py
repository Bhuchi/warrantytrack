"""Drop documents.textract_job_id.

Revision ID: 0004_drop_textract_job_id
Revises: 0003_optional_condition
Create Date: 2026-11-13

Receipts are read by Claude on Amazon Bedrock only; the Textract backend was
removed. The column held the job ID for Textract's async API, which was never
used, so it is always NULL and nothing reads it.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_drop_textract_job_id"
down_revision = "0003_optional_condition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("documents", "textract_job_id")


def downgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("textract_job_id", sa.String(length=128), nullable=True),
    )

"""Create minimal migration bookkeeping foundation."""

import sqlalchemy as sa
from alembic import op

revision = "0001_database_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schema_foundation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_schema_foundation_singleton"),
    )


def downgrade() -> None:
    op.drop_table("schema_foundation")

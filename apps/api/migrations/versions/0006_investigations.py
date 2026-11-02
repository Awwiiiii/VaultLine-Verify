"""Persist evidence-grounded investigations without changing deterministic history."""

import sqlalchemy as sa
from alembic import op

revision = "0006_investigations"
down_revision = "0005_financing_claims"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investigations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "case_id",
            sa.Uuid(),
            sa.ForeignKey("verification_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(40)),
        sa.CheckConstraint(
            "status IN ('pending','completed','failed')", name="ck_investigation_status"
        ),
    )
    op.create_index("ix_investigations_case_id", "investigations", ["case_id"])


def downgrade():
    op.drop_table("investigations")

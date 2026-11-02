"""Persistent financing assertions; existing evidence and runs are unchanged."""

import sqlalchemy as sa
from alembic import op

revision = "0005_financing_claims"
down_revision = "0004_verification_runs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "financing_claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "case_id",
            sa.Uuid(),
            sa.ForeignKey("verification_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "invoice_document_id",
            sa.Uuid(),
            sa.ForeignKey("evidence_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("claim_reference", sa.String(200), nullable=False),
        sa.Column("lender", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(26, 8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_reference", sa.String(200)),
        sa.Column("notes", sa.String(2000)),
        sa.Column("status_history", sa.JSON(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.UniqueConstraint("case_id", "claim_reference", name="uq_claim_case_reference"),
        sa.CheckConstraint("amount >= 0", name="ck_claim_amount"),
        sa.CheckConstraint(
            "status IN ('proposed','active','released','cancelled')", name="ck_claim_status"
        ),
        sa.CheckConstraint(
            "currency IN ('USD','EUR','GBP','INR','JPY','KWD')", name="ck_claim_currency"
        ),
    )
    op.create_index("ix_financing_claims_case_id", "financing_claims", ["case_id"])
    op.create_index(
        "ix_financing_claims_invoice_document_id", "financing_claims", ["invoice_document_id"]
    )


def downgrade():
    op.drop_table("financing_claims")

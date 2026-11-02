"""Normalized financial records and field-level provenance."""

import sqlalchemy as sa
from alembic import op

revision = "0003_financial_extraction"
down_revision = "0002_cases_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_processing_status", "evidence_documents", type_="check")
    op.create_check_constraint(
        "ck_processing_status",
        "evidence_documents",
        "processing_status IN ('uploaded','processing','extracted','needs_review','failed')",
    )
    op.create_table(
        "financial_extractions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("evidence_documents.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "verification_case_id",
            sa.Uuid(),
            sa.ForeignKey("verification_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('processing', 'extracted', 'needs_review', 'failed')",
            name="ck_extraction_status",
        ),
    )
    op.create_index(
        "ix_financial_extractions_verification_case_id",
        "financial_extractions",
        ["verification_case_id"],
    )
    op.create_table(
        "field_provenance",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "extraction_id",
            sa.Uuid(),
            sa.ForeignKey("financial_extractions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            sa.Uuid(),
            sa.ForeignKey("evidence_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(200), nullable=False),
        sa.Column("original_value", sa.String(), nullable=False),
        sa.Column("normalized_value", sa.String()),
        sa.Column("source_location", sa.JSON(), nullable=False),
        sa.Column("extraction_method", sa.String(50), nullable=False),
        sa.Column("validation_status", sa.String(20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("ix_field_provenance_extraction_id", "field_provenance", ["extraction_id"])


def downgrade() -> None:
    op.drop_table("field_provenance")
    op.drop_table("financial_extractions")
    op.drop_constraint("ck_processing_status", "evidence_documents", type_="check")
    op.execute("UPDATE evidence_documents SET processing_status = 'uploaded'")
    op.create_check_constraint(
        "ck_processing_status", "evidence_documents", "processing_status = 'uploaded'"
    )

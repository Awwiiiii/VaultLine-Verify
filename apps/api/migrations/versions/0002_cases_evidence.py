"""Cases and evidence metadata foundation."""

import sqlalchemy as sa
from alembic import op

revision = "0002_cases_evidence"
down_revision = "0001_database_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_reference", sa.String(40), unique=True, nullable=False),
        sa.Column("counterparty_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status = 'open'", name="ck_case_status"),
    )
    op.create_index("ix_cases_created", "verification_cases", ["created_at", "id"])
    op.create_table(
        "evidence_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "verification_case_id",
            sa.Uuid(),
            sa.ForeignKey("verification_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256_checksum", sa.String(64), nullable=False),
        sa.Column("storage_reference", sa.String(40), unique=True, nullable=False),
        sa.Column("upload_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_status", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "document_type IN ('invoice', 'purchase_order')", name="ck_document_type"
        ),
        sa.CheckConstraint("file_size > 0", name="ck_file_size"),
        sa.CheckConstraint("processing_status = 'uploaded'", name="ck_processing_status"),
    )
    op.create_index(
        "ix_evidence_documents_verification_case_id", "evidence_documents", ["verification_case_id"]
    )
    op.create_index("ix_documents_checksum", "evidence_documents", ["sha256_checksum"])


def downgrade() -> None:
    op.drop_table("evidence_documents")
    op.drop_table("verification_cases")

"""Cases and immutable evidence metadata; no financial conclusions."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from vaultline_api.db.base import Base


def now() -> datetime:
    return datetime.now(UTC)


class SchemaFoundation(Base):
    """Bookkeeping table from migration 0001, retained in metadata to prevent false drops."""

    __tablename__ = "schema_foundation"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("id = 1", name="ck_schema_foundation_singleton"),)


class VerificationCase(Base):
    __tablename__ = "verification_cases"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_reference: Mapped[str] = mapped_column(String(40), unique=True)
    counterparty_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        CheckConstraint("status = 'open'", name="ck_case_status"),
        Index("ix_cases_created", "created_at", "id"),
    )


class EvidenceDocument(Base):
    __tablename__ = "evidence_documents"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    verification_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="RESTRICT"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(20))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int]
    sha256_checksum: Mapped[str] = mapped_column(String(64))
    storage_reference: Mapped[str] = mapped_column(String(40), unique=True)
    upload_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processing_status: Mapped[str] = mapped_column(String(20), default="uploaded")
    __table_args__ = (
        CheckConstraint("document_type IN ('invoice', 'purchase_order')", name="ck_document_type"),
        CheckConstraint("file_size > 0", name="ck_file_size"),
        CheckConstraint(
            "processing_status IN ('uploaded','processing','extracted','needs_review','failed')",
            name="ck_processing_status",
        ),
        Index("ix_documents_checksum", "sha256_checksum"),
    )


class FinancialExtraction(Base):
    """Provider-independent normalized record: amounts persisted as decimal strings in JSON."""

    __tablename__ = "financial_extractions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence_documents.id", ondelete="RESTRICT"), unique=True
    )
    verification_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'extracted', 'needs_review', 'failed')",
            name="ck_extraction_status",
        ),
    )


class FieldProvenance(Base):
    __tablename__ = "field_provenance"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    extraction_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_extractions.id", ondelete="CASCADE"), index=True
    )
    source_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence_documents.id", ondelete="RESTRICT")
    )
    field_name: Mapped[str] = mapped_column(String(200))
    original_value: Mapped[str] = mapped_column(String)
    normalized_value: Mapped[str | None] = mapped_column(String)
    source_location: Mapped[dict] = mapped_column(JSON)
    extraction_method: Mapped[str] = mapped_column(String(50))
    validation_status: Mapped[str] = mapped_column(String(20))
    position: Mapped[int]


class VerificationRun(Base):
    """Append-only application history with the complete input snapshot and tolerances."""

    __tablename__ = "verification_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    verification_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="RESTRICT"), index=True
    )
    rule_set_version: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(30))
    tolerances: Mapped[dict] = mapped_column(JSON)
    input_snapshot: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('passed','discrepancy','insufficient_evidence','not_applicable')",
            name="ck_run_outcome",
        ),
    )


class VerificationFinding(Base):
    __tablename__ = "verification_findings"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("verification_runs.id", ondelete="RESTRICT"), index=True
    )
    rule_id: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)
    position: Mapped[int]
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('passed','discrepancy','insufficient_evidence','not_applicable')",
            name="ck_finding_outcome",
        ),
    )


class FinancingClaim(Base):
    """Recorded assertion, not proof of financing or legal identity."""

    __tablename__ = "financing_claims"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="RESTRICT"), index=True
    )
    invoice_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence_documents.id", ondelete="RESTRICT"), index=True
    )
    claim_reference: Mapped[str] = mapped_column(String(200))
    lender: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(26, 8))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    external_reference: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(String(2000))
    status_history: Mapped[list] = mapped_column(JSON)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("case_id", "claim_reference", name="uq_claim_case_reference"),
        CheckConstraint("amount >= 0", name="ck_claim_amount"),
        CheckConstraint(
            "status IN ('proposed','active','released','cancelled')", name="ck_claim_status"
        ),
        CheckConstraint(
            "currency IN ('USD','EUR','GBP','INR','JPY','KWD')", name="ck_claim_currency"
        ),
    )


class Investigation(Base):
    """Append-only AI-assisted report and the exact minimized evidence sent to its provider."""

    __tablename__ = "investigations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    evidence_snapshot: Mapped[dict] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str] = mapped_column(String(20))
    error_code: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','completed','failed')", name="ck_investigation_status"
        ),
    )

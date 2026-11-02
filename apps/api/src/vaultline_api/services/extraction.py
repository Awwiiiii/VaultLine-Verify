"""Extraction orchestration: lock, check immutable evidence, parse, normalize, persist."""

import hashlib
import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from vaultline_api.core.config import get_settings
from vaultline_api.db.models import EvidenceDocument, FieldProvenance, FinancialExtraction
from vaultline_api.extraction.contracts import ExtractionResult
from vaultline_api.extraction.fields import extract_fields
from vaultline_api.extraction.normalization import normalize
from vaultline_api.extraction.parsing import parse_document


def get_document(
    db: Session, case_id: UUID, document_id: UUID, lock: bool = False
) -> EvidenceDocument:
    query = select(EvidenceDocument).where(
        EvidenceDocument.id == document_id, EvidenceDocument.verification_case_id == case_id
    )
    if lock:
        query = query.with_for_update()
    document = db.scalar(query)
    if document is None:
        raise HTTPException(404, "Document not found in this case")
    return document


def extraction_response(db: Session, record: FinancialExtraction) -> dict:
    provenance = db.scalars(
        select(FieldProvenance)
        .where(FieldProvenance.extraction_id == record.id)
        .order_by(FieldProvenance.position)
    ).all()
    return {
        "id": str(record.id),
        "document_id": str(record.document_id),
        "verification_case_id": str(record.verification_case_id),
        "status": record.status,
        "error": record.error,
        "result": {
            **record.payload,
            "provenance": [
                {
                    "source_document_id": str(v.source_document_id),
                    "field_name": v.field_name,
                    "original_value": v.original_value,
                    "normalized_value": v.normalized_value,
                    "source_location": v.source_location,
                    "extraction_method": v.extraction_method,
                    "validation_status": v.validation_status,
                }
                for v in provenance
            ],
        },
    }


def extract_document(db: Session, case_id: UUID, document_id: UUID) -> dict:
    with db.begin():
        document = get_document(db, case_id, document_id, lock=True)
        record = db.scalar(
            select(FinancialExtraction).where(FinancialExtraction.document_id == document_id)
        )
        if record is not None and record.status in {"extracted", "needs_review"}:
            return extraction_response(db, record)
        if record is None:
            record = FinancialExtraction(
                document_id=document_id, verification_case_id=case_id, status="processing"
            )
            db.add(record)
        record.status = document.processing_status = "processing"
        record.error = None
        db.flush()
        try:
            settings = get_settings()
            if not re.fullmatch(r"[a-f0-9]{32}\.(pdf|csv)", document.storage_reference):
                raise ValueError("Invalid storage key")
            root = settings.evidence_storage_dir.resolve()
            path = root / document.storage_reference
            if path.is_symlink() or path.resolve().parent != root:
                raise ValueError("Invalid storage path")
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as source:
                while chunk := source.read(65536):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise ValueError("Evidence exceeds processing limit")
                    digest.update(chunk)
            if size != document.file_size or digest.hexdigest() != document.sha256_checksum:
                raise ValueError("Evidence integrity mismatch")
            result = normalize(
                extract_fields(parse_document(path)), document.document_type, str(document_id)
            )
        except Exception:
            # No parser details, paths, or financial data in externally visible errors.
            record.status = document.processing_status = "failed"
            record.error = "Extraction failed. Check schema, text and evidence integrity."
            record.payload = ExtractionResult(document_type=document.document_type).model_dump(
                exclude={"provenance"}
            )
        else:
            record.status = document.processing_status = (
                "needs_review" if result.findings else "extracted"
            )
            record.payload = result.model_dump(exclude={"provenance"})
            db.execute(delete(FieldProvenance).where(FieldProvenance.extraction_id == record.id))
            for position, value in enumerate(result.provenance):
                db.add(
                    FieldProvenance(
                        extraction_id=record.id,
                        position=position,
                        **{**value.model_dump(), "source_document_id": document_id},
                    )
                )
        db.flush()
        response = extraction_response(db, record)
    return response

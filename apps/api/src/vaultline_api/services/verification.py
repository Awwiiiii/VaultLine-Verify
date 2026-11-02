"""Snapshot persisted evidence once, run pure rules, append historical results."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vaultline_api.core.config import get_settings
from vaultline_api.db.models import (
    EvidenceDocument,
    FieldProvenance,
    FinancialExtraction,
    VerificationCase,
    VerificationFinding,
    VerificationRun,
)
from vaultline_api.verification.contracts import RULE_SET_VERSION, DocumentEvidence, Tolerances
from vaultline_api.verification.engine import verify


def snapshot_dataset(db: Session) -> list[DocumentEvidence]:
    # One SQL statement gives a consistent MVCC snapshot for all compared evidence.
    rows = db.execute(
        select(EvidenceDocument, FinancialExtraction, FieldProvenance)
        .outerjoin(FinancialExtraction, FinancialExtraction.document_id == EvidenceDocument.id)
        .outerjoin(FieldProvenance, FieldProvenance.extraction_id == FinancialExtraction.id)
        .order_by(EvidenceDocument.id, FieldProvenance.position)
    ).all()
    documents: dict[str, DocumentEvidence] = {}
    for document, extraction, provenance in rows:
        key = str(document.id)
        if key not in documents:
            payload = extraction.payload if extraction is not None else {}
            documents[key] = DocumentEvidence(
                document_id=key,
                case_id=str(document.verification_case_id),
                document_type=document.document_type,
                processing_status=extraction.status if extraction else document.processing_status,
                extraction_id=str(extraction.id) if extraction else None,
                checksum=document.sha256_checksum,
                fields=payload.get("fields", {}),
                line_items=payload.get("line_items", []),
                validation_findings=payload.get("findings", []),
            )
        if provenance is not None:
            documents[key].provenance.append(
                {
                    "id": str(provenance.id),
                    "source_document_id": str(provenance.source_document_id),
                    "field_name": provenance.field_name,
                    "original_value": provenance.original_value,
                    "normalized_value": provenance.normalized_value,
                    "source_location": provenance.source_location,
                    "extraction_method": provenance.extraction_method,
                    "validation_status": provenance.validation_status,
                }
            )
    return list(documents.values())


def run_response(db: Session, run: VerificationRun, include_findings: bool = True) -> dict:
    data = {
        "id": str(run.id),
        "case_id": str(run.verification_case_id),
        "rule_set_version": run.rule_set_version,
        "outcome": run.outcome,
        "tolerances": run.tolerances,
        "created_at": run.created_at.isoformat(),
    }
    if include_findings:
        data["findings"] = [
            f.payload
            for f in db.scalars(
                select(VerificationFinding)
                .where(VerificationFinding.run_id == run.id)
                .order_by(VerificationFinding.position)
            )
        ]
    return data


def run_verification(db: Session, case_id: UUID) -> dict:
    settings = get_settings()
    tolerances = Tolerances(
        amount=settings.verification_amount_tolerance,
        quantity=settings.verification_quantity_tolerance,
        unit_price=settings.verification_price_tolerance,
    )
    with db.begin():
        if db.get(VerificationCase, case_id) is None:
            raise HTTPException(404, "Case not found")
        dataset = snapshot_dataset(db)
        documents = [d for d in dataset if d.case_id == str(case_id)]
        invoices = [d for d in dataset if d.document_type == "invoice"]
        result = verify(str(case_id), documents, invoices, tolerances)
        run = VerificationRun(
            verification_case_id=case_id,
            rule_set_version=RULE_SET_VERSION,
            outcome=result.outcome,
            tolerances=tolerances.model_dump(mode="json"),
            input_snapshot=[
                d.model_dump(mode="json")
                for d in dataset
                if d.document_type == "invoice" or d.case_id == str(case_id)
            ],
        )
        db.add(run)
        db.flush()
        for position, finding in enumerate(result.findings):
            db.add(
                VerificationFinding(
                    run_id=run.id,
                    rule_id=finding.rule_id,
                    outcome=finding.outcome,
                    position=position,
                    payload=finding.model_dump(mode="json"),
                )
            )
        db.flush()
        response = run_response(db, run)
    return response

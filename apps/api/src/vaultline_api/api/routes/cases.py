"""Case management and evidence ingestion endpoints."""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vaultline_api.api.schemas import CaseCreate, CasePage, CaseRead, DocumentRead
from vaultline_api.db.models import EvidenceDocument, VerificationCase
from vaultline_api.db.session import get_db_session
from vaultline_api.services.evidence import store_upload

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])
DB = Annotated[Session, Depends(get_db_session)]


def require_case(db: Session, case_id: UUID) -> VerificationCase:
    case = db.get(VerificationCase, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


@router.post("", response_model=CaseRead, status_code=201)
def create_case(payload: CaseCreate, db: DB) -> VerificationCase:
    with db.begin():
        case = VerificationCase(
            counterparty_name=payload.counterparty_name, case_reference=f"VL-{uuid4().hex.upper()}"
        )
        db.add(case)
        db.flush()
    return case


@router.get("", response_model=CasePage)
def list_cases(
    db: DB, limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0
) -> dict:
    return {
        "items": db.scalars(
            select(VerificationCase)
            .order_by(VerificationCase.created_at.desc(), VerificationCase.id)
            .limit(limit)
            .offset(offset)
        ).all(),
        "total": db.scalar(select(func.count()).select_from(VerificationCase)),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: UUID, db: DB) -> VerificationCase:
    return require_case(db, case_id)


@router.get("/{case_id}/documents", response_model=list[DocumentRead])
def list_documents(case_id: UUID, db: DB) -> list[EvidenceDocument]:
    require_case(db, case_id)
    return list(
        db.scalars(
            select(EvidenceDocument)
            .where(EvidenceDocument.verification_case_id == case_id)
            .order_by(EvidenceDocument.upload_timestamp.desc())
        )
    )


@router.post("/{case_id}/documents", response_model=DocumentRead, status_code=201)
def upload_document(
    case_id: UUID,
    db: DB,
    document_type: Annotated[Literal["invoice", "purchase_order"], Form()],
    file: Annotated[UploadFile, File()],
) -> EvidenceDocument:
    path = None
    try:
        with db.begin():
            require_case(db, case_id)
            path, name, size, checksum = store_upload(file)
            document = EvidenceDocument(
                verification_case_id=case_id,
                document_type=document_type,
                original_filename=name,
                content_type=file.content_type,
                file_size=size,
                sha256_checksum=checksum,
                storage_reference=path.name,
            )
            db.add(document)
            db.flush()
        return document
    except BaseException:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@router.post("/{case_id}/documents/{document_id}/extract")
def extract(case_id: UUID, document_id: UUID, db: DB) -> dict:
    from vaultline_api.services.extraction import extract_document

    return extract_document(db, case_id, document_id)


@router.get("/{case_id}/documents/{document_id}/extraction")
def get_extraction(case_id: UUID, document_id: UUID, db: DB) -> dict:
    from vaultline_api.db.models import FinancialExtraction
    from vaultline_api.services.extraction import extraction_response, get_document

    get_document(db, case_id, document_id)
    record = db.scalar(
        select(FinancialExtraction).where(FinancialExtraction.document_id == document_id)
    )
    if record is None:
        raise HTTPException(404, "Extraction has not been requested")
    return extraction_response(db, record)


@router.post("/{case_id}/verify", status_code=201)
def verify_case(case_id: UUID, db: DB) -> dict:
    from vaultline_api.services.verification import run_verification

    return run_verification(db, case_id)


@router.get("/{case_id}/verifications")
def list_verifications(
    case_id: UUID,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    from vaultline_api.db.models import VerificationRun
    from vaultline_api.services.verification import run_response

    require_case(db, case_id)
    query = select(VerificationRun).where(VerificationRun.verification_case_id == case_id)
    runs = db.scalars(
        query.order_by(VerificationRun.created_at.desc(), VerificationRun.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [run_response(db, run, include_findings=False) for run in runs],
        "total": db.scalar(
            select(func.count())
            .select_from(VerificationRun)
            .where(VerificationRun.verification_case_id == case_id)
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{case_id}/verifications/{run_id}")
def get_verification(case_id: UUID, run_id: UUID, db: DB) -> dict:
    from vaultline_api.db.models import VerificationRun
    from vaultline_api.services.verification import run_response

    require_case(db, case_id)
    run = db.scalar(
        select(VerificationRun).where(
            VerificationRun.id == run_id, VerificationRun.verification_case_id == case_id
        )
    )
    if run is None:
        raise HTTPException(404, "Verification run not found in this case")
    return run_response(db, run)

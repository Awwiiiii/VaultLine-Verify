"""Claim registry HTTP boundary and persistence orchestration."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from vaultline_api.api.routes.cases import DB, require_case
from vaultline_api.claims.engine import detect
from vaultline_api.db.models import EvidenceDocument, FinancingClaim, now
from vaultline_api.extraction.normalization import MINOR_UNITS
from vaultline_api.services.verification import snapshot_dataset

router = APIRouter(prefix="/api/v1", tags=["claims"])
Status = Literal["proposed", "active", "released", "cancelled"]


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    invoice_document_id: UUID
    claim_reference: str = Field(min_length=1, max_length=200)
    lender: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0, max_digits=26, decimal_places=8, allow_inf_nan=False)
    currency: Literal["USD", "EUR", "GBP", "INR", "JPY", "KWD"]
    status: Status = "proposed"
    external_reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("amount", mode="before")
    @classmethod
    def decimal_string(cls, value):
        if not isinstance(value, str):
            raise ValueError("Amount must be an exact decimal string")
        import re

        if not re.fullmatch(r"\d{1,18}(?:\.\d{1,8})?", value):
            raise ValueError("Use nonnegative decimal digits without exponent or separators")
        return value

    @model_validator(mode="after")
    def minor_units(self):
        if self.amount != self.amount.quantize(Decimal(1).scaleb(-MINOR_UNITS[self.currency])):
            raise ValueError("Amount exceeds currency minor units; no rounding performed")
        return self


class ClaimRead(ClaimCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    case_id: UUID
    created_at: datetime
    status_history: list[dict]
    evidence_snapshot: dict

    @field_validator("amount", mode="before")
    @classmethod
    def decimal_string(cls, value):
        return value


def read(claim):
    result = ClaimRead.model_validate(claim).model_dump(mode="json")
    result["amount"] = format(
        claim.amount.quantize(Decimal(1).scaleb(-MINOR_UNITS[claim.currency])), "f"
    )
    return result


@router.post("/cases/{case_id}/claims", status_code=201)
def create_claim(case_id: UUID, payload: ClaimCreate, db: DB):
    try:
        with db.begin():
            require_case(db, case_id)
            doc = db.get(EvidenceDocument, payload.invoice_document_id)
            if doc is None or doc.verification_case_id != case_id:
                raise HTTPException(404, "Invoice not found in this case")
            if doc.document_type != "invoice":
                raise HTTPException(422, "Claims require an invoice document")
            evidence = next(d for d in snapshot_dataset(db) if d.document_id == str(doc.id))
            claim = FinancingClaim(
                **payload.model_dump(),
                case_id=case_id,
                evidence_snapshot=evidence.model_dump(mode="json"),
                status_history=[{"status": payload.status, "at": now().isoformat()}],
            )
            db.add(claim)
            db.flush()
            result = read(claim)
        return result
    except IntegrityError:
        raise HTTPException(409, "Claim reference already recorded in this case") from None


@router.get("/cases/{case_id}/claims")
def list_claims(
    case_id: UUID,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    require_case(db, case_id)
    query = select(FinancingClaim).where(FinancingClaim.case_id == case_id)
    return {
        "items": [
            read(c)
            for c in db.scalars(
                query.order_by(FinancingClaim.created_at, FinancingClaim.id)
                .limit(limit)
                .offset(offset)
            )
        ],
        "total": db.scalar(
            select(func.count())
            .select_from(FinancingClaim)
            .where(FinancingClaim.case_id == case_id)
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/claims/{claim_id}")
def get_claim(claim_id: UUID, db: DB):
    claim = db.get(FinancingClaim, claim_id)
    if claim is None:
        raise HTTPException(404, "Claim not found")
    return read(claim)


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status


@router.patch("/claims/{claim_id}/status")
def change_status(claim_id: UUID, payload: StatusChange, db: DB):
    with db.begin():
        claim = db.scalar(
            select(FinancingClaim).where(FinancingClaim.id == claim_id).with_for_update()
        )
        if claim is None:
            raise HTTPException(404, "Claim not found")
        allowed = {"proposed": {"active", "cancelled"}, "active": {"released", "cancelled"}}
        if payload.status not in allowed.get(claim.status, set()):
            raise HTTPException(409, "Invalid status transition")
        claim.status = payload.status
        claim.status_history = [
            *claim.status_history,
            {"status": payload.status, "at": now().isoformat()},
        ]
        db.flush()
        return read(claim)


@router.get("/cases/{case_id}/claim-conflicts")
def conflicts(case_id: UUID, db: DB):
    require_case(db, case_id)
    claims = [read(c) for c in db.scalars(select(FinancingClaim).order_by(FinancingClaim.id))]
    return {
        "scope": "Recorded VaultLine dataset only; external financing is unverified.",
        "findings": detect(str(case_id), claims),
    }

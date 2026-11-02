"""Deterministic case risk-indicator view; no write or financing decision endpoint."""

from uuid import UUID

from fastapi import APIRouter, Response

from vaultline_api.api.routes.cases import DB
from vaultline_api.risk.contracts import RiskAssessmentRead
from vaultline_api.services.risk import risk_assessment

router = APIRouter(prefix="/api/v1/cases", tags=["risk indicators"])


@router.get("/{case_id}/risk-assessment", response_model=RiskAssessmentRead)
def get_risk_assessment(case_id: UUID, db: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return risk_assessment(db, case_id)

"""Case-scoped append-only investigation endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from vaultline_api.api.routes.cases import DB, require_case
from vaultline_api.db.models import Investigation
from vaultline_api.investigations.providers import AIProvider, get_provider
from vaultline_api.services.investigations import investigate, response

router = APIRouter(prefix="/api/v1/cases", tags=["investigations"])


@router.post("/{case_id}/investigations", status_code=201)
def start(case_id: UUID, db: DB, provider: Annotated[AIProvider, Depends(get_provider)]):
    return investigate(db, case_id, provider)


@router.get("/{case_id}/investigations")
def list_investigations(
    case_id: UUID,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    require_case(db, case_id)
    query = select(Investigation).where(Investigation.case_id == case_id)
    return {
        "items": [
            response(r, detail=False)
            for r in db.scalars(
                query.order_by(Investigation.created_at.desc(), Investigation.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ],
        "total": db.scalar(
            select(func.count()).select_from(Investigation).where(Investigation.case_id == case_id)
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{case_id}/investigations/{investigation_id}")
def get_investigation(case_id: UUID, investigation_id: UUID, db: DB):
    require_case(db, case_id)
    record = db.scalar(
        select(Investigation).where(
            Investigation.id == investigation_id, Investigation.case_id == case_id
        )
    )
    if record is None:
        raise HTTPException(404, "Investigation not found in this case")
    return response(record)

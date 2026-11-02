"""Read-only collection of existing deterministic findings and their current coverage."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from vaultline_api.api.routes.cases import require_case
from vaultline_api.claims.engine import detect
from vaultline_api.db.models import FinancingClaim, VerificationRun, now
from vaultline_api.risk.contracts import RiskInputs
from vaultline_api.risk.engine import assess
from vaultline_api.services.verification import run_response, snapshot_dataset


def document_fingerprint(documents: list[dict]) -> str:
    """Canonical evidence digest includes provenance; never substitutes for source evidence."""
    encoded = json.dumps(
        sorted(documents, key=lambda d: d["document_id"]), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def collect_inputs(db: Session, case_id: UUID) -> RiskInputs:
    require_case(db, case_id)
    run = db.scalar(
        select(VerificationRun)
        .where(VerificationRun.verification_case_id == case_id)
        .order_by(VerificationRun.created_at.desc(), VerificationRun.id.desc())
        .limit(1)
    )
    documents = [
        d.model_dump(mode="json")
        for d in snapshot_dataset(db)
        if d.document_type == "invoice" or d.case_id == str(case_id)
    ]
    current = document_fingerprint(documents)
    saved = document_fingerprint(run.input_snapshot) if run else None
    claims = [
        {
            "id": str(c.id),
            "case_id": str(c.case_id),
            "invoice_document_id": str(c.invoice_document_id),
            "lender": c.lender,
            "amount": format(c.amount, "f"),
            "currency": c.currency,
            "status": c.status,
            "evidence_snapshot": c.evidence_snapshot,
        }
        for c in db.scalars(select(FinancingClaim).order_by(FinancingClaim.id))
    ]
    conflicts = detect(str(case_id), claims)
    relevant_ids = {identifier for f in conflicts for identifier in f["claim_ids"]}
    relevant_ids.update(c["id"] for c in claims if c["case_id"] == str(case_id))
    # Unrelated document payloads are used only for the dataset-coverage hash, never returned.
    return RiskInputs(
        case_id=str(case_id),
        verification=run_response(db, run) if run else None,
        freshness="missing" if run is None else "current" if current == saved else "stale",
        saved_document_fingerprint=saved,
        current_document_fingerprint=current,
        claim_conflicts=conflicts,
        claims=[
            {k: v for k, v in c.items() if k != "evidence_snapshot"}
            for c in claims
            if c["id"] in relevant_ids
        ],
    )


def risk_assessment(db: Session, case_id: UUID) -> dict:
    inputs = collect_inputs(db, case_id)
    return {"assessed_at": now().isoformat(), **assess(inputs).model_dump(mode="json")}

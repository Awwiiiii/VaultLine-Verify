"""Build the minimized package from existing findings; never rerun or alter verification."""

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from vaultline_api.claims.engine import FIELDS, detect
from vaultline_api.db.models import FinancingClaim, VerificationRun, now
from vaultline_api.investigations.contracts import EvidenceEntry, EvidencePackage
from vaultline_api.investigations.providers import ProviderError
from vaultline_api.services.verification import run_response
from vaultline_api.verification.contracts import DocumentEvidence, Observation
from vaultline_api.verification.engine import observe, usable


def build_evidence(db: Session, case_id: UUID) -> EvidencePackage:
    entries: list[EvidenceEntry] = []

    def add(identifier, kind, text, documents=None, claims=None, cases=None, provenance=None):
        entries.append(
            EvidenceEntry(
                id=identifier,
                kind=kind,
                text=text,
                document_ids=documents or [],
                claim_ids=claims or [],
                case_ids=cases or [str(case_id)],
                provenance=provenance or [],
            )
        )

    run = db.scalar(
        select(VerificationRun)
        .where(VerificationRun.verification_case_id == case_id)
        .order_by(VerificationRun.created_at.desc(), VerificationRun.id.desc())
        .limit(1)
    )
    if run is None:
        add("coverage", "unknown", "No deterministic verification run has been recorded.")
    else:
        add(
            "verification",
            "deterministic_finding",
            f"Saved verification outcome: {run.outcome}; rule version: {run.rule_set_version}.",
        )
        for i, finding in enumerate(run_response(db, run)["findings"]):
            add(
                f"verification:{i}",
                "deterministic_finding",
                f"{finding['rule_id']}: {finding['outcome']}. {finding['explanation']}",
                documents=finding["document_ids"],
            )
            for j, observation in enumerate(finding["source_evidence"]):
                parsed = Observation.model_validate(observation)
                if usable(parsed):
                    # Never transmit raw source text, source files, paths or arbitrary metadata.
                    provenance = [
                        {
                            k: p[k]
                            for k in (
                                "id",
                                "source_document_id",
                                "field_name",
                                "normalized_value",
                                "source_location",
                                "extraction_method",
                                "validation_status",
                            )
                            if k in p
                        }
                        for p in parsed.provenance
                    ]
                    add(
                        f"observation:{i}:{j}",
                        "observed_fact",
                        "Document observation: "
                        + json.dumps({"field": parsed.field_name, "value": parsed.value}),
                        documents=[parsed.document_id],
                        cases=[parsed.case_id],
                        provenance=provenance,
                    )
    rows = list(db.scalars(select(FinancingClaim).order_by(FinancingClaim.id)))
    # The pure conflict engine needs the saved invoice snapshot, not notes or external references.
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
        for c in rows
    ]
    conflicts = detect(str(case_id), claims)
    relevant_ids = {c["id"] for c in claims if c["case_id"] == str(case_id)}
    for i, finding in enumerate(conflicts):
        relevant_ids.update(finding["claim_ids"])
        add(
            f"conflict:{i}",
            "deterministic_finding",
            f"{finding['category']}: {finding['explanation']} Rule: {finding['rule_version']}.",
            documents=finding["invoice_document_ids"],
            claims=finding["claim_ids"],
            cases=finding["case_ids"],
        )
        for j, source in enumerate(finding["source_evidence"]):
            document = DocumentEvidence.model_validate(source)
            for field in FIELDS:
                observation = observe(document, field)
                if usable(observation):
                    provenance = [
                        {
                            k: p[k]
                            for k in (
                                "id",
                                "source_document_id",
                                "field_name",
                                "normalized_value",
                                "source_location",
                                "extraction_method",
                                "validation_status",
                            )
                            if k in p
                        }
                        for p in observation.provenance
                    ]
                    add(
                        f"conflict_observation:{i}:{j}:{field}",
                        "observed_fact",
                        "Claim invoice snapshot observation: "
                        + json.dumps({"field": field, "value": observation.value}),
                        documents=[document.document_id],
                        cases=[document.case_id],
                        claims=finding["claim_ids"],
                        provenance=provenance,
                    )
    for claim in claims:
        if claim["id"] in relevant_ids:
            add(
                "claim:" + claim["id"],
                "observed_fact",
                "Recorded assertion (not proof of financing): "
                + json.dumps({k: claim[k] for k in ("id", "amount", "currency", "status")}),
                documents=[claim["invoice_document_id"]],
                claims=[claim["id"]],
                cases=[claim["case_id"]],
            )
    package = EvidencePackage(
        case_id=str(case_id),
        captured_at=now().isoformat(),
        verification_run_id=str(run.id) if run else None,
        verification_created_at=run.created_at.isoformat() if run else None,
        entries=entries,
    )
    if len(entries) > 500 or len(package.model_dump_json().encode()) > 120000:
        raise ProviderError("evidence_too_large")
    return package

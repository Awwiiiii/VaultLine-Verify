"""Deterministic comparisons limited to recorded VaultLine claims."""

from decimal import Decimal, localcontext

from vaultline_api.verification.contracts import DocumentEvidence
from vaultline_api.verification.engine import conservative_text, number, observe, usable

VERSION = "vaultline.claim-conflicts.v1"
FIELDS = ("invoice_number", "supplier_name", "buyer_name", "currency", "total_amount")


def detect(case_id: str, claims: list[dict]) -> list[dict]:
    findings = []

    def evidence(claim):
        return DocumentEvidence.model_validate(claim["evidence_snapshot"])

    def identity(claim):
        doc = evidence(claim)
        if not all(usable(observe(doc, f)) for f in FIELDS):
            return None
        if (
            doc.fields["currency"] != claim["currency"]
            or number(observe(doc, "total_amount")) is None
        ):
            return None
        return tuple(
            conservative_text(doc.fields[f])
            if f in {"supplier_name", "buyer_name"}
            else doc.fields[f].strip()
            if f != "total_amount"
            else Decimal(doc.fields[f])
            for f in FIELDS
        )

    def add(category, group, explanation):
        findings.append(
            {
                "category": category,
                "rule_version": VERSION,
                "claim_ids": [c["id"] for c in group],
                "case_ids": sorted({c["case_id"] for c in group}),
                "invoice_document_ids": sorted({c["invoice_document_id"] for c in group}),
                "matched_fields": list(FIELDS) if all(identity(c) for c in group) else [],
                "source_evidence": [c["evidence_snapshot"] for c in group],
                "explanation": explanation,
            }
        )

    relevant = [c for c in claims if c["case_id"] == case_id]
    for claim in relevant:
        if claim["status"] == "proposed":
            add(
                "insufficient_evidence",
                [claim],
                "Proposed assertion; not active financing. Review before activation.",
            )
        if claim["status"] not in {"active", "proposed"}:
            continue
        if identity(claim) is None:
            add(
                "insufficient_evidence",
                [claim],
                "Invoice identity, provenance or matching currency is unresolved.",
            )
    active = [c for c in claims if c["status"] == "active"]
    if any(c["status"] == "active" for c in relevant):
        for unknown in active:
            if unknown["case_id"] != case_id and identity(unknown) is None:
                add(
                    "insufficient_evidence",
                    [unknown],
                    "Unresolved active claim elsewhere prevents complete dataset matching.",
                )
    seen = set()
    for claim in relevant:
        if claim["status"] != "active":
            continue
        group = [
            c
            for c in active
            if c["invoice_document_id"] == claim["invoice_document_id"]
            or (identity(claim) is not None and identity(c) == identity(claim))
        ]
        key = tuple(sorted(c["id"] for c in group))
        if key in seen:
            continue
        seen.add(key)
        if len(group) > 1:
            same_record = (
                len(
                    {
                        (c["invoice_document_id"], c["lender"], c["amount"], c["currency"])
                        for c in group
                    }
                )
                == 1
            )
            add(
                "confirmed_duplicate_records" if same_record else "potential_competing_claims",
                group,
                "Repeated recorded lender/document/amount/currency assertions."
                if same_record
                else "Multiple active claims share evidence; lender names are unverified.",
            )
        valid = identity(claim)
        with localcontext() as ctx:
            ctx.prec = 80
            if valid and all(c["currency"] == claim["currency"] for c in group):
                if sum((Decimal(c["amount"]) for c in group), Decimal(0)) > valid[-1]:
                    add(
                        "aggregate_exceeds_invoice",
                        group,
                        "Active recorded amounts exceed invoice total; no FX conversion.",
                    )
    if not findings:
        add(
            "no_conflict_found",
            relevant,
            "No conflict found in VaultLine. External financing remains unverified.",
        )
    return findings

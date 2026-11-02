"""Validated, provider-independent contracts for non-predictive risk indicators."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vaultline_api.verification.contracts import DocumentEvidence, Finding, Outcome

RULE_VERSION = "vaultline.risk-indicators.v1"
SCOPE = "Recorded VaultLine evidence only; external financing is unknown and unverified."
Category = Literal[
    "discrepancy",
    "potential_claim_conflict",
    "aggregate_claim_excess",
    "duplicate_assertions",
    "insufficient_evidence",
    "unchecked_comparison",
    "no_recorded_claim_conflict",
    "unknown_external_financing",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VerificationInput(Contract):
    id: str
    case_id: str
    rule_set_version: str
    outcome: Outcome
    tolerances: dict[str, str]
    created_at: str
    findings: list[Finding]


class ClaimConflict(Contract):
    category: Literal[
        "confirmed_duplicate_records",
        "potential_competing_claims",
        "aggregate_exceeds_invoice",
        "insufficient_evidence",
        "no_conflict_found",
    ]
    rule_version: str
    claim_ids: list[str]
    case_ids: list[str]
    invoice_document_ids: list[str]
    matched_fields: list[str]
    source_evidence: list[DocumentEvidence]
    explanation: str


class RecordedClaim(Contract):
    id: str
    case_id: str
    invoice_document_id: str
    lender: str
    amount: str = Field(pattern=r"^\d{1,18}(?:\.\d{1,8})?$")
    currency: Literal["USD", "EUR", "GBP", "INR", "JPY", "KWD"]
    status: Literal["proposed", "active", "released", "cancelled"]


class RiskInputs(Contract):
    case_id: str
    verification: VerificationInput | None
    freshness: Literal["missing", "current", "stale"]
    saved_document_fingerprint: str | None
    current_document_fingerprint: str
    claim_conflicts: list[ClaimConflict]
    claims: list[RecordedClaim]
    scope: Literal[SCOPE] = SCOPE

    @model_validator(mode="after")
    def validate_scope(self):
        if self.verification is None:
            if self.freshness != "missing" or self.saved_document_fingerprint is not None:
                raise ValueError("Missing verification cannot be current")
        else:
            if self.verification.case_id != self.case_id or any(
                f.case_id != self.case_id for f in self.verification.findings
            ):
                raise ValueError("Verification belongs to another case")
            expected = (
                "current"
                if self.saved_document_fingerprint == self.current_document_fingerprint
                else "stale"
            )
            if self.saved_document_fingerprint is None or self.freshness != expected:
                raise ValueError("Verification freshness contradicts document fingerprints")
        return self


class Source(Contract):
    id: str
    kind: Literal[
        "verification_run",
        "verification_finding",
        "claim_conflict",
        "claim_assertion",
        "verification_coverage",
        "scope_limitation",
    ]
    payload: dict


class Indicator(Contract):
    id: str
    category: Category
    title: str
    explanation: str
    source_refs: list[str] = Field(min_length=1)


class RiskAssessment(Contract):
    rule_version: Literal[RULE_VERSION] = RULE_VERSION
    case_id: str
    assessment_status: Literal[
        "review_findings_present", "insufficient_evidence", "no_recorded_discrepancy"
    ]
    human_review_required: Literal[True] = True
    review_requirement: str = (
        "A human must review source evidence and unresolved questions. "
        "No financing decision is made."
    )
    scope: Literal[SCOPE] = SCOPE
    indicators: list[Indicator]
    sources: list[Source]
    input_snapshot: RiskInputs


class RiskAssessmentRead(RiskAssessment):
    assessed_at: datetime

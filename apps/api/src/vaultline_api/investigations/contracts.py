"""Bounded provider-independent evidence and investigation contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PROMPT_VERSION = "vaultline.investigation.v1"
INTERPRETATIONS = (
    "Review the cited findings together before drawing a conclusion.",
    "The cited evidence warrants further verification; it does not establish wrongdoing.",
)
UNKNOWNS = (
    "Evidence is insufficient for a complete assessment.",
    "External financing is unknown and unverified.",
    "Legal identity, ownership and enforceability remain unverified.",
)
STEPS = (
    "Obtain the missing source evidence and rerun deterministic verification.",
    "Reconcile the cited discrepancy against the original source documents.",
    "Ask the relevant parties to substantiate the recorded claim through an approved channel.",
    "Review the cited field provenance and unresolved extraction findings.",
)
LIMITATION = (
    "AI-assisted review only; no financing decision. "
    "VaultLine records do not establish absence of external financing."
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceEntry(StrictModel):
    id: str
    kind: Literal["observed_fact", "deterministic_finding", "unknown"]
    text: str
    document_ids: list[str]
    claim_ids: list[str]
    case_ids: list[str]
    provenance: list[dict]


class EvidencePackage(StrictModel):
    case_id: str
    captured_at: str
    verification_run_id: str | None
    verification_created_at: str | None
    entries: list[EvidenceEntry]
    scope: str = "Recorded VaultLine dataset only; external financing is unverified."
    prompt_version: str = PROMPT_VERSION


class Statement(StrictModel):
    kind: Literal["observed_fact", "deterministic_finding", "ai_interpretation", "unknown"]
    text: str = Field(min_length=1, max_length=3000)
    evidence_refs: list[str] = Field(min_length=1, max_length=40)


class InvestigationOutput(StrictModel):
    executive_summary: list[Statement] = Field(min_length=1, max_length=10)
    key_findings: list[Statement] = Field(max_length=40)
    supporting_evidence_references: list[str] = Field(min_length=1, max_length=100)
    unresolved_questions: list[Statement] = Field(min_length=1, max_length=10)
    recommended_next_verification_steps: list[Statement] = Field(min_length=1, max_length=10)
    limitations: list[Statement] = Field(min_length=1, max_length=10)


def validate_output(raw: str, package: EvidencePackage) -> InvestigationOutput:
    """Reject fabricated facts, foreign references and unbounded policy/decision language."""
    result = InvestigationOutput.model_validate_json(raw)
    allowed = {e.id: e for e in package.entries}
    cited = set(result.supporting_evidence_references)
    if not cited <= allowed.keys():
        raise ValueError("Unsupported evidence reference")
    sections = (
        result.executive_summary,
        result.key_findings,
        result.unresolved_questions,
        result.recommended_next_verification_steps,
        result.limitations,
    )
    used = set()
    for section in sections:
        for statement in section:
            refs = set(statement.evidence_refs)
            if not refs <= allowed.keys():
                raise ValueError("Unsupported evidence reference")
            used.update(refs)
            if statement.kind in {"observed_fact", "deterministic_finding"}:
                if len(refs) != 1:
                    raise ValueError("Facts require one exact source")
                source = allowed[next(iter(refs))]
                if source.kind != statement.kind or statement.text != source.text:
                    raise ValueError("Unsupported factual statement")
            elif statement.kind == "unknown":
                if statement.text not in UNKNOWNS:
                    raise ValueError("Unsupported unknown statement")
            elif statement.text not in (*INTERPRETATIONS, *STEPS, LIMITATION):
                raise ValueError("Unsupported interpretation")
    if cited != used:
        raise ValueError("Evidence index must equal statement references")
    if not any(s.kind == "unknown" and s.text == UNKNOWNS[1] for s in result.unresolved_questions):
        raise ValueError("External financing uncertainty must be explicit")
    if not any(s.kind == "ai_interpretation" and s.text == LIMITATION for s in result.limitations):
        raise ValueError("Mandatory limitation missing")
    if any(e.kind == "unknown" or "insufficient_evidence" in e.text for e in package.entries):
        if not any(
            s.kind == "unknown" and s.text == UNKNOWNS[0] for s in result.unresolved_questions
        ):
            raise ValueError("Insufficient evidence must be explicit")
    return result

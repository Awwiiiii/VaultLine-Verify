"""Bounded provider-independent evidence and investigation contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    required_finding_refs: list[str] = Field(default_factory=list)


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


class OutputValidationError(ValueError):
    """A fixed diagnostic code, never raw Pydantic errors containing untrusted input."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_output(raw: str, package: EvidencePackage) -> InvestigationOutput:
    """Reject fabricated facts, foreign references and unbounded policy/decision language."""
    try:
        result = InvestigationOutput.model_validate_json(raw)
    except ValidationError as exc:
        errors = exc.errors(include_input=False, include_context=False, include_url=False)
        if any(e["type"] == "json_invalid" for e in errors):
            code = "invalid_json"
        elif any(e["type"] == "literal_error" and e["loc"][-1:] == ("kind",) for e in errors):
            code = "statement_kind"
        elif any(
            e["loc"] == ("limitations",) and e["type"] in {"missing", "too_short"} for e in errors
        ):
            code = "limitation"
        else:
            code = "output_schema"
        raise OutputValidationError(code) from None
    allowed = {e.id: e for e in package.entries}
    cited = set(result.supporting_evidence_references)
    if not cited <= allowed.keys():
        raise OutputValidationError("references")
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
                raise OutputValidationError("references")
            used.update(refs)
            if statement.kind in {"observed_fact", "deterministic_finding"}:
                if len(refs) != 1:
                    raise OutputValidationError("grounding_sources")
                source = allowed[next(iter(refs))]
                if source.kind != statement.kind:
                    raise OutputValidationError("grounding_kind")
                if statement.text != source.text:
                    raise OutputValidationError("grounding_text")
            elif statement.kind == "unknown":
                if statement.text not in UNKNOWNS:
                    raise OutputValidationError("vocabulary")
            elif statement.text not in (*INTERPRETATIONS, *STEPS, LIMITATION):
                raise OutputValidationError("vocabulary")
    factual_refs = {
        ref
        for section in sections
        for statement in section
        if statement.kind == "deterministic_finding"
        for ref in statement.evidence_refs
    }
    if not set(package.required_finding_refs) <= factual_refs:
        raise OutputValidationError("material_findings")
    if cited != used:
        raise OutputValidationError("evidence_index")
    if not any(s.kind == "unknown" and s.text == UNKNOWNS[1] for s in result.unresolved_questions):
        raise OutputValidationError("uncertainty")
    if not any(s.kind == "ai_interpretation" and s.text == LIMITATION for s in result.limitations):
        raise OutputValidationError("limitation")
    if any(e.kind == "unknown" or "insufficient_evidence" in e.text for e in package.entries):
        if not any(
            s.kind == "unknown" and s.text == UNKNOWNS[0] for s in result.unresolved_questions
        ):
            raise OutputValidationError("uncertainty")
    return result

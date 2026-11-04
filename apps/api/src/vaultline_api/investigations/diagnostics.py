"""Allowlisted diagnostics only: never include model values or validation exception text."""

BASETEN_DIAGNOSTICS = {
    "baseten_grounding_sources": (
        "evidence_grounding",
        "A factual statement must cite exactly one source entry.",
    ),
    "baseten_grounding_kind": (
        "evidence_grounding",
        "Factual statement kind differs from its cited source kind.",
    ),
    "baseten_grounding_text": (
        "evidence_grounding",
        "Factual statement text differs from its cited source text.",
    ),
    "baseten_material_findings": (
        "evidence_coverage",
        "Material discrepancies or conflicts were not reported as exact deterministic findings.",
    ),
    "baseten_envelope": (
        "response_envelope",
        "Invalid provider JSON envelope or choice/message structure.",
    ),
    "baseten_model_mismatch": (
        "response_identity",
        "Response model differs from the requested model; not accepted.",
    ),
    "baseten_response_limit": ("response_size", "Provider envelope exceeded the byte limit."),
    "baseten_completion_state": (
        "completion",
        "Unexpected completion finish reason; no report accepted.",
    ),
    "baseten_refusal": ("completion", "Provider refused the request; no report accepted."),
    "baseten_tool_calls": ("completion", "Unexpected tool calls; no report accepted."),
    "baseten_content_type": ("assistant_content", "Assistant content is not a string."),
    "baseten_content_limit": ("assistant_content", "Assistant content exceeded the byte limit."),
    "baseten_no_content": (
        "assistant_content",
        "No final assistant content; reasoning alone is not a report.",
    ),
    "baseten_output_budget": (
        "completion",
        "Output budget exhausted; no complete report accepted.",
    ),
    "baseten_invalid_json": ("json_syntax", "Final assistant content is not valid JSON."),
    "baseten_output_schema": (
        "schema_validation",
        "Final JSON fails the strict investigation schema.",
    ),
    "baseten_statement_kind": ("schema_validation", "Unsupported statement kind."),
    "baseten_limitation": (
        "mandatory_limitation",
        "Mandatory limitation is missing or not in the required section/kind.",
    ),
    "baseten_references": ("evidence_references", "Statement or index cites unsupported evidence."),
    "baseten_grounding": (
        "evidence_grounding",
        "Source kind/text or exact-source count does not match.",
    ),
    "baseten_vocabulary": (
        "allowed_language",
        "Unknown or interpretation text is outside the allowed phrases.",
    ),
    "baseten_evidence_index": (
        "evidence_references",
        "Evidence index does not equal the references used.",
    ),
    "baseten_uncertainty": (
        "mandatory_uncertainty",
        "Required external-financing or insufficient-evidence uncertainty is missing.",
    ),
    "baseten_unsupported_request": (
        "request_compatibility",
        "Provider rejected request settings/schema (HTTP 400/422); no retry made.",
    ),
}


def error_stage(code: str | None) -> str | None:
    entry = BASETEN_DIAGNOSTICS.get(code)
    return entry[0] if entry else None

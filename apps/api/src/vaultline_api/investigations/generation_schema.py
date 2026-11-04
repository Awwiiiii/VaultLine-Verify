"""Constrain Baseten generation, without changing the final domain output contract."""

from vaultline_api.investigations.contracts import (
    INTERPRETATIONS,
    LIMITATION,
    STEPS,
    UNKNOWNS,
    EvidencePackage,
    InvestigationOutput,
)


def grounded_generation_schema(package: EvidencePackage) -> dict:
    """Each fact branch couples source kind, exact text and exactly one permitted entry ID.

    The old generic schema constrained kind but allowed arbitrary text and up to 40 refs.
    The final validator still checks everything; provider schema enforcement is not trusted.
    """
    schema = InvestigationOutput.model_json_schema()
    variants = []
    for entry in package.entries:
        if (
            entry.kind not in {"observed_fact", "deterministic_finding"}
            or not 0 < len(entry.text) <= 3000
        ):
            continue
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "text", "evidence_refs"],
                "properties": {
                    "kind": {"type": "string", "enum": [entry.kind]},
                    "text": {"type": "string", "enum": [entry.text]},
                    "evidence_refs": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 1,
                        "items": {"type": "string", "enum": [entry.id]},
                    },
                },
            }
        )
    refs = [e.id for e in package.entries]
    for kind, phrases in [
        ("ai_interpretation", [*INTERPRETATIONS, *STEPS, LIMITATION]),
        ("unknown", list(UNKNOWNS)),
    ]:
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "text", "evidence_refs"],
                "properties": {
                    "kind": {"type": "string", "enum": [kind]},
                    "text": {"type": "string", "enum": phrases},
                    "evidence_refs": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 40,
                        "items": {"type": "string", "enum": refs},
                    },
                },
            }
        )
    schema["$defs"]["Statement"] = {"anyOf": variants}
    schema["properties"]["supporting_evidence_references"]["items"]["enum"] = refs
    return schema

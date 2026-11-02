"""Provider-independent deterministic verification contracts."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Outcome = Literal["passed", "discrepancy", "insufficient_evidence", "not_applicable"]
RULE_SET_VERSION = "vaultline.cross-document.v1.1"


class Tolerances(BaseModel):
    amount: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=8, allow_inf_nan=False
    )
    quantity: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=8, allow_inf_nan=False
    )
    unit_price: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=8, allow_inf_nan=False
    )


class DocumentEvidence(BaseModel):
    document_id: str
    case_id: str
    document_type: Literal["invoice", "purchase_order"]
    processing_status: str
    extraction_id: str | None = None
    checksum: str
    fields: dict[str, str | None] = Field(default_factory=dict)
    line_items: list[dict[str, str | None]] = Field(default_factory=list)
    provenance: list[dict] = Field(default_factory=list)
    validation_findings: list[dict] = Field(default_factory=list)


class Observation(BaseModel):
    document_id: str
    case_id: str
    field_name: str
    value: str | None
    provenance: list[dict] = Field(default_factory=list)


class Finding(BaseModel):
    case_id: str
    rule_id: str
    outcome: Outcome
    mandatory: bool = True
    document_ids: list[str]
    compared_fields: list[str]
    actual_values: dict[str, str | None]
    expected_values: dict[str, str | None]
    source_evidence: list[Observation]
    explanation: str


class VerificationResult(BaseModel):
    outcome: Outcome
    findings: list[Finding]

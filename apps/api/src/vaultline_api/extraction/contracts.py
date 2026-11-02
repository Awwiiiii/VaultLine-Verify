"""Provider-independent extraction contracts. Monetary normalized values are decimal strings."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class SourceField:
    name: str
    value: str
    location: dict[str, str | int]
    method: str


class Provenance(BaseModel):
    source_document_id: str
    field_name: str
    original_value: str
    normalized_value: str | None
    source_location: dict[str, str | int]
    extraction_method: str
    validation_status: Literal["valid", "invalid", "ambiguous", "rounded"]


class Finding(BaseModel):
    field: str
    code: str
    message: str


class ExtractionResult(BaseModel):
    schema_version: str = "1"
    document_type: Literal["invoice", "purchase_order"] | None = None
    fields: dict[str, str | None] = Field(default_factory=dict)
    line_items: list[dict[str, str | None]] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)

"""Validated API contracts without local storage paths."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    counterparty_name: str = Field(min_length=1, max_length=200)


class CaseRead(CaseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    case_reference: str
    status: str
    created_at: datetime
    updated_at: datetime


class CasePage(BaseModel):
    items: list[CaseRead]
    total: int
    limit: int
    offset: int


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    verification_case_id: UUID
    document_type: Literal["invoice", "purchase_order"]
    original_filename: str
    content_type: str
    file_size: int
    sha256_checksum: str
    upload_timestamp: datetime
    processing_status: Literal["uploaded", "processing", "extracted", "needs_review", "failed"]

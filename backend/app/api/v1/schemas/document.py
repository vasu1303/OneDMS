from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.workflow import ValidationIssue


class DealerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dealer_code: str
    name: str


class DmsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    integration_tier: int
    integration_method: str
    input_format: str


class InvoiceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    total_amount: Decimal
    currency: str
    validation_status: str
    review_status: str
    oem_delivery_status: str


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dealer_id: int
    dms_id: int
    document_type: str
    original_file_name: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    storage_key: str | None = None
    checksum_sha256: str | None = None
    raw_payload: dict[str, Any] | None = None
    received_at: datetime
    status: Literal["RECEIVED", "PROCESSING", "COMPLETED", "REVIEW_REQUIRED", "FAILED"]
    error_message: str | None = None

    dealer: DealerSummary | None = None
    dms: DmsSummary | None = None
    invoice: InvoiceSummary | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    size: int


class ProcessDocumentRequest(BaseModel):
    force: bool = Field(
        default=False,
        description="If true, re-processes an existing unapproved invoice or retries a failed document."
    )


class ProcessDocumentResponse(BaseModel):
    document_id: int
    document_status: Literal["RECEIVED", "PROCESSING", "COMPLETED", "REVIEW_REQUIRED", "FAILED"]
    invoice_id: int | None = None
    validation_status: str | None = None
    review_status: str | None = None
    message: str
    validation_issues: list[ValidationIssue] = Field(default_factory=list)


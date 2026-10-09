from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.workflow import ValidationIssue


class InvoiceLineItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    line_number: int
    item_code: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal = Decimal("0.00")
    taxable_amount: Decimal
    tax_rate: Decimal | None = None
    tax_amount: Decimal
    line_total: Decimal
    chassis_number: str | None = None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    invoice_number: str
    invoice_date: date
    buyer_oem_id: str
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    canonical_payload: dict[str, Any]
    validation_status: Literal["PENDING", "VALID", "INVALID", "REVIEW_REQUIRED"]
    review_status: Literal["NOT_REQUIRED", "PENDING", "APPROVED", "REJECTED"]
    oem_delivery_status: Literal["NOT_SENT", "SENT", "FAILED"]
    created_at: datetime
    updated_at: datetime

    line_items: list[InvoiceLineItemResponse] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    size: int


class LineItemPatch(BaseModel):
    line_number: int = Field(gt=0)
    item_code: str | None = None
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    discount_amount: Decimal | None = None
    taxable_amount: Decimal | None = None
    tax_rate: Decimal | None = None
    tax_amount: Decimal | None = None
    line_total: Decimal | None = None
    chassis_number: str | None = None


class InvoicePatchRequest(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    buyer_oem_id: str | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    reviewer_notes: str | None = None
    line_items: list[LineItemPatch] | None = None


class InvoiceReviewRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    notes: str | None = None
    force_override: bool = Field(
        default=False,
        description="If true, allows approving an INVALID invoice with an auditor override."
    )


class MockOEMResponse(BaseModel):
    is_mock: bool = True
    target_system: str = "DAIMLER_ERP"
    delivery_status: Literal["NOT_SENT", "SENT", "FAILED"]
    payload: dict[str, Any]
    disclaimer: str = "Preview / Mock: No external Daimler endpoint was called."
    timestamp: datetime


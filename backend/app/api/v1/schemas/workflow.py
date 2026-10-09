from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ValidationIssue(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_code: str
    rule_name: str
    severity: Literal["ERROR", "WARNING"]
    field: str | None = None
    line_number: int | None = None
    message: str


class ValidationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["VALID", "INVALID", "REVIEW_REQUIRED"]
    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    rules_applied_count: int = 0


class ExtractedLineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_number: int | None = None
    item_code: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal = Decimal("0.00")
    taxable_amount: Decimal
    tax_rate: Decimal | None = None
    tax_amount: Decimal = Decimal("0.00")
    line_total: Decimal
    chassis_number: str | None = None
    item_category: str | None = None


class ExtractedInvoiceData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_number: str
    invoice_date: date | str
    supplier_dealer_code: str | None = None
    buyer_oem_id: str | None = None
    currency: str = "INR"
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    confidence_score: float = 1.0
    extraction_method: str = "STRUCTURED_PARSE"
    raw_extracted_fields: dict[str, Any] = Field(default_factory=dict)


class OEMExportResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_mock: bool = True
    target_system: str = "DAIMLER_ERP"
    delivery_status: Literal["PREVIEW_NOT_SENT", "SENT", "FAILED"]
    payload: dict[str, Any]
    generated_at: datetime


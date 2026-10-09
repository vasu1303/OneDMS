"""Pydantic models and data contracts for the format parsing and extraction boundary."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DocumentFormat(str, Enum):
    """Supported inbound invoice document formats."""
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    UNKNOWN = "unknown"


class CanonicalLineItemCandidate(BaseModel):
    """Canonical candidate line item proposal extracted from invoice."""

    line_number: int = Field(..., ge=1, description="Sequential line index (1-based)")
    item_code: str | None = Field(default=None, description="Optional OEM or dealer part/item code")
    description: str = Field(..., min_length=1, description="Line item description")
    quantity: Decimal = Field(..., description="Quantity delivered or billed")
    unit_price: Decimal = Field(..., description="Unit price before tax and discount")
    discount_amount: Decimal = Field(default=Decimal("0.0"), description="Discount applied on line")
    taxable_amount: Decimal | None = Field(default=None, description="Taxable base amount")
    tax_rate: Decimal | None = Field(default=None, description="Tax rate in percentage (e.g. 19.0 for 19%)")
    tax_amount: Decimal = Field(default=Decimal("0.0"), description="Tax amount for this line")
    line_total: Decimal = Field(..., description="Final line total payable")
    chassis_number: str | None = Field(default=None, description="VIN or chassis identifier for vehicle/truck units")

    @field_validator("quantity", "unit_price", "discount_amount", "line_total", "tax_amount", mode="before")
    @classmethod
    def parse_decimal(cls, v: Any) -> Decimal:
        if v is None:
            return Decimal("0.0")
        if isinstance(v, (int, float, str)):
            # Strip currency symbols and commas if present
            s = str(v).replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
            if not s:
                return Decimal("0.0")
            return Decimal(s)
        if isinstance(v, Decimal):
            return v
        raise ValueError(f"Cannot convert {v} to Decimal")

    @field_validator("taxable_amount", "tax_rate", mode="before")
    @classmethod
    def parse_optional_decimal(cls, v: Any) -> Decimal | None:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float, str)):
            s = str(v).replace("%", "").replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
            if not s:
                return None
            return Decimal(s)
        if isinstance(v, Decimal):
            return v
        return None


class CanonicalInvoiceCandidate(BaseModel):
    """Canonical candidate invoice representation for downstream mapping and validation."""

    invoice_number: str = Field(..., min_length=1, description="Unique invoice number")
    invoice_date: str = Field(..., description="ISO 8601 date string (YYYY-MM-DD)")
    buyer_oem_id: str | None = Field(default=None, description="OEM identifier or customer reference")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code (e.g. EUR, USD)")
    subtotal_amount: Decimal | None = Field(default=None, description="Net subtotal before tax")
    tax_amount: Decimal | None = Field(default=None, description="Total tax amount")
    total_amount: Decimal = Field(..., description="Gross total invoice amount")
    line_items: list[CanonicalLineItemCandidate] = Field(default_factory=list, description="Extracted line items")

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, v: Any) -> str:
        if not v:
            return "USD"
        cleaned = str(v).strip().upper()
        # Map common symbols to ISO 4217
        symbol_map = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
        return symbol_map.get(cleaned, cleaned[:3])

    @field_validator("total_amount", "subtotal_amount", "tax_amount", mode="before")
    @classmethod
    def parse_decimal_totals(cls, v: Any) -> Decimal | None:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float, str)):
            s = str(v).replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
            if not s:
                return None
            return Decimal(s)
        if isinstance(v, Decimal):
            return v
        return None


class ExtractionMetadata(BaseModel):
    """Metadata regarding the extraction process for auditability and UI inspection."""

    duration_ms: float = Field(default=0.0, description="Processing duration in milliseconds")
    page_count: int | None = Field(default=None, description="Page count for document formats")
    table_count: int | None = Field(default=None, description="Number of tabular structures detected")
    character_count: int | None = Field(default=None, description="Length of text content analyzed")
    field_confidence: dict[str, float] = Field(
        default_factory=dict,
        description="Internal heuristic confidence per field (0.0 to 1.0). Not calibrated truth."
    )


class ExtractionResult(BaseModel):
    """The unified typed result returned by the format parsing and extraction layer."""

    format: DocumentFormat = Field(..., description="Detected or provided document format")
    extraction_method: str = Field(..., description="Identifier of the parsing engine used")
    success: bool = Field(..., description="Whether the extraction succeeded without fatal parsing errors")
    source_data: Any | None = Field(
        default=None,
        description="Raw structured data for JSON/CSV formats to be passed to Person 3's deterministic mapping"
    )
    canonical_candidate: CanonicalInvoiceCandidate | None = Field(
        default=None,
        description="Structured canonical invoice candidate proposed for PDF documents"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Extraction warnings, non-fatal anomalies, or missing optional fields"
    )
    metadata: ExtractionMetadata = Field(
        default_factory=ExtractionMetadata,
        description="Extraction metrics and metadata"
    )
    error_message: str | None = Field(
        default=None,
        description="Fatal error message if extraction failed"
    )

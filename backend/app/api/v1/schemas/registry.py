"""Explicit, user-approved source mappings; no inferred or AI-generated fields."""

from typing import Annotated, Any, Literal

from pydantic import (
    AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, model_validator,
)


SourcePath = Annotated[str, StringConstraints(
    strict=True, strip_whitespace=True, min_length=1,
    pattern=r"^[^.]+(?:\.[^.]+)*$",
)]


class RegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LineMapping(RegistryModel):
    source_field: SourcePath
    description: SourcePath
    quantity: SourcePath
    unit_price: SourcePath
    taxable_amount: SourcePath
    tax_amount: SourcePath
    line_total: SourcePath
    item_code: SourcePath | None = None
    chassis_number: SourcePath | None = None
    item_category: SourcePath | None = None
    discount_amount: SourcePath | None = None
    tax_rate: SourcePath | None = None


class SourceMapping(RegistryModel):
    invoice_number: SourcePath
    invoice_date: SourcePath
    currency: SourcePath
    subtotal: SourcePath
    tax_amount: SourcePath
    total_amount: SourcePath
    buyer_oem_id: SourcePath
    supplier_dealer_code: SourcePath | None = None
    line_items: LineMapping

    def mapper_config(self) -> dict[str, Any]:
        # The mapper treats every supplied field as a requested mapping.
        return self.model_dump(exclude_none=True)


class DmsSystemCreate(RegistryModel):
    name: Annotated[str, StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=255,
    )]
    integration_tier: int = Field(
        strict=True, ge=1, le=3,
        validation_alias=AliasChoices("tier", "integration_tier"),
    )
    integration_method: Literal["API", "UPLOAD"]
    input_format: Literal["JSON", "CSV", "PDF"]
    mapping_config: SourceMapping | None = None

    @model_validator(mode="after")
    def require_structured_mapping(self) -> "DmsSystemCreate":
        if self.input_format != "PDF" and self.mapping_config is None:
            raise ValueError("mapping_config is required for JSON and CSV")
        return self


class DealerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dealer_code: str
    name: str


class DmsSystemResponse(BaseModel):
    id: int
    name: str
    integration_tier: int
    integration_method: str
    input_format: str
    active_mapping_version: int | None
    active_mapping_config: dict[str, Any] | None


class MappingPreviewRequest(RegistryModel):
    mapping_config: SourceMapping
    payload: dict[str, Any]


class MappingPreviewResponse(BaseModel):
    canonical_candidate: dict[str, Any]
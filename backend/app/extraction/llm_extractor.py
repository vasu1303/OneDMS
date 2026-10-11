"""LLM-enhanced PDF extractor that uses OpenRouter as a fallback when heuristic parsing fails."""

from __future__ import annotations

import io
import json
from decimal import Decimal
from typing import Any

from app.core.logging import log
from app.extraction.models import (
    CanonicalInvoiceCandidate,
    CanonicalLineItemCandidate,
    DocumentFormat,
    ExtractionMetadata,
    ExtractionResult,
)
from app.services.llm import llm_service


EXTRACTION_SYSTEM_PROMPT = """\
You are an invoice data extraction engine for automotive dealer management systems.
Given the raw text content of an invoice document, extract ALL structured data into
a JSON object with EXACTLY these fields:

{
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD",
  "buyer_oem_id": "string or null",
  "currency": "3-letter ISO code e.g. INR, USD, EUR",
  "subtotal": "numeric string",
  "tax_amount": "numeric string",
  "total_amount": "numeric string",
  "line_items": [
    {
      "item_code": "string or null",
      "description": "string",
      "quantity": "numeric string",
      "unit_price": "numeric string",
      "discount_amount": "numeric string, default 0.00",
      "taxable_amount": "numeric string",
      "tax_rate": "numeric string or null",
      "tax_amount": "numeric string",
      "line_total": "numeric string",
      "chassis_number": "string or null"
    }
  ]
}

Rules:
- Return ONLY valid JSON, no markdown fences, no explanation.
- All monetary values must be exact decimal strings (e.g. "1234.56").
- Dates must be ISO 8601 format (YYYY-MM-DD).
- If a field cannot be determined, use null.
- Preserve original precision of all numbers.
"""


async def llm_extract_invoice(raw_text: str) -> ExtractionResult:
    """Use the LLM service to extract invoice data from unstructured text."""
    if not llm_service.is_configured:
        log.warning("LLM service not configured; cannot perform AI extraction")
        return ExtractionResult(
            format=DocumentFormat.PDF,
            extraction_method="llm_unavailable",
            success=False,
            source_data=None,
            canonical_candidate=None,
            warnings=["LLM service is not configured"],
            metadata=ExtractionMetadata(),
            error_message="OpenRouter API key is not configured",
        )

    user_prompt = (
        "Extract all invoice data from this document text into the specified JSON structure.\n\n"
        f"--- DOCUMENT TEXT ---\n{raw_text[:12000]}\n--- END ---"
    )

    try:
        log.info("Invoking LLM for invoice data extraction")
        extracted = await llm_service.extract_json(
            raw_document_text=user_prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
        )
        log.info("LLM extraction returned structured JSON successfully")
    except Exception as exc:
        log.error(f"LLM extraction failed: {exc}")
        return ExtractionResult(
            format=DocumentFormat.PDF,
            extraction_method="llm_openrouter",
            success=False,
            source_data=None,
            canonical_candidate=None,
            warnings=[f"LLM extraction error: {type(exc).__name__}"],
            metadata=ExtractionMetadata(),
            error_message=str(exc),
        )

    # Build canonical candidate from LLM response
    try:
        line_items = []
        for idx, item in enumerate(extracted.get("line_items", []), start=1):
            line_items.append(
                CanonicalLineItemCandidate(
                    line_number=idx,
                    item_code=item.get("item_code"),
                    description=item.get("description", f"Item {idx}"),
                    quantity=item.get("quantity", "1"),
                    unit_price=item.get("unit_price", "0"),
                    discount_amount=item.get("discount_amount", "0"),
                    taxable_amount=item.get("taxable_amount"),
                    tax_rate=item.get("tax_rate"),
                    tax_amount=item.get("tax_amount", "0"),
                    line_total=item.get("line_total", "0"),
                    chassis_number=item.get("chassis_number"),
                )
            )

        candidate = CanonicalInvoiceCandidate(
            invoice_number=extracted.get("invoice_number", "UNKNOWN"),
            invoice_date=extracted.get("invoice_date", "1970-01-01"),
            buyer_oem_id=extracted.get("buyer_oem_id"),
            currency=extracted.get("currency", "USD"),
            subtotal_amount=extracted.get("subtotal"),
            tax_amount=extracted.get("tax_amount"),
            total_amount=extracted.get("total_amount", "0"),
            line_items=line_items,
        )

        return ExtractionResult(
            format=DocumentFormat.PDF,
            extraction_method="llm_openrouter",
            success=True,
            source_data=extracted,
            canonical_candidate=candidate,
            warnings=["Extracted via LLM (AI-assisted); heuristic parsing was insufficient"],
            metadata=ExtractionMetadata(
                field_confidence={
                    "invoice_number": 0.85,
                    "invoice_date": 0.85,
                    "currency": 0.85,
                    "total_amount": 0.80,
                    "line_items": 0.75,
                },
            ),
        )

    except Exception as exc:
        log.error(f"Failed to parse LLM extraction result into canonical structure: {exc}")
        return ExtractionResult(
            format=DocumentFormat.PDF,
            extraction_method="llm_openrouter",
            success=False,
            source_data=extracted,
            canonical_candidate=None,
            warnings=["LLM returned data but it could not be parsed into canonical format"],
            metadata=ExtractionMetadata(),
            error_message=f"Post-LLM parsing failed: {exc}",
        )


async def llm_normalize_any(raw_content: str, content_type: str = "unknown") -> ExtractionResult:
    """Use the LLM to normalize ANY incoming data format into structured invoice JSON.
    
    This handles edge cases like malformed CSVs, XML, email bodies, or any 
    non-standard format that the deterministic parsers cannot handle.
    """
    if not llm_service.is_configured:
        return ExtractionResult(
            format=DocumentFormat.UNKNOWN,
            extraction_method="llm_unavailable",
            success=False,
            source_data=None,
            canonical_candidate=None,
            warnings=["LLM service is not configured for normalization"],
            metadata=ExtractionMetadata(),
            error_message="OpenRouter API key is not configured",
        )

    user_prompt = (
        f"This document has content type '{content_type}'. "
        "Extract all invoice data from the following content into the specified JSON structure.\n\n"
        f"--- CONTENT ---\n{raw_content[:12000]}\n--- END ---"
    )

    try:
        log.info(f"Invoking LLM for normalization of {content_type} content")
        extracted = await llm_service.extract_json(
            raw_document_text=user_prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
        )
        log.info("LLM normalization returned structured JSON successfully")

        line_items = []
        for idx, item in enumerate(extracted.get("line_items", []), start=1):
            line_items.append(
                CanonicalLineItemCandidate(
                    line_number=idx,
                    item_code=item.get("item_code"),
                    description=item.get("description", f"Item {idx}"),
                    quantity=item.get("quantity", "1"),
                    unit_price=item.get("unit_price", "0"),
                    discount_amount=item.get("discount_amount", "0"),
                    taxable_amount=item.get("taxable_amount"),
                    tax_rate=item.get("tax_rate"),
                    tax_amount=item.get("tax_amount", "0"),
                    line_total=item.get("line_total", "0"),
                    chassis_number=item.get("chassis_number"),
                )
            )

        candidate = CanonicalInvoiceCandidate(
            invoice_number=extracted.get("invoice_number", "UNKNOWN"),
            invoice_date=extracted.get("invoice_date", "1970-01-01"),
            buyer_oem_id=extracted.get("buyer_oem_id"),
            currency=extracted.get("currency", "USD"),
            subtotal_amount=extracted.get("subtotal"),
            tax_amount=extracted.get("tax_amount"),
            total_amount=extracted.get("total_amount", "0"),
            line_items=line_items,
        )

        return ExtractionResult(
            format=DocumentFormat.UNKNOWN,
            extraction_method="llm_normalization",
            success=True,
            source_data=extracted,
            canonical_candidate=candidate,
            warnings=[f"Content normalized via LLM from {content_type}"],
            metadata=ExtractionMetadata(
                field_confidence={
                    "invoice_number": 0.80,
                    "invoice_date": 0.80,
                    "total_amount": 0.75,
                    "line_items": 0.70,
                },
            ),
        )

    except Exception as exc:
        log.error(f"LLM normalization failed: {exc}")
        return ExtractionResult(
            format=DocumentFormat.UNKNOWN,
            extraction_method="llm_normalization",
            success=False,
            source_data=None,
            canonical_candidate=None,
            warnings=[f"LLM normalization error: {type(exc).__name__}"],
            metadata=ExtractionMetadata(),
            error_message=str(exc),
        )


async def llm_map_to_canonical(source_data: Any) -> CanonicalInvoiceCandidate:
    """Use the LLM to map a parsed structured data extract (JSON/CSV) to the canonical OEM standard payload."""
    if not llm_service.is_configured:
        raise ValueError("LLM service is not configured; cannot perform AI mapping")

    user_prompt = (
        "Map the following data extract into the specified OEM standard JSON payload structure.\n\n"
        f"--- DATA EXTRACT ---\n{json.dumps(source_data, indent=2, default=str)[:12000]}\n--- END ---"
    )

    log.info("Invoking LLM for data mapping to canonical payload")
    extracted = await llm_service.extract_json(
        raw_document_text=user_prompt,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
    )
    
    line_items = []
    for idx, item in enumerate(extracted.get("line_items", []), start=1):
        line_items.append(
            CanonicalLineItemCandidate(
                line_number=idx,
                item_code=item.get("item_code"),
                description=item.get("description", f"Item {idx}"),
                quantity=item.get("quantity", "1"),
                unit_price=item.get("unit_price", "0"),
                discount_amount=item.get("discount_amount", "0"),
                taxable_amount=item.get("taxable_amount"),
                tax_rate=item.get("tax_rate"),
                tax_amount=item.get("tax_amount", "0"),
                line_total=item.get("line_total", "0"),
                chassis_number=item.get("chassis_number"),
            )
        )

    return CanonicalInvoiceCandidate(
        invoice_number=extracted.get("invoice_number", "UNKNOWN"),
        invoice_date=extracted.get("invoice_date", "1970-01-01"),
        buyer_oem_id=extracted.get("buyer_oem_id"),
        currency=extracted.get("currency", "USD"),
        subtotal_amount=extracted.get("subtotal"),
        tax_amount=extracted.get("tax_amount"),
        total_amount=extracted.get("total_amount", "0"),
        line_items=line_items,
    )


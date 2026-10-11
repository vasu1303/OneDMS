from __future__ import annotations

import io
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import log
from app.exceptions.handlers import NotFoundException, OneDMSException
from app.extraction.llm_extractor import llm_extract_invoice, llm_map_to_canonical, llm_normalize_any
from app.extraction.models import CanonicalInvoiceCandidate, DocumentFormat
from app.extraction.service import extraction_service
from app.models.invoice import (
    Dealer, InboundDocument, InvoiceLineItem, MappingConfig,
    StandardizedInvoice, ValidationRule,
)
from app.services.mapping import map_source_to_canonical
from app.services.storage import ObjectStorage
from app.services.validation import ValidationContext, get_overall_status, validate_canonical_payload


def sanitize_error(exc: Exception) -> str:
    """Sanitizes an exception message to prevent leaking credentials, stack traces, or raw provider bodies."""
    raw = str(exc)
    cleaned = re.sub(r"(key|secret|password|token)[=:][^\s,]+", r"\1=[REDACTED]", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"https?://[^\s]+@[^\s]+", "[REDACTED_URL]", cleaned)
    if len(cleaned) > 200:
        cleaned = cleaned[:197] + "..."
    return f"Processing failed: {cleaned}" if cleaned else "Processing failed due to an internal error."


def to_frontend_processing_status(db_status: str) -> str:
    mapping = {
        "RECEIVED": "received",
        "PROCESSING": "processing",
        "COMPLETED": "processed",
        "REVIEW_REQUIRED": "review_required",
        "FAILED": "failed",
    }
    return mapping.get(db_status, "received")


def to_frontend_validation_status(db_status: str) -> str:
    mapping = {
        "PENDING": "pending",
        "VALID": "valid",
        "INVALID": "invalid",
        "REVIEW_REQUIRED": "warning",
    }
    return mapping.get(db_status, "pending")


def to_frontend_review_status(db_status: str) -> str:
    mapping = {
        "NOT_REQUIRED": "pending",
        "PENDING": "in_review",
        "APPROVED": "approved",
        "REJECTED": "rejected",
    }
    return mapping.get(db_status, "pending")


def to_frontend_source_type(mime_or_format: str | None) -> str:
    if not mime_or_format:
        return "pdf"
    val = mime_or_format.lower()
    if "json" in val:
        return "json"
    if "csv" in val:
        return "csv"
    if "pdf" in val:
        return "pdf"
    if "xls" in val or "excel" in val or "spreadsheetml" in val:
        return "excel"
    if "xml" in val:
        return "xml"
    return "pdf"


def serialize_document_for_frontend(doc: InboundDocument) -> dict[str, Any]:
    """Formats an InboundDocument into the DocumentDetail shape expected by the frontend."""
    inv = doc.invoice
    val_status = inv.validation_status if inv else "PENDING"
    rev_status = inv.review_status if inv else "NOT_REQUIRED"

    findings = []
    if inv and inv.canonical_payload and "_onedms" in inv.canonical_payload:
        findings = inv.canonical_payload["_onedms"].get("validation", {}).get("issues", [])

    return {
        "id": doc.id,
        "dealer_code": doc.dealer.dealer_code if doc.dealer else f"D-{doc.dealer_id}",
        "dealer_name": doc.dealer.name if doc.dealer else None,
        "dms_name": doc.dms.name if doc.dms else None,
        "source_type": to_frontend_source_type(doc.mime_type or (doc.dms.input_format if doc.dms else None)),
        "source_filename": doc.original_file_name,
        "received_at": doc.received_at.isoformat() if doc.received_at else datetime.now(timezone.utc).isoformat(),
        "processing_status": to_frontend_processing_status(doc.status),
        "validation_status": to_frontend_validation_status(val_status),
        "review_status": to_frontend_review_status(rev_status),
        "summary": doc.error_message or ("Invoice extracted successfully." if doc.status == "COMPLETED" else None),
        "has_findings": len(findings) > 0,
        "findings_count": len(findings),
        "invoice_id": inv.id if inv else None,
        "source_content_type": doc.mime_type,
        "source_size_bytes": doc.file_size_bytes,
        "checksum_sha256": doc.checksum_sha256,
        "last_error": doc.error_message,
        # Backward compatibility for direct schema consumers
        "status": doc.status,
        "document_type": doc.document_type,
    }


def serialize_invoice_for_frontend(inv: StandardizedInvoice) -> dict[str, Any]:
    """Formats a StandardizedInvoice into the InvoiceDetail shape expected by the frontend."""
    doc = inv.document
    canonical = inv.canonical_payload or {}
    raw_findings = canonical.get("_onedms", {}).get("validation", {}).get("issues", [])

    frontend_findings = []
    for idx, f in enumerate(raw_findings, start=1):
        frontend_findings.append({
            "id": idx,
            "severity": f.get("severity", "info").lower(),
            "field": f.get("field"),
            "line_number": f.get("line_number"),
            "message": f.get("message", f"Finding {idx}"),
            "confidence": f.get("confidence", 0.95),
            "extracted_value": f.get("extracted_value"),
            "approved_value": f.get("approved_value"),
        })

    lines = []
    for line in inv.line_items:
        lines.append({
            "id": line.id,
            "line_number": line.line_number,
            "part_number": line.item_code,
            "description": line.description,
            "quantity": float(line.quantity),
            "unit_price": float(line.unit_price),
            "discount_amount": float(line.discount_amount),
            "tax_amount": float(line.tax_amount),
            "line_total": float(line.line_total),
            "vin": line.chassis_number,
        })

    subtotal_val = float(inv.subtotal) if inv.subtotal is not None else 0.0
    discount_val = float(canonical.get("discount_amount", 0.0))
    tax_val = float(inv.tax_amount) if inv.tax_amount is not None else 0.0
    total_val = float(inv.total_amount) if inv.total_amount is not None else (subtotal_val + tax_val)

    delivery_status = "delivered" if inv.oem_delivery_status == "SENT" else "pending"

    return {
        "id": inv.id,
        "document_id": inv.document_id,
        "buyer_oem_id": inv.buyer_oem_id,
        "processing_status": to_frontend_processing_status(doc.status if doc else "COMPLETED"),
        "validation_status": to_frontend_validation_status(inv.validation_status),
        "review_status": to_frontend_review_status(inv.review_status),
        "delivery_status": delivery_status,
        "header": {
            "invoice_number": inv.invoice_number,
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "dealer_invoice_ref": canonical.get("dealer_invoice_ref", inv.invoice_number),
            "currency_code": inv.currency,
            "subtotal_amount": subtotal_val,
            "discount_amount": discount_val,
            "tax_amount": tax_val,
            "total_amount": total_val,
        },
        "line_items": lines,
        "findings": frontend_findings,
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
    }


class WorkflowService:
    """Orchestrates the end-to-end invoice processing workflow: extraction → mapping → validation → persistence."""

    @staticmethod
    async def _load_validation_rules(session: AsyncSession) -> list[dict]:
        """Load all active validation rules for invoices from the database."""
        stmt = select(ValidationRule).where(
            ValidationRule.document_type == "INVOICE",
            ValidationRule.is_active == True,  # noqa: E712
        )
        result = await session.execute(stmt)
        return [
            {
                "rule_code": r.rule_code,
                "severity": r.severity,
                "rule_config": r.rule_config,
            }
            for r in result.scalars().all()
        ]

    @staticmethod
    async def _is_registered_dealer(session: AsyncSession, dealer_code: str) -> bool:
        """Check if a dealer code exists in the database."""
        stmt = select(func.count()).select_from(Dealer).where(Dealer.dealer_code == dealer_code)
        count = await session.scalar(stmt)
        return count > 0

    @staticmethod
    async def _is_duplicate_invoice(session: AsyncSession, dealer_code: str, invoice_number: str, invoice_date: str) -> bool:
        """Check if an invoice with the same dealer, number, and date already exists."""
        try:
            parsed_date = date.fromisoformat(invoice_date)
        except (ValueError, TypeError):
            return False

        stmt = (
            select(func.count())
            .select_from(StandardizedInvoice)
            .join(InboundDocument, StandardizedInvoice.document_id == InboundDocument.id)
            .join(Dealer, InboundDocument.dealer_id == Dealer.id)
            .where(
                Dealer.dealer_code == dealer_code,
                StandardizedInvoice.invoice_number == invoice_number,
                StandardizedInvoice.invoice_date == parsed_date,
            )
        )
        count = await session.scalar(stmt)
        return count > 0

    @staticmethod
    async def _build_canonical_from_candidate(
        candidate: CanonicalInvoiceCandidate, dealer_code: str | None
    ) -> dict[str, Any]:
        """Convert a CanonicalInvoiceCandidate (from PDF/LLM extraction) into a dict."""
        candidate_lines = []
        for l in candidate.line_items:
            candidate_lines.append({
                "line_number": l.line_number,
                "item_code": l.item_code,
                "description": l.description,
                "quantity": str(l.quantity),
                "unit_price": str(l.unit_price),
                "discount_amount": str(l.discount_amount),
                "taxable_amount": str(l.taxable_amount or (l.quantity * l.unit_price)),
                "tax_rate": str(l.tax_rate) if l.tax_rate is not None else None,
                "tax_amount": str(l.tax_amount),
                "line_total": str(l.line_total),
                "chassis_number": l.chassis_number,
                "item_category": "VEHICLE" if l.chassis_number else "PART",
            })

        return {
            "invoice_number": candidate.invoice_number,
            "invoice_date": candidate.invoice_date,
            "supplier_dealer_code": dealer_code,
            "buyer_oem_id": candidate.buyer_oem_id,
            "currency": candidate.currency,
            "subtotal": str(candidate.subtotal_amount or (candidate.total_amount - (candidate.tax_amount or Decimal("0.0")))),
            "tax_amount": str(candidate.tax_amount or Decimal("0.0")),
            "total_amount": str(candidate.total_amount),
            "line_items": candidate_lines,
        }

    @staticmethod
    async def process_document(
        session: AsyncSession,
        document_id: int,
        storage: ObjectStorage | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Runs the extraction, mapping, validation, and persistence pipeline atomically.

        Integrates deterministic extraction, LLM fallback, mapping & validation engines.
        Ensures idempotency, atomic persistence, and consistent status transitions.
        """
        # 1. Fetch document with dealer, dms, and existing invoice
        stmt = (
            select(InboundDocument)
            .options(
                selectinload(InboundDocument.dealer),
                selectinload(InboundDocument.dms),
                selectinload(InboundDocument.invoice).selectinload(StandardizedInvoice.line_items),
            )
            .where(InboundDocument.id == document_id)
        )
        result = await session.execute(stmt)
        document = result.scalar_one_or_none()

        if document is None:
            raise NotFoundException(f"Document with ID {document_id} not found")

        # 2. Check existing invoice & idempotency
        existing_invoice = document.invoice
        if existing_invoice is not None:
            if existing_invoice.review_status == "APPROVED":
                raise OneDMSException(
                    "Invoice has already been approved and cannot be reprocessed.",
                    status_code=409,
                )
            if not force:
                log.info(f"Document {document_id} already has an existing invoice; returning current state")
                return serialize_document_for_frontend(document)

        # 3. Transition document to PROCESSING
        document.status = "PROCESSING"
        document.error_message = None
        await session.flush()

        try:
            # 4. Load raw source data or file bytes
            content: bytes | str
            content_type = document.mime_type or "application/octet-stream"

            if document.raw_payload is not None:
                content = json.dumps(document.raw_payload)
                content_type = "application/json"
            elif document.storage_key:
                if storage is None:
                    raise OneDMSException("Object storage is required to process stored file", status_code=503)
                file_bytes, storage_content_type = await storage.get_file_bytes(document.storage_key)
                content = file_bytes
                content_type = document.mime_type or storage_content_type
            else:
                raise OneDMSException(
                    "Document has no raw payload and no storage key; cannot process.",
                    status_code=422,
                )

            # 5. Invoke deterministic extraction engine
            log.info(f"Extracting document {document_id} using ExtractionService")
            extraction_result = extraction_service.extract_document(
                content=content,
                filename=document.original_file_name,
                content_type=content_type,
            )

            # 6. If deterministic extraction failed, fall back to LLM
            if not extraction_result.success:
                log.warning(
                    f"Deterministic extraction failed for document {document_id}: "
                    f"{extraction_result.error_message}. Attempting LLM fallback."
                )

            # 6. Transform to canonical representation
            canonical: dict[str, Any]

            if extraction_result.format in (DocumentFormat.JSON, DocumentFormat.CSV, DocumentFormat.EXCEL):
                # Load active mapping config (SOURCE_TO_CANONICAL) for dms_id
                map_stmt = select(MappingConfig).where(
                    MappingConfig.mapping_direction == "SOURCE_TO_CANONICAL",
                    MappingConfig.dms_id == document.dms_id,
                    MappingConfig.document_type == "INVOICE",
                    MappingConfig.is_active == True,  # noqa: E712
                )
                map_res = await session.execute(map_stmt)
                active_mapping = map_res.scalar_one_or_none()

                mapping_config = active_mapping.mapping_config if active_mapping else {
                    "invoice_number": "invoiceNo",
                    "invoice_date": "billDate",
                    "supplier_dealer_code": "dealerCode",
                    "buyer_oem_id": "buyerCode",
                    "currency": "currencyCode",
                    "subtotal": "subTotal",
                    "tax_amount": "taxTotal",
                    "total_amount": "grandTotal",
                    "line_items": {
                        "source_field": "items",
                        "item_code": "sku",
                        "description": "description",
                        "quantity": "qty",
                        "unit_price": "rate",
                        "discount_amount": "discount",
                        "taxable_amount": "taxableValue",
                        "tax_rate": "taxRate",
                        "tax_amount": "taxAmount",
                        "line_total": "lineTotal",
                        "chassis_number": "chassisNo",
                        "item_category": "category",
                    },
                }

                source_data = extraction_result.source_data
                if isinstance(source_data, list):
                    if not source_data:
                        raise OneDMSException("Spreadsheet or CSV has no invoice line rows", status_code=422)
                    # Header fields map from the first row; line fields map over all rows.
                    source_dict = {**source_data[0], "rows": source_data}
                    canonical = map_source_to_canonical(source_dict, mapping_config)
            else:
                # Convert content to text for LLM
                if isinstance(content, bytes):
                    # For PDFs, try to extract text first with pdfplumber
                    try:
                        import pdfplumber
                        with pdfplumber.open(io.BytesIO(content)) as pdf:
                            raw_text = "\n".join(
                                page.extract_text() or "" for page in pdf.pages
                            )
                    except Exception:
                        raw_text = content.decode("utf-8", errors="replace")
                else:
                    raw_text = content

                if raw_text.strip():
                    if "pdf" in content_type.lower():
                        extraction_result = await llm_extract_invoice(raw_text)
                    else:
                        extraction_result = await llm_normalize_any(raw_text, content_type)

                if not extraction_result.success:
                    raise OneDMSException(
                        extraction_result.error_message or "Extraction failed after LLM fallback",
                        status_code=422,
                    )

            # 7. Transform to canonical representation
            canonical: dict[str, Any]
            dealer_code = document.dealer.dealer_code if document.dealer else None

            # Always pass the parsed data extract through the LLM to map to OEM standard payload
            raw_extracted_data = extraction_result.source_data
            if extraction_result.canonical_candidate is not None:
                # If local pdfplumber or LLM fallback structured it, pass that structure to the LLM mapper
                raw_extracted_data = extraction_result.canonical_candidate.model_dump(mode="json")

            try:
                candidate = await llm_map_to_canonical(raw_extracted_data)
                canonical = await WorkflowService._build_canonical_from_candidate(
                    candidate, dealer_code
                )
            except Exception as exc:
                raise OneDMSException(f"Failed to map data extract to canonical invoice: {exc}", status_code=422)

            # Ensure header supplier code is populated from document relationship
            if not canonical.get("supplier_dealer_code") and dealer_code:
                canonical["supplier_dealer_code"] = dealer_code

            # 8. Invoke validation engine with real DB context
            rules_config_list = await WorkflowService._load_validation_rules(session)

            # Build validation context with real database lookups
            # We need to capture the session in closures for sync callbacks
            # Since validation is sync, we pre-fetch the necessary data
            dealer_code_for_validation = canonical.get("supplier_dealer_code", "")
            dealer_exists = await WorkflowService._is_registered_dealer(session, dealer_code_for_validation) if dealer_code_for_validation else False

            inv_number = canonical.get("invoice_number", "")
            inv_date = canonical.get("invoice_date", "")
            is_duplicate = await WorkflowService._is_duplicate_invoice(
                session, dealer_code_for_validation, inv_number, inv_date
            ) if dealer_code_for_validation and inv_number and inv_date else False

            context = ValidationContext(
                is_registered_dealer=lambda d_code: dealer_exists if d_code == dealer_code_for_validation else False,
                is_duplicate_invoice=lambda d, inv, dt: is_duplicate if (d == dealer_code_for_validation and inv == inv_number and dt == inv_date) else False,
            )

            validation_findings = validate_canonical_payload(canonical, rules_config_list, context)
            overall_status = get_overall_status(validation_findings)

            # 9. Record metadata in canonical_payload
            raw_issues = [
                {
                    "rule_code": f.rule_code,
                    "severity": f.severity,
                    "message": f.message,
                    "field": f.field,
                    "line_number": f.line_number,
                    "confidence": 0.95,
                }
                for f in validation_findings
                if not f.is_valid
            ]

            canonical["_onedms"] = {
                "extraction": {
                    "method": extraction_result.extraction_method,
                    "format": extraction_result.format.value,
                    "warnings": extraction_result.warnings,
                },
                "validation": {
                    "status": overall_status,
                    "issues": raw_issues,
                },
            }

            # 10. Status transitions
            if overall_status == "INVALID":
                doc_status = "REVIEW_REQUIRED"
                inv_validation_status = "INVALID"
                inv_review_status = "PENDING"
            elif overall_status == "REVIEW_REQUIRED":
                doc_status = "REVIEW_REQUIRED"
                inv_validation_status = "REVIEW_REQUIRED"
                inv_review_status = "PENDING"
            else:
                doc_status = "COMPLETED"
                inv_validation_status = "VALID"
                inv_review_status = "NOT_REQUIRED"

            # Parse date safely
            try:
                parsed_date = date.fromisoformat(str(canonical.get("invoice_date")))
            except Exception:
                parsed_date = date.today()

            subtotal_num = Decimal(str(canonical.get("subtotal") or 0)).quantize(Decimal("0.01"))
            tax_num = Decimal(str(canonical.get("tax_amount") or 0)).quantize(Decimal("0.01"))
            total_num = Decimal(str(canonical.get("total_amount") or (subtotal_num + tax_num))).quantize(Decimal("0.01"))

            # 11. Atomic Persistence (update existing or create new)
            if existing_invoice is not None:
                invoice = existing_invoice
                invoice.invoice_number = str(canonical.get("invoice_number"))
                invoice.invoice_date = parsed_date
                invoice.buyer_oem_id = str(canonical.get("buyer_oem_id") or "")
                invoice.currency = str(canonical.get("currency") or "INR")[:3]
                invoice.subtotal = subtotal_num
                invoice.tax_amount = tax_num
                invoice.total_amount = total_num
                invoice.canonical_payload = canonical
                invoice.validation_status = inv_validation_status
                invoice.review_status = inv_review_status
                await session.execute(
                    delete(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
                )
            else:
                invoice = StandardizedInvoice(
                    document_id=document.id,
                    invoice_number=str(canonical.get("invoice_number")),
                    invoice_date=parsed_date,
                    buyer_oem_id=str(canonical.get("buyer_oem_id") or ""),
                    currency=str(canonical.get("currency") or "INR")[:3],
                    subtotal=subtotal_num,
                    tax_amount=tax_num,
                    total_amount=total_num,
                    canonical_payload=canonical,
                    validation_status=inv_validation_status,
                    review_status=inv_review_status,
                    oem_delivery_status="NOT_SENT",
                )
                session.add(invoice)
                await session.flush()

            # Insert canonical line items
            canonical_lines = canonical.get("line_items", [])
            for idx, item in enumerate(canonical_lines, start=1):
                qty = Decimal(str(item.get("quantity") or 1))
                price = Decimal(str(item.get("unit_price") or 0))
                disc = Decimal(str(item.get("discount_amount") or 0))
                taxable = Decimal(str(item.get("taxable_amount") or (qty * price - disc)))
                tax_rate_str = item.get("tax_rate")
                tax_rate = Decimal(str(tax_rate_str)) if tax_rate_str is not None else None
                tax_amt = Decimal(str(item.get("tax_amount") or 0))
                line_total = Decimal(str(item.get("line_total") or (taxable + tax_amt)))

                line = InvoiceLineItem(
                    invoice_id=invoice.id,
                    line_number=idx,
                    item_code=item.get("item_code"),
                    description=item.get("description") or f"Item {idx}",
                    quantity=qty,
                    unit_price=price,
                    discount_amount=disc,
                    taxable_amount=taxable,
                    tax_rate=tax_rate,
                    tax_amount=tax_amt,
                    line_total=line_total,
                    chassis_number=item.get("chassis_number"),
                )
                session.add(line)

            # Update document state
            document.status = doc_status
            document.error_message = (
                "Validation issues identified. Review required."
                if doc_status == "REVIEW_REQUIRED"
                else None
            )

            await session.commit()
            await session.refresh(document)
            await session.refresh(invoice)
            document.invoice = invoice

            return serialize_document_for_frontend(document)

        except Exception as exc:
            log.error(f"Processing failed for document {document_id}: {exc}")
            await session.rollback()

            sanitized = sanitize_error(exc)
            document.status = "FAILED"
            document.error_message = sanitized
            session.add(document)
            await session.commit()

            raise OneDMSException(sanitized, status_code=422) from exc

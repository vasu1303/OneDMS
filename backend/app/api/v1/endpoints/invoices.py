from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps.db import get_db_session
from app.exceptions.handlers import OneDMSException
from app.models.invoice import InboundDocument, InvoiceLineItem, MappingConfig, StandardizedInvoice, ValidationRule
from app.services.oem import OEMExportService
from app.services.validation import ValidationContext, get_overall_status, validate_canonical_payload
from app.services.workflow import serialize_invoice_for_frontend

router = APIRouter()


@router.get("")
async def list_invoices(
    validation_status: str | None = None,
    review_status: str | None = None,
    delivery_status: str | None = None,
    search: str | None = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db_session),
):
    """
    List standardized invoices with status filtering, search, and pagination.
    Returns items envelope compatible with frontend getInvoices.
    """
    query = (
        select(StandardizedInvoice)
        .options(
            selectinload(StandardizedInvoice.line_items),
            selectinload(StandardizedInvoice.document).selectinload(InboundDocument.dealer),
            selectinload(StandardizedInvoice.document).selectinload(InboundDocument.dms),
        )
        .order_by(StandardizedInvoice.created_at.desc())
    )

    if validation_status and validation_status != "all":
        val_map = {"valid": "VALID", "invalid": "INVALID", "warning": "REVIEW_REQUIRED", "pending": "PENDING"}
        db_val = val_map.get(validation_status.lower(), validation_status.upper())
        query = query.where(StandardizedInvoice.validation_status == db_val)

    if review_status and review_status != "all":
        rev_map = {"approved": "APPROVED", "rejected": "REJECTED", "in_review": "PENDING", "pending": "NOT_REQUIRED"}
        db_rev = rev_map.get(review_status.lower(), review_status.upper())
        query = query.where(StandardizedInvoice.review_status == db_rev)

    if search:
        query = query.where(StandardizedInvoice.invoice_number.ilike(f"%{search}%"))

    offset = max(0, (page - 1) * size)
    query = query.offset(offset).limit(size)

    invoices = (await db.execute(query)).scalars().all()
    items = [serialize_invoice_for_frontend(inv) for inv in invoices]

    return {"items": items, "total": len(items), "page": page, "size": size}


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Retrieve full standardized invoice detail with line items and validation findings.
    """
    stmt = (
        select(StandardizedInvoice)
        .options(
            selectinload(StandardizedInvoice.line_items),
            selectinload(StandardizedInvoice.document).selectinload(InboundDocument.dealer),
            selectinload(StandardizedInvoice.document).selectinload(InboundDocument.dms),
        )
        .where(StandardizedInvoice.id == invoice_id)
    )
    inv = (await db.execute(stmt)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    return serialize_invoice_for_frontend(inv)


@router.patch("/{invoice_id}")
async def patch_invoice(
    invoice_id: int,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
):
    """
    Applies auditor corrections to invoice header and line items, re-validates, and persists.
    """
    stmt = (
        select(StandardizedInvoice)
        .options(
            selectinload(StandardizedInvoice.line_items),
            selectinload(StandardizedInvoice.document).selectinload(InboundDocument.dealer),
        )
        .where(StandardizedInvoice.id == invoice_id)
    )
    inv = (await db.execute(stmt)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    if inv.review_status == "APPROVED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot modify an already approved invoice.")

    # 1. Update header fields
    raw_header = payload.get("header", {})
    if "invoice_number" in raw_header and raw_header["invoice_number"]:
        inv.invoice_number = str(raw_header["invoice_number"])
    if "invoice_date" in raw_header and raw_header["invoice_date"]:
        try:
            inv.invoice_date = date.fromisoformat(str(raw_header["invoice_date"]))
        except Exception:
            pass
    if "currency_code" in raw_header and raw_header["currency_code"]:
        inv.currency = str(raw_header["currency_code"])[:3]
    if "subtotal_amount" in raw_header:
        inv.subtotal = Decimal(str(raw_header["subtotal_amount"])).quantize(Decimal("0.01"))
    if "tax_amount" in raw_header:
        inv.tax_amount = Decimal(str(raw_header["tax_amount"])).quantize(Decimal("0.01"))
    if "total_amount" in raw_header:
        inv.total_amount = Decimal(str(raw_header["total_amount"])).quantize(Decimal("0.01"))

    # 2. Update line items
    raw_lines = payload.get("line_items", [])
    lines_by_no = {line.line_number: line for line in inv.line_items}

    for raw_l in raw_lines:
        line_no = raw_l.get("line_number")
        existing_l = lines_by_no.get(line_no)
        if existing_l:
            if "part_number" in raw_l:
                existing_l.item_code = raw_l["part_number"]
            if "description" in raw_l:
                existing_l.description = raw_l["description"] or ""
            if "quantity" in raw_l:
                existing_l.quantity = Decimal(str(raw_l["quantity"]))
            if "unit_price" in raw_l:
                existing_l.unit_price = Decimal(str(raw_l["unit_price"]))
            if "discount_amount" in raw_l:
                existing_l.discount_amount = Decimal(str(raw_l["discount_amount"]))
            if "tax_amount" in raw_l:
                existing_l.tax_amount = Decimal(str(raw_l["tax_amount"]))
            if "line_total" in raw_l:
                existing_l.line_total = Decimal(str(raw_l["line_total"]))
            if "vin" in raw_l:
                existing_l.chassis_number = raw_l["vin"]

    # 3. Rebuild canonical payload
    canonical = dict(inv.canonical_payload) if inv.canonical_payload else {}
    canonical["invoice_number"] = inv.invoice_number
    canonical["invoice_date"] = inv.invoice_date.isoformat()
    canonical["currency"] = inv.currency
    canonical["subtotal"] = str(inv.subtotal)
    canonical["tax_amount"] = str(inv.tax_amount)
    canonical["total_amount"] = str(inv.total_amount)
    if "dealer_invoice_ref" in raw_header:
        canonical["dealer_invoice_ref"] = raw_header["dealer_invoice_ref"]

    payload_lines = []
    for line in inv.line_items:
        payload_lines.append({
            "line_number": line.line_number,
            "item_code": line.item_code,
            "description": line.description,
            "quantity": str(line.quantity),
            "unit_price": str(line.unit_price),
            "discount_amount": str(line.discount_amount),
            "taxable_amount": str(line.taxable_amount or (line.quantity * line.unit_price)),
            "tax_rate": str(line.tax_rate) if line.tax_rate is not None else None,
            "tax_amount": str(line.tax_amount),
            "line_total": str(line.line_total),
            "chassis_number": line.chassis_number,
            "item_category": "VEHICLE" if line.chassis_number else "PART",
        })
    canonical["line_items"] = payload_lines

    # 4. Re-run Person 3 validation
    rules_stmt = select(ValidationRule).where(
        ValidationRule.document_type == "INVOICE",
        ValidationRule.is_active == True,  # noqa: E712
    )
    rules_res = await db.execute(rules_stmt)
    active_rules = rules_res.scalars().all()

    rules_config_list = [
        {"rule_code": r.rule_code, "severity": r.severity, "rule_config": r.rule_config}
        for r in active_rules
    ]

    context = ValidationContext(
        is_registered_dealer=lambda _: True,
        is_duplicate_invoice=lambda *_: False,
    )

    validation_findings = validate_canonical_payload(canonical, rules_config_list, context)
    overall_status = get_overall_status(validation_findings)

    # 5. Update _onedms metadata
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

    onedms_meta = canonical.get("_onedms", {})
    onedms_meta["validation"] = {"status": overall_status, "issues": raw_issues}
    onedms_meta["review"] = {
        "last_action": "CORRECTED",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    canonical["_onedms"] = onedms_meta
    inv.canonical_payload = canonical

    # 6. Update statuses
    if overall_status == "INVALID":
        inv.validation_status = "INVALID"
    elif overall_status == "REVIEW_REQUIRED":
        inv.validation_status = "REVIEW_REQUIRED"
    else:
        inv.validation_status = "VALID"

    await db.commit()
    await db.refresh(inv)

    return serialize_invoice_for_frontend(inv)


@router.post("/{invoice_id}/review")
async def review_invoice(
    invoice_id: int,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
):
    """
    Auditor approval or rejection of an invoice.
    Rejects approval while INVALID unless force_override is explicitly specified.
    """
    stmt = (
        select(StandardizedInvoice)
        .options(
            selectinload(StandardizedInvoice.line_items),
            selectinload(StandardizedInvoice.document).selectinload(InboundDocument.dealer),
        )
        .where(StandardizedInvoice.id == invoice_id)
    )
    inv = (await db.execute(stmt)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    decision = str(payload.get("decision", "")).lower()
    notes = payload.get("notes")
    force_override = bool(payload.get("force_override", False))

    if decision == "approve":
        if inv.validation_status == "INVALID" and not force_override:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot approve an INVALID invoice. Please correct validation errors first.",
            )
        inv.review_status = "APPROVED"
        if inv.document and inv.document.status == "REVIEW_REQUIRED":
            inv.document.status = "COMPLETED"
            inv.document.error_message = None

    elif decision == "reject":
        inv.review_status = "REJECTED"
        if inv.document:
            inv.document.status = "FAILED"
            inv.document.error_message = f"Rejected during audit review: {notes or 'No reason provided'}"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported decision '{decision}'. Expected 'approve' or 'reject'.",
        )

    # Update _onedms review record
    canonical = dict(inv.canonical_payload) if inv.canonical_payload else {}
    onedms_meta = canonical.get("_onedms", {})
    onedms_meta["review"] = {
        "decision": decision.upper(),
        "notes": notes,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    canonical["_onedms"] = onedms_meta
    inv.canonical_payload = canonical

    await db.commit()
    await db.refresh(inv)

    return serialize_invoice_for_frontend(inv)


@router.post("/{invoice_id}/oem-preview")
@router.get("/{invoice_id}/mock-oem")
async def preview_mock_oem(
    invoice_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Generates preview of deterministic Daimler OEM payload (no external network call).
    Strips internal _onedms metadata.
    """
    stmt = (
        select(StandardizedInvoice)
        .options(selectinload(StandardizedInvoice.line_items))
        .where(StandardizedInvoice.id == invoice_id)
    )
    inv = (await db.execute(stmt)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    mapping_stmt = select(MappingConfig).where(
        MappingConfig.mapping_direction == "CANONICAL_TO_OEM",
        MappingConfig.is_active == True,  # noqa: E712
    )
    mapping_res = await db.execute(mapping_stmt)
    mapping_config = mapping_res.scalar_one_or_none()

    res = OEMExportService.generate_oem_payload(inv, mapping_config)
    return res.model_dump()

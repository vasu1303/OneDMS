"""Approved canonical invoice copies; no source documents or settings access."""

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from io import BytesIO
import re

from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.invoice import StandardizedInvoice


@dataclass(frozen=True)
class InvoicePDFLine:
    number: int
    item_code: str | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    taxable: Decimal
    tax_rate: Decimal | None
    tax: Decimal
    total: Decimal
    chassis: str | None


@dataclass(frozen=True)
class InvoicePDFData:
    number: str
    date: str
    dealer: str | None
    dealer_code: str | None
    buyer: str
    currency: str
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    lines: tuple[InvoicePDFLine, ...]


def snapshot_invoice(invoice: StandardizedInvoice) -> InvoicePDFData:
    """Copy only business fields while eager ORM relationships are on the event loop."""
    dealer = invoice.document.dealer if invoice.document is not None else None
    return InvoicePDFData(
        number=invoice.invoice_number, date=invoice.invoice_date.isoformat(),
        dealer=dealer.name if dealer is not None else None,
        dealer_code=dealer.dealer_code if dealer is not None else None,
        buyer=invoice.buyer_oem_id, currency=invoice.currency,
        subtotal=invoice.subtotal, tax=invoice.tax_amount, total=invoice.total_amount,
        lines=tuple(InvoicePDFLine(
            number=line.line_number, item_code=line.item_code, description=line.description,
            quantity=line.quantity, unit_price=line.unit_price, discount=line.discount_amount,
            taxable=line.taxable_amount, tax_rate=line.tax_rate, tax=line.tax_amount,
            total=line.line_total, chassis=line.chassis_number,
        ) for line in sorted(invoice.line_items, key=lambda line: line.line_number)),
    )


def invoice_pdf_filename(invoice_number: str) -> str:
    """ASCII-only, bounded attachment name; no paths, quotes, or header controls."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", invoice_number).strip("-_")[:80]
    return f"invoice-{slug or 'approved'}.pdf"


def _text(value: object) -> str:
    return escape(str(value) if value is not None else "-", quote=True).replace("\n", "<br/>")


def _decimal(value: Decimal | None, places: int = 2) -> str:
    # Never convert to float: database monetary and quantity scales remain exact.
    return format(value, f".{places}f") if value is not None else "-"


def generate_invoice_pdf(invoice: InvoicePDFData) -> bytes:
    """Render a detached canonical snapshot entirely in memory."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=36, rightMargin=36,
        topMargin=76, bottomMargin=44, title="Standardized invoice copy",
        author="OneDMS", subject="Approved canonical invoice; not an OEM-issued original",
    )
    body = ParagraphStyle("InvoiceBody", fontName="Helvetica", fontSize=9, leading=12)
    cell = ParagraphStyle("InvoiceCell", parent=body, fontSize=8, leading=11)
    numeric = ParagraphStyle("InvoiceNumeric", parent=cell, alignment=TA_RIGHT)
    heading = ParagraphStyle("InvoiceHeading", parent=body, fontName="Helvetica-Bold", fontSize=15, leading=19)

    def paragraph(value: object, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(_text(value), style)

    def page_frame(canvas, doc):
        canvas.saveState()
        width, height = doc.pagesize
        title = paragraph("STANDARDIZED INVOICE COPY", heading)
        title.wrap(doc.width, 22)
        title.drawOn(canvas, doc.leftMargin, height - 36)
        disclaimer = paragraph("Approved canonical copy - not an OEM-issued original.")
        disclaimer.wrap(doc.width, 18)
        disclaimer.drawOn(canvas, doc.leftMargin, height - 54)
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.line(doc.leftMargin, height - 63, width - doc.rightMargin, height - 63)
        canvas.line(doc.leftMargin, 34, width - doc.rightMargin, 34)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawString(doc.leftMargin, 21, "Standardized copy | OneDMS")
        canvas.drawRightString(width - doc.rightMargin, 21, f"Page {doc.page}")
        canvas.restoreState()

    details = Table([
        [paragraph(f"Invoice number: {invoice.number}"), paragraph(f"Invoice date: {invoice.date}")],
        [paragraph(f"Dealer: {invoice.dealer or '-'}"), paragraph(f"Dealer code: {invoice.dealer_code or '-'}")],
        [paragraph(f"Buyer: {invoice.buyer}"), paragraph(f"Currency: {invoice.currency}")],
    ], colWidths=[document.width * 0.6, document.width * 0.4])
    details.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story = [details, Spacer(1, 14)]
    headers = ["Line", "Description / Item code", "Quantity", "Unit price", "Discount", "Taxable", "Tax rate %", "Tax", "Total"]
    rows = [[paragraph(label, cell) for label in headers]]
    for line in sorted(invoice.lines, key=lambda line: line.number):
        description = _text(line.description)
        if line.item_code:
            description += "<br/><b>Item code:</b> " + _text(line.item_code)
        if line.chassis:
            description += "<br/><b>Chassis:</b> " + _text(line.chassis)
        rows.append([
            paragraph(line.number, cell), Paragraph(description, cell),
            paragraph(_decimal(line.quantity, 3), numeric),
            *[paragraph(_decimal(value), numeric) for value in (
                line.unit_price, line.discount, line.taxable, line.tax_rate, line.tax, line.total,
            )],
        ])
    weights = [26, 219, 58, 78, 70, 80, 60, 80, 99]
    table = Table(
        rows, colWidths=[document.width * weight / sum(weights) for weight in weights],
        repeatRows=1, splitByRow=1, splitInRow=1, hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#94a3b8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 16)])
    totals = Table([
        [paragraph(label), paragraph(_decimal(value), numeric)]
        for label, value in (("Subtotal", invoice.subtotal), ("Tax amount", invoice.tax), ("Grand total", invoice.total))
    ], colWidths=[130, 120], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(totals)
    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return buffer.getvalue()


async def invoice_pdf_response(invoice: StandardizedInvoice) -> Response:
    snapshot = snapshot_invoice(invoice)
    content = await asyncio.to_thread(generate_invoice_pdf, snapshot)
    return Response(
        content=content, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice_pdf_filename(snapshot.number)}"'},
    )
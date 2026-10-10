"""Generate and verify a synthetic invoice; no database, storage, or LLM calls."""

from pathlib import Path
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.extraction.service import extraction_service
from app.services.validation import ValidationContext, get_overall_status, validate_canonical_payload


def main():
    destination = ROOT / "docs" / "testing" / "onedms_test_invoice.pdf"
    destination.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("OneDMS synthetic test invoice", styles["Title"]),
        Spacer(1, 16),
    ]
    for text in [
        "Invoice No: ONEDMS-PDF-TEST-20261010",
        "Invoice Date: 2026-10-10",
        "Supplier: Demo North Trucks (ONEDMS-DEMO-API)",
        "Buyer Code: DAIMLER-DEMO",
        "Currency: INR",
        "Synthetic spare-parts invoice. No real transaction or tax claim.",
        "Zero tax is intentional for this local parser smoke test.",
    ]:
        story.extend([Paragraph(text, styles["Normal"]), Spacer(1, 7)])
    story.append(Spacer(1, 12))
    table = Table([
        ["Item Code", "Description", "Qty", "Unit Price", "Line Total"],
        ["PART-BRAKE", "Brake pad kit", "2", "300.00", "600.00"],
        ["PART-FILTER", "Air filter", "1", "400.00", "400.00"],
    ], colWidths=[100, 145, 40, 80, 90], rowHeights=30)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#526579")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4edf7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
    ]))
    story.extend([table, Spacer(1, 18)])
    for text in ["Subtotal: 1000.00", "Tax Amount: 0.00", "Grand Total: 1000.00"]:
        story.extend([Paragraph(text, styles["Normal"]), Spacer(1, 8)])
    SimpleDocTemplate(str(destination), pagesize=A4).build(story)

    result = extraction_service.extract_document(
        destination.read_bytes(), filename=destination.name, content_type="application/pdf",
    )
    assert result.success, result.error_message
    candidate = result.canonical_candidate
    assert candidate is not None
    assert candidate.invoice_number == "ONEDMS-PDF-TEST-20261010"
    assert candidate.invoice_date == "2026-10-10"
    assert candidate.currency == "INR"
    assert len(candidate.line_items) == 2
    assert candidate.subtotal_amount == 1000
    assert candidate.tax_amount == 0
    assert candidate.total_amount == 1000
    canonical = candidate.model_dump(mode="json")
    canonical["subtotal"] = canonical.pop("subtotal_amount")
    canonical["supplier_dealer_code"] = "ONEDMS-DEMO-API"
    rules = [{
        "rule_code": "INVOICE_TOTAL_RECONCILIATION", "severity": "ERROR",
        "rule_config": {
            "type": "TOTAL_RECONCILIATION", "subtotal_field": "subtotal",
            "tax_field": "tax_amount", "total_field": "total_amount",
            "line_subtotal_field": "taxable_amount", "line_tax_field": "tax_amount",
            "line_total_field": "line_total", "tolerance": "0.01",
        },
    }]
    findings = validate_canonical_payload(canonical, rules, ValidationContext(
        is_registered_dealer=lambda _: True, is_duplicate_invoice=lambda *_: False,
    ))
    assert not findings, findings
    assert not result.warnings, result.warnings
    print(f"PDF created: {destination}")
    print(f"Extraction: PASS ({result.extraction_method}); 2 lines, INR 1000.00, tax 0.00")
    print(f"Total reconciliation: {get_overall_status(findings)}; {len(findings)} findings")
    print("No network calls or database writes were performed.")


if __name__ == "__main__":
    main()
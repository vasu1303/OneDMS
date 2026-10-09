"""Interactive CLI test demonstrating JSON, CSV, and Local PDF extraction."""

import io
import json
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from app.extraction.service import extraction_service
from app.extraction.models import DocumentFormat


def build_sample_pdf() -> bytes:
    """Creates a sample Daimler Truck invoice PDF in memory."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("<b>DAIMLER TRUCK NORTH AMERICA - INVOICE</b>", styles["Title"]),
        Spacer(1, 10),
        Paragraph("""
        <b>Invoice No:</b> DTNA-2026-00452<br/>
        <b>Invoice Date:</b> 2026-03-20<br/>
        <b>Buyer OEM:</b> Daimler Truck AG<br/>
        <b>Currency:</b> EUR
        """, styles["Normal"]),
        Spacer(1, 12),
        Table([
            ["Item Code", "Description", "Qty", "Unit Price", "Line Total", "VIN / Chassis"],
            ["DT-4401", "Heavy Duty Disc Brake Set", "4", "350.00", "1400.00", "WDB9634031L887711"],
            ["DT-9002", "Electronic Control Unit (ECU)", "1", "4200.00", "4200.00", "WDB9634031L887712"],
            ["DT-1120", "Air Suspension Bellows", "2", "600.00", "1200.00", ""],
        ], colWidths=[65, 175, 35, 65, 65, 135], style=[
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]),
        Spacer(1, 12),
        Paragraph("<b>Grand Total:</b> 6800.00 EUR", styles["Normal"]),
    ]
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def main():
    print("=" * 60)
    print(" OneDMS Format Parsing & Local Extraction Demo")
    print("=" * 60)

    # 1. Test JSON
    print("\n[1] Testing JSON Ingestion (Zero LLM)...")
    json_data = json.dumps({
        "dms_source": "Reynolds",
        "invoice_ref": "REY-8910",
        "dealer_code": "D-401",
        "items": [{"part": "OIL-5W30", "qty": 10, "rate": 15.0}]
    })
    res_json = extraction_service.extract_document(json_data, format_hint=DocumentFormat.JSON)
    print(f" -> Method: {res_json.extraction_method}")
    print(f" -> Success: {res_json.success}")
    print(f" -> Source Data Keys: {list(res_json.source_data.keys())}")
    print(f" -> Duration: {res_json.metadata.duration_ms} ms")

    # 2. Test CSV
    print("\n[2] Testing CSV Ingestion (Deterministic Sniffing)...")
    csv_data = "PartNumber,Description,Quantity,Price,Total\nBRK-100,Brake Pad Set,2,120.00,240.00\nFLT-200,Fuel Filter,1,45.00,45.00"
    res_csv = extraction_service.extract_document(csv_data, filename="dealer_export.csv")
    print(f" -> Method: {res_csv.extraction_method}")
    print(f" -> Detected Rows: {len(res_csv.source_data)}")
    print(f" -> First Row: {res_csv.source_data[0]}")
    print(f" -> Duration: {res_csv.metadata.duration_ms} ms")

    # 3. Test Local PDF with pdfplumber
    print("\n[3] Testing Local PDF Parsing (pdfplumber - No LLM)...")
    pdf_bytes = build_sample_pdf()
    res_pdf = extraction_service.extract_document(pdf_bytes, filename="daimler_invoice.pdf")
    print(f" -> Method: {res_pdf.extraction_method}")
    print(f" -> Success: {res_pdf.success}")
    
    candidate = res_pdf.canonical_candidate
    print(f" -> Invoice Number: {candidate.invoice_number}")
    print(f" -> Invoice Date:   {candidate.invoice_date}")
    print(f" -> Buyer OEM:      {candidate.buyer_oem_id}")
    print(f" -> Currency:       {candidate.currency}")
    print(f" -> Grand Total:    {candidate.total_amount}")
    print(f" -> Line Items Extracted: {len(candidate.line_items)}")
    for item in candidate.line_items:
        vin_str = f" [VIN: {item.chassis_number}]" if item.chassis_number else ""
        print(f"    - Line {item.line_number}: ({item.item_code}) {item.description} | Qty: {item.quantity} x {item.unit_price} = {item.line_total}{vin_str}")
    
    print(f" -> Warnings: {res_pdf.warnings or 'None'}")
    print(f" -> Duration: {res_pdf.metadata.duration_ms} ms")
    print("\n" + "=" * 60)
    print(" ALL LOCAL EXTRACTIONS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()

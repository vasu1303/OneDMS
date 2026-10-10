"""Comprehensive unit tests for Format Parsing and Local PDF/JSON/CSV Extraction."""

import io
from decimal import Decimal
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from openpyxl import Workbook
import xlwt

from app.extraction.models import DocumentFormat, ExtractionResult
from app.extraction.service import ExtractionService
from app.extraction.parsers.json_parser import JsonExtractor
from app.extraction.parsers.csv_parser import CsvExtractor
from app.extraction.parsers.excel_parser import ExcelExtractor
from app.extraction.parsers.pdf_parser import LocalPdfExtractor


def create_synthetic_invoice_pdf(
    invoice_num: str = "INV-2026-9042",
    date_str: str = "2026-03-15",
    buyer: str = "Daimler Truck North America",
    currency: str = "EUR",
    total_val: str = "12450.00",
) -> bytes:
    """Helper to generate an in-memory synthetic PDF invoice with realistic Daimler structure."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    # Title & Header
    story.append(Paragraph("<b>TAX INVOICE / RECHNUNG</b>", styles["Title"]))
    story.append(Spacer(1, 12))

    header_text = f"""
    <b>Invoice No:</b> {invoice_num}<br/>
    <b>Invoice Date:</b> {date_str}<br/>
    <b>Buyer OEM:</b> {buyer}<br/>
    <b>Currency:</b> {currency}
    """
    story.append(Paragraph(header_text, styles["Normal"]))
    story.append(Spacer(1, 14))

    # Line Item Table
    table_data = [
        ["Item Code", "Description", "Qty", "Unit Price", "Line Total", "VIN / Chassis"],
        ["DT-8820", "Brake Caliper Assembly Heavy Duty", "2", "1200.00", "2400.00", "WDB9634031L890123"],
        ["DT-9911", "Axle Differential Gearbox Unit", "1", "8050.00", "8050.00", "WDB9634031L890124"],
        ["DT-1002", "Synthetic Transmission Oil 20L", "4", "500.00", "2000.00", ""],
    ]

    t = Table(table_data, colWidths=[65, 175, 35, 65, 65, 135])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    # Summary Totals
    totals_text = f"""
    <b>Subtotal:</b> 12450.00 {currency}<br/>
    <b>Tax Amount:</b> 0.00 {currency}<br/>
    <b>Grand Total:</b> {total_val} {currency}
    """
    story.append(Paragraph(totals_text, styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


class TestJsonExtractor:
    """Tests for deterministic JSON parsing."""

    def test_valid_json_invoice(self):
        extractor = JsonExtractor()
        payload = '{"invoice_id": "DMS-99", "amount": 450.00, "lines": [{"sku": "A1", "qty": 2}]}'
        result = extractor.extract(payload)

        assert result.success is True
        assert result.format == DocumentFormat.JSON
        assert result.extraction_method == "deterministic_json"
        assert result.source_data == {"invoice_id": "DMS-99", "amount": 450.0, "lines": [{"sku": "A1", "qty": 2}]}
        assert result.canonical_candidate is None  # Person 3 handles mapping from source_data
        assert result.metadata.character_count > 0
        assert result.metadata.duration_ms >= 0

    def test_json_bytes_with_bom(self):
        extractor = JsonExtractor()
        payload = b'\xef\xbb\xbf{"dealer": "Stuttgart East", "order_ref": "ORD-12"}'
        result = extractor.extract(payload)

        assert result.success is True
        assert result.source_data["dealer"] == "Stuttgart East"

    def test_empty_json(self):
        extractor = JsonExtractor()
        result = extractor.extract("")
        assert result.success is False
        assert "empty" in result.error_message.lower()

    def test_malformed_json(self):
        extractor = JsonExtractor()
        result = extractor.extract('{"invalid": json content without closing')
        assert result.success is False
        assert "invalid json" in result.error_message.lower()


class TestCsvExtractor:
    """Tests for deterministic CSV parsing."""

    def test_comma_delimited_csv(self):
        extractor = CsvExtractor()
        csv_text = "PartNumber,Description,Quantity,Price,Total\nPN-1,Oil Filter,5,25.00,125.00\nPN-2,Air Filter,2,40.00,80.00"
        result = extractor.extract(csv_text)

        assert result.success is True
        assert result.format == DocumentFormat.CSV
        assert result.extraction_method == "deterministic_csv"
        assert len(result.source_data) == 2
        assert result.source_data[0]["PartNumber"] == "PN-1"
        assert result.source_data[0]["Quantity"] == "5"

    def test_semicolon_delimited_csv(self):
        extractor = CsvExtractor()
        csv_text = "ItemCode;Name;Qty;Amount\nIC-99;Brake Pad;4;200.00"
        result = extractor.extract(csv_text)

        assert result.success is True
        assert len(result.source_data) == 1
        assert result.source_data[0]["ItemCode"] == "IC-99"

    def test_empty_csv(self):
        extractor = CsvExtractor()
        result = extractor.extract("   ")
        assert result.success is False
        assert "empty" in result.error_message.lower()


def create_excel_invoice_xlsx() -> bytes:
    buffer = io.BytesIO()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["InvoiceNumber", "Description", "Qty", "UnitPrice"])
    sheet.append(["XLSX-001", "Brake rotor", 2, 125.5])
    workbook.save(buffer)
    return buffer.getvalue()


def create_excel_invoice_xls() -> bytes:
    buffer = io.BytesIO()
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Invoice")
    for column, value in enumerate(("InvoiceNumber", "Description", "Qty", "UnitPrice")):
        sheet.write(0, column, value)
    for column, value in enumerate(("XLS-001", "Brake rotor", 2, 125.5)):
        sheet.write(1, column, value)
    workbook.save(buffer)
    return buffer.getvalue()


class TestExcelExtractor:
    def test_extract_xlsx_first_sheet_rows(self):
        result = ExcelExtractor().extract(create_excel_invoice_xlsx())

        assert result.success is True
        assert result.format == DocumentFormat.EXCEL
        assert result.extraction_method == "deterministic_excel"
        assert result.source_data == [{
            "InvoiceNumber": "XLSX-001", "Description": "Brake rotor", "Qty": 2, "UnitPrice": 125.5,
        }]

    def test_extract_xls_rows(self):
        result = ExcelExtractor().extract(create_excel_invoice_xls())

        assert result.success is True
        assert result.source_data == [{
            "InvoiceNumber": "XLS-001", "Description": "Brake rotor", "Qty": 2.0, "UnitPrice": 125.5,
        }]

    def test_reject_malformed_excel(self):
        result = ExcelExtractor().extract(b"not a workbook")

        assert result.success is False
        assert "not a supported" in result.error_message.lower()


class TestLocalPdfExtractor:
    """Tests for local PDF parsing using pdfplumber."""

    def test_extract_synthetic_pdf(self):
        pdf_bytes = create_synthetic_invoice_pdf()
        extractor = LocalPdfExtractor()
        result = extractor.extract(pdf_bytes)

        assert result.success is True
        assert result.format == DocumentFormat.PDF
        assert result.extraction_method == "local_pdfplumber"
        assert result.canonical_candidate is not None

        candidate = result.canonical_candidate
        assert candidate.invoice_number == "INV-2026-9042"
        assert candidate.invoice_date == "2026-03-15"
        assert "Daimler" in candidate.buyer_oem_id
        assert candidate.currency == "EUR"
        assert candidate.total_amount == Decimal("12450.00")

        # Verify line items extracted from table
        assert len(candidate.line_items) == 3
        first_line = candidate.line_items[0]
        assert first_line.item_code == "DT-8820"
        assert "Brake Caliper" in first_line.description
        assert first_line.quantity == Decimal("2")
        assert first_line.unit_price == Decimal("1200.00")
        assert first_line.line_total == Decimal("2400.00")
        assert first_line.chassis_number == "WDB9634031L890123"

        assert result.metadata.page_count == 1
        assert result.metadata.table_count >= 1
        assert result.metadata.field_confidence.get("invoice_number", 0) > 0.8

    def test_corrupt_pdf_bytes(self):
        extractor = LocalPdfExtractor()
        corrupt_bytes = b"%PDF-1.4 invalid random content not conforming to pdf spec"
        result = extractor.extract(corrupt_bytes)

        assert result.success is False
        assert result.error_message is not None

    def test_empty_pdf(self):
        extractor = LocalPdfExtractor()
        result = extractor.extract(b"")

        assert result.success is False
        assert "empty" in result.error_message.lower()


class TestExtractionService:
    """Tests for ExtractionService routing, autodetection, and fault tolerance."""

    def test_detect_format_by_extension(self):
        service = ExtractionService()
        assert service.detect_format(b"data", filename="invoice.json") == DocumentFormat.JSON
        assert service.detect_format(b"data", filename="export.csv") == DocumentFormat.CSV
        assert service.detect_format(b"data", filename="workbook.xlsx") == DocumentFormat.EXCEL
        assert service.detect_format(b"data", filename="workbook.xls") == DocumentFormat.EXCEL
        assert service.detect_format(b"data", filename="scan.pdf") == DocumentFormat.PDF

    def test_detect_format_by_magic_bytes(self):
        service = ExtractionService()
        assert service.detect_format(b"%PDF-1.7 ...") == DocumentFormat.PDF
        assert service.detect_format(b'{"order": 1}') == DocumentFormat.JSON

    def test_service_extract_json(self):
        service = ExtractionService()
        payload = '{"test": 123}'
        result = service.extract_document(payload, format_hint=DocumentFormat.JSON)
        assert result.success is True
        assert result.source_data == {"test": 123}

    def test_service_unsupported_format(self):
        service = ExtractionService()
        result = service.extract_document(b"xyz", format_hint=DocumentFormat.UNKNOWN)
        assert result.success is False
        assert "unsupported" in result.error_message.lower()

    def test_service_extract_pdf(self):
        service = ExtractionService()
        pdf_bytes = create_synthetic_invoice_pdf(invoice_num="INV-9901")
        result = service.extract_document(pdf_bytes, filename="invoice.pdf")
        assert result.success is True
        assert result.canonical_candidate.invoice_number == "INV-9901"

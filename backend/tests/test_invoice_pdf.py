"""Offline rendering/API tests: no settings, environment files, or real database."""

import asyncio
from dataclasses import replace
from datetime import date
from decimal import Decimal
import importlib.util
from io import BytesIO
from pathlib import Path
import re
import sys
import threading
from types import ModuleType
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
import httpx
import pdfplumber

from app.models.invoice import Dealer, InboundDocument, InvoiceLineItem, StandardizedInvoice
from app.services.invoice_pdf import (
    generate_invoice_pdf, invoice_pdf_filename, snapshot_invoice,
)


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[1] / relative_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Load the real DB dependency without its package initializer, which imports
# unrelated object storage/settings. The endpoint uses this same callable.
db_dependency = load_module("invoice_pdf_test_db", "app/api/deps/db.py")
get_db_session = db_dependency.get_db_session


def isolated_invoice_endpoints():
    # Preserve production imports/functionality. Stub only unrelated legacy imports
    # that otherwise initialize logging/settings when importing this endpoint.
    handlers = ModuleType("app.exceptions.handlers")
    handlers.OneDMSException = Exception
    workflow = ModuleType("app.services.workflow")
    workflow.serialize_invoice_for_frontend = MagicMock()
    spec = importlib.util.spec_from_file_location(
        "invoice_pdf_test_endpoints",
        Path(__file__).resolve().parents[1] / "app/api/v1/endpoints/invoices.py",
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        "app.api.deps.db": db_dependency,
        "app.exceptions.handlers": handlers, "app.services.workflow": workflow,
        # Any accidental settings import must fail instead of reading .env.
        "app.core.config": None, "app.core.logging": None,
    }):
        spec.loader.exec_module(module)
    return module


def make_invoice():
    invoice = StandardizedInvoice(
        id=42, document_id=73, invoice_number="CANON-001", invoice_date=date(2026, 10, 10),
        buyer_oem_id="BUYER-9", currency="INR", subtotal=Decimal("999999999999.99"),
        tax_amount=Decimal("180.01"), total_amount=Decimal("1000000000179.99"),
        review_status="APPROVED", validation_status="VALID", oem_delivery_status="NOT_SENT",
        canonical_payload={
            "invoice_number": "STALE-NUMBER", "_onedms": {"notes": "INTERNAL-SECRET"},
            "source_content": "SOURCE-SECRET", "arbitrary": "ARBITRARY-SECRET",
        },
    )
    invoice.document = InboundDocument(
        id=73, dealer=Dealer(name="Business Dealer", dealer_code="DLR-9"),
        raw_payload={"invoice_number": "SOURCE-SECRET"},
        original_file_name="PRIVATE-FILE.pdf", storage_key="PRIVATE-STORAGE",
        error_message="PRIVATE-ERROR", checksum_sha256="PRIVATE-CHECKSUM",
    )
    invoice.line_items = [InvoiceLineItem(
        line_number=number, item_code=f"CODE-{number}", description=f"Ordered item {number}",
        quantity=Decimal("1.125"), unit_price=Decimal("12345678901.23"),
        discount_amount=Decimal("0.01"), taxable_amount=Decimal("10.10"),
        tax_rate=Decimal("18.00"), tax_amount=Decimal("1.82"), line_total=Decimal("11.92"),
        chassis_number="CHASSIS-2" if number == 2 else None,
    ) for number in (2, 1)]
    return invoice


def pdf_pages(content):
    with pdfplumber.open(BytesIO(content)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


class TestInvoicePDFGeneration(unittest.TestCase):
    def test_canonical_business_fields_exact_decimals_and_no_source_metadata(self):
        invoice = make_invoice()
        snapshot = snapshot_invoice(invoice)
        self.assertEqual([line.number for line in snapshot.lines], [1, 2])
        content = generate_invoice_pdf(snapshot)
        self.assertTrue(content.startswith(b"%PDF-"))
        text = "\n".join(pdf_pages(content))
        for expected in (
            "CANON-001", "2026-10-10", "Business Dealer", "DLR-9", "BUYER-9", "INR",
            "CODE-1", "CODE-2", "CHASSIS-2", "1.125", "12345678901.23", "0.01",
            "10.10", "18.00", "1.82", "11.92", "999999999999.99", "180.01",
            "1000000000179.99", "STANDARDIZED INVOICE COPY", "not an OEM-issued original",
            "Grand total", "Page 1",
        ):
            self.assertIn(expected, text)
        self.assertLess(text.index("Ordered item 1"), text.index("Ordered item 2"))
        for forbidden in (
            "STALE-NUMBER", "INTERNAL-SECRET", "SOURCE-SECRET", "ARBITRARY-SECRET",
            "PRIVATE-FILE", "PRIVATE-STORAGE", "PRIVATE-ERROR", "PRIVATE-CHECKSUM",
            "_onedms", "NOT_SENT", "validation_status",
        ):
            self.assertNotIn(forbidden, text)
        self.assertEqual(invoice.oem_delivery_status, "NOT_SENT")

    def test_all_dynamic_paragraph_fields_are_escaped(self):
        invoice = make_invoice()
        invoice.invoice_number = 'INV <b>literal</b> & "quoted"'
        invoice.document.dealer.name = "Dealer <i>literal</i> & Co"
        invoice.document.dealer.dealer_code = "D<9>&"
        invoice.buyer_oem_id = "Buyer <u>literal</u> & OEM"
        invoice.currency = "X&Y"
        invoice.line_items = [invoice.line_items[0]]
        line = invoice.line_items[0]
        line.description = 'Part <b>literal</b> & <img src="never-read.png"/>\nSecond line'
        line.item_code = "SKU <tag>&"
        line.chassis_number = "VIN <tag>&"
        text = "\n".join(pdf_pages(generate_invoice_pdf(snapshot_invoice(invoice))))
        for literal in (
            invoice.invoice_number, invoice.document.dealer.name,
            invoice.document.dealer.dealer_code, invoice.buyer_oem_id, "X&Y",
            'Part <b>literal</b> & <img src="never-read.png"/>', "Second line",
            "SKU <tag>&", "VIN <tag>&",
        ):
            self.assertIn(literal, text)

    def test_multiple_pages_repeat_headers_footer_and_keep_line_order(self):
        snapshot = snapshot_invoice(make_invoice())
        lines = tuple(replace(
            snapshot.lines[0], number=number, description=f"Row-{number:03d} business description",
            item_code=f"SKU-{number:03d}", chassis=None,
        ) for number in range(1, 101))
        pages = pdf_pages(generate_invoice_pdf(replace(snapshot, lines=tuple(reversed(lines)))))
        self.assertGreater(len(pages), 1)
        for number, text in enumerate(pages, 1):
            self.assertIn("STANDARDIZED INVOICE COPY", text)
            self.assertIn("not an OEM-issued original", text)
            self.assertIn(f"Page {number}", text)
            if "Row-" in text:
                self.assertIn("Description / Item code", text)
                self.assertIn("Quantity", text)
        self.assertEqual(re.findall(r"Row-(\d{3})", "\n".join(pages)), [f"{n:03d}" for n in range(1, 101)])
        self.assertIn("Grand total", pages[-1])

    def test_oversized_description_splits_across_pages(self):
        snapshot = snapshot_invoice(make_invoice())
        line = replace(snapshot.lines[0], description="Long business description. " * 500)
        pages = pdf_pages(generate_invoice_pdf(replace(snapshot, lines=(line,))))
        self.assertGreater(len(pages), 1)
        self.assertIn("Grand total", pages[-1])
        self.assertEqual("\n".join(pages).count("Long business description."), 500)

    def test_optional_fields_absent_and_empty_lines(self):
        invoice = make_invoice()
        invoice.document = None
        invoice.line_items = []
        text = "\n".join(pdf_pages(generate_invoice_pdf(snapshot_invoice(invoice))))
        self.assertIn("Dealer: -", text)
        self.assertIn("Dealer code: -", text)
        self.assertNotIn("Chassis:", text)
        self.assertIn("Grand total", text)

    def test_filename_ascii_bounded_safe_and_fallback(self):
        for number in ('../../evil\\path\r\nX: "bad"; é你好', "x" * 1000, "你好", "", "...", "__"):
            name = invoice_pdf_filename(number)
            self.assertTrue(name.isascii())
            self.assertLessEqual(len(name), 92)
            self.assertRegex(name, r"^invoice-[A-Za-z0-9_-]+\.pdf$")
        self.assertEqual(invoice_pdf_filename("你好"), "invoice-approved.pdf")
        self.assertEqual(invoice_pdf_filename("CANON-001"), "invoice-CANON-001.pdf")


class FakeSession:
    def __init__(self, invoice):
        result = MagicMock()
        result.scalar_one_or_none.return_value = invoice
        self.execute = AsyncMock(return_value=result)
        self.commit = AsyncMock()
        self.flush = AsyncMock()
        self.add = MagicMock()


class TestInvoicePDFAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.endpoints = isolated_invoice_endpoints()
        self.app = FastAPI()
        self.app.include_router(self.endpoints.router, prefix="/api/invoices")
        self.invoice = make_invoice()
        self.db = FakeSession(self.invoice)

        async def override_db():
            yield self.db

        self.app.dependency_overrides[get_db_session] = override_db
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.app.dependency_overrides.clear()

    def assert_no_writes(self):
        self.db.commit.assert_not_awaited()
        self.db.flush.assert_not_awaited()
        self.db.add.assert_not_called()

    async def test_missing_404_without_rendering(self):
        self.db = FakeSession(None)
        with patch.object(self.endpoints, "invoice_pdf_response", new_callable=AsyncMock) as render:
            response = await self.client.get("/api/invoices/42/pdf")
            render.assert_not_awaited()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Invoice not found."})
        self.assert_no_writes()

    async def test_all_unapproved_states_409_without_rendering(self):
        with patch.object(self.endpoints, "invoice_pdf_response", new_callable=AsyncMock) as render:
            for state in ("NOT_REQUIRED", "PENDING", "REJECTED", "approved", None):
                with self.subTest(state=state):
                    self.invoice.review_status = state
                    response = await self.client.get("/api/invoices/42/pdf")
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(response.json(), {"detail": "Only approved invoices can be exported as PDF."})
            render.assert_not_awaited()
        self.assert_no_writes()

    async def test_approved_attachment_eager_query_thread_and_no_delivery_mutation(self):
        event_loop_thread = threading.get_ident()
        renderer_threads = []

        def render(snapshot):
            renderer_threads.append(threading.get_ident())
            return generate_invoice_pdf(snapshot)

        with patch("app.services.invoice_pdf.generate_invoice_pdf", side_effect=render), patch(
            "app.services.invoice_pdf.asyncio.to_thread", wraps=asyncio.to_thread,
        ) as offload:
            response = await self.client.get("/api/invoices/42/pdf")
            offload.assert_awaited_once()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.headers["content-disposition"], 'attachment; filename="invoice-CANON-001.pdf"')
        self.assertIn("CANON-001", "\n".join(pdf_pages(response.content)))
        self.assertEqual(len(renderer_threads), 1)
        self.assertNotEqual(renderer_threads[0], event_loop_thread)
        self.db.execute.assert_awaited_once()
        stmt = self.db.execute.call_args.args[0]
        self.assertEqual(stmt.compile().params["id_1"], 42)
        paths = [str(option.path) for option in stmt._with_options]
        self.assertTrue(any("StandardizedInvoice.line_items" in path for path in paths))
        self.assertTrue(any("StandardizedInvoice.document" in path and "InboundDocument.dealer" in path for path in paths))
        self.assertEqual(self.invoice.review_status, "APPROVED")
        self.assertEqual(self.invoice.oem_delivery_status, "NOT_SENT")
        self.assert_no_writes()

    async def test_approved_unsafe_number_safe_attachment_and_sent_status_preserved(self):
        self.invoice.invoice_number = '../../bad\\name\r\nInjected: "yes"; é' + "x" * 150
        self.invoice.oem_delivery_status = "SENT"
        response = await self.client.get("/api/invoices/42/pdf")
        self.assertEqual(response.status_code, 200)
        filename = invoice_pdf_filename(self.invoice.invoice_number)
        self.assertEqual(response.headers["content-disposition"], f'attachment; filename="{filename}"')
        self.assertNotIn("injected", response.headers)
        self.assertEqual(self.invoice.oem_delivery_status, "SENT")
        self.assert_no_writes()


if __name__ == "__main__":
    unittest.main()
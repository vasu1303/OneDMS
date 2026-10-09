"""Local PDF Extractor utilizing pdfplumber and heuristic table/text parsing."""

from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

import pdfplumber

from app.extraction.base import BaseExtractor
from app.extraction.exceptions import EmptyDocumentError, MalformedDocumentError
from app.extraction.models import (
    CanonicalInvoiceCandidate,
    CanonicalLineItemCandidate,
    DocumentFormat,
)


class LocalPdfExtractor(BaseExtractor):
    """
    High-performance local PDF invoice parser.
    Extracts text layout and tabular structures using pdfplumber without any external LLM calls.
    Produces a typed CanonicalInvoiceCandidate along with field-level confidence and warnings.
    """

    @property
    def supported_format(self) -> DocumentFormat:
        return DocumentFormat.PDF

    @property
    def method_identifier(self) -> str:
        return "local_pdfplumber"

    def _extract_impl(self, content: bytes | str) -> tuple[Any | None, Any | None, list[str], dict[str, Any]]:
        warnings: list[str] = []

        if isinstance(content, str):
            pdf_bytes = content.encode("utf-8")
        else:
            pdf_bytes = content

        if not pdf_bytes:
            raise EmptyDocumentError("PDF content is empty (0 bytes)")

        try:
            pdf_stream = io.BytesIO(pdf_bytes)
            with pdfplumber.open(pdf_stream) as pdf:
                page_count = len(pdf.pages)
                if page_count == 0:
                    raise EmptyDocumentError("PDF document contains no pages")

                all_text: list[str] = []
                all_tables: list[list[list[str | None]]] = []

                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text.append(text)
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)

        except Exception as exc:
            if isinstance(exc, (EmptyDocumentError, MalformedDocumentError)):
                raise
            raise MalformedDocumentError(f"Failed to read PDF document structure: {exc}") from exc

        joined_text = "\n".join(all_text)
        if not joined_text.strip():
            warnings.append("PDF contains no selectable text; document may be a scanned image or empty")
            # If no text at all, raise or return minimal candidate
            raise MalformedDocumentError("Scanned or raster-only PDF: no selectable text found")

        # 1. Extract Header Fields via Regex heuristics
        invoice_number, inv_num_conf = self._extract_invoice_number(joined_text)
        if not invoice_number:
            warnings.append("Could not identify invoice number; defaulting to UNKNOWN")
            invoice_number = "UNKNOWN"

        invoice_date, inv_date_conf = self._extract_invoice_date(joined_text)
        if not invoice_date:
            warnings.append("Could not identify invoice date; defaulting to current date")
            invoice_date = datetime.now().strftime("%Y-%m-%d")

        buyer_oem_id = self._extract_buyer_oem(joined_text)
        currency, curr_conf = self._extract_currency(joined_text)
        subtotal, tax_amount, total_amount, totals_conf = self._extract_totals(joined_text)

        # 2. Extract Line Items from Tables or Text Fallback
        line_items, table_count = self._extract_line_items_from_tables(all_tables)
        if not line_items:
            # Fallback to text line scanner
            line_items = self._extract_line_items_from_text(joined_text)
            if not line_items:
                warnings.append("No line items could be parsed from PDF tables or text")

        # If total_amount was not found in header, compute from line items
        if total_amount is None:
            if line_items:
                computed_total = sum(item.line_total for item in line_items)
                total_amount = computed_total
                warnings.append(f"Header total missing; computed sum from line items ({total_amount})")
            else:
                total_amount = Decimal("0.0")
                warnings.append("Total amount missing and could not be calculated")

        # Arithmetic consistency check
        if line_items and total_amount > 0:
            sum_lines = sum(item.line_total for item in line_items)
            diff = abs(sum_lines - total_amount)
            if diff > Decimal("0.50"):
                warnings.append(
                    f"Discrepancy detected: sum of line items ({sum_lines}) differs from invoice total ({total_amount})"
                )

        candidate = CanonicalInvoiceCandidate(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            buyer_oem_id=buyer_oem_id,
            currency=currency,
            subtotal_amount=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            line_items=line_items,
        )

        metadata = {
            "page_count": page_count,
            "table_count": table_count,
            "character_count": len(joined_text),
            "field_confidence": {
                "invoice_number": inv_num_conf,
                "invoice_date": inv_date_conf,
                "currency": curr_conf,
                "total_amount": totals_conf,
                "line_items": 0.9 if line_items else 0.2,
            },
        }

        return None, candidate, warnings, metadata

    def _extract_invoice_number(self, text: str) -> tuple[str | None, float]:
        patterns = [
            r"(?i)(?:invoice\s*(?:no|number|#|num|id)|rechnungs-?nr|factura\s*n[°o]?)\s*[:.\-]?\s*([A-Za-z0-9\-/_]+)",
            r"(?i)(?:inv\s*(?:no|#))\s*[:.\-]?\s*([A-Za-z0-9\-/_]+)",
            r"(?i)\bINV-?[0-9]{4,}\b",
        ]
        for idx, pattern in enumerate(patterns):
            match = re.search(pattern, text)
            if match:
                value = match.group(1) if match.groups() else match.group(0)
                cleaned = value.strip()
                if len(cleaned) >= 3:
                    conf = 0.95 if idx == 0 else 0.80
                    return cleaned, conf
        return None, 0.0

    def _extract_invoice_date(self, text: str) -> tuple[str | None, float]:
        # Try finding date after "Date:", "Invoice Date:", etc.
        patterns = [
            r"(?i)(?:invoice\s*date|date|datum|rechnungsdatum)\s*[:.\-]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})",
            r"(?i)(?:invoice\s*date|date|datum|rechnungsdatum)\s*[:.\-]?\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{2,4})",
            r"\b([0-9]{4}-[0-9]{2}-[0-9]{2})\b",
            r"\b([0-9]{2}/[0-9]{2}/[0-9]{4})\b",
            r"\b([0-9]{2}\.[0-9]{2}\.[0-9]{4})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                raw_date = match.group(1).strip()
                iso_date = self._parse_to_iso_date(raw_date)
                if iso_date:
                    return iso_date, 0.90
        return None, 0.0

    def _parse_to_iso_date(self, s: str) -> str | None:
        formats = [
            "%Y-%m-%d", "%Y/%m/%d",
            "%d/%m/%Y", "%m/%d/%Y",
            "%d.%m.%Y", "%d-%m-%Y",
            "%Y%m%d"
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _extract_buyer_oem(self, text: str) -> str | None:
        oem_patterns = [
            r"(?i)\b(daimler\s*truck|daimler|dtna|mercedes-?benz|freightliner|western\s*star)\b",
            r"(?i)(?:customer|buyer|client)\s*(?:id|code|no)?\s*[:.\-]?\s*([A-Za-z0-9\-]+)",
        ]
        for pattern in oem_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_currency(self, text: str) -> tuple[str, float]:
        currencies = ["EUR", "USD", "GBP", "CAD", "INR", "CHF", "AUD"]
        for curr in currencies:
            if re.search(rf"\b{curr}\b", text, re.IGNORECASE):
                return curr, 0.95
        if "€" in text:
            return "EUR", 0.90
        if "$" in text:
            return "USD", 0.90
        if "£" in text:
            return "GBP", 0.90
        return "USD", 0.50

    def _extract_totals(self, text: str) -> tuple[Decimal | None, Decimal | None, Decimal | None, float]:
        subtotal: Decimal | None = None
        tax_amount: Decimal | None = None
        total: Decimal | None = None

        total_patterns = [
            r"(?i)(?:total\s*amount|grand\s*total|invoice\s*total|gesamtbetrag|total)\s*[:.\-]?\s*[$€£]?\s*([0-9]+(?:[,.][0-9]{2,3})*(?:\.[0-9]{2})?)",
        ]
        for pat in total_patterns:
            matches = list(re.finditer(pat, text))
            if matches:
                # Often the last total match is the grand total
                raw_val = matches[-1].group(1).replace(",", "")
                try:
                    total = Decimal(raw_val)
                    break
                except Exception:
                    pass

        subtotal_match = re.search(
            r"(?i)(?:subtotal|net\s*amount|nettobetrag|sub-?total)\s*[:.\-]?\s*[$€£]?\s*([0-9]+(?:[,.][0-9]{2,3})*(?:\.[0-9]{2})?)",
            text
        )
        if subtotal_match:
            try:
                subtotal = Decimal(subtotal_match.group(1).replace(",", ""))
            except Exception:
                pass

        tax_match = re.search(
            r"(?i)(?:tax|vat|mwst|gst|sales\s*tax)\s*(?:amount)?\s*[:.\-]?\s*[$€£]?\s*([0-9]+(?:[,.][0-9]{2,3})*(?:\.[0-9]{2})?)",
            text
        )
        if tax_match:
            try:
                tax_amount = Decimal(tax_match.group(1).replace(",", ""))
            except Exception:
                pass

        conf = 0.90 if total is not None else 0.30
        return subtotal, tax_amount, total, conf

    def _extract_line_items_from_tables(
        self, tables: list[list[list[str | None]]]
    ) -> tuple[list[CanonicalLineItemCandidate], int]:
        candidates: list[CanonicalLineItemCandidate] = []
        parsed_table_count = 0

        for table in tables:
            if not table or len(table) < 2:
                continue

            header_row = [str(col).strip().lower() if col else "" for col in table[0]]
            col_map = self._map_table_columns(header_row)

            # Require at least description or item code and a price/total column
            if not (col_map.get("desc") is not None or col_map.get("item_code") is not None):
                continue
            if col_map.get("total") is None and col_map.get("unit_price") is None:
                continue

            parsed_table_count += 1
            line_idx = 1

            for row in table[1:]:
                if not any(row):
                    continue

                desc_idx = col_map.get("desc")
                desc = " ".join(str(row[desc_idx]).split()) if desc_idx is not None and row[desc_idx] else ""
                
                # Filter out summary rows (Subtotal, Total, etc.)
                if re.search(r"(?i)\b(total|subtotal|tax|vat|shipping)\b", desc):
                    continue

                item_code_idx = col_map.get("item_code")
                item_code = "".join(str(row[item_code_idx]).split()) if item_code_idx is not None and row[item_code_idx] else None

                qty_idx = col_map.get("qty")
                qty = self._parse_number(row[qty_idx]) if qty_idx is not None and row[qty_idx] else Decimal("1.0")

                price_idx = col_map.get("unit_price")
                unit_price = self._parse_number(row[price_idx]) if price_idx is not None and row[price_idx] else Decimal("0.0")

                total_idx = col_map.get("total")
                line_total = self._parse_number(row[total_idx]) if total_idx is not None and row[total_idx] else (qty * unit_price)

                if not desc and item_code:
                    desc = f"Item {item_code}"
                elif not desc:
                    desc = f"Line Item {line_idx}"

                chassis_idx = col_map.get("chassis")
                chassis = "".join(str(row[chassis_idx]).split()) if chassis_idx is not None and row[chassis_idx] else None

                candidates.append(
                    CanonicalLineItemCandidate(
                        line_number=line_idx,
                        item_code=item_code,
                        description=desc,
                        quantity=qty,
                        unit_price=unit_price,
                        discount_amount=Decimal("0.0"),
                        taxable_amount=line_total,
                        tax_rate=None,
                        tax_amount=Decimal("0.0"),
                        line_total=line_total,
                        chassis_number=chassis,
                    )
                )
                line_idx += 1

        return candidates, parsed_table_count

    def _map_table_columns(self, header: list[str]) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for idx, col in enumerate(header):
            if any(term in col for term in ["item", "part", "sku", "code", "art.-nr", "artikel"]):
                mapping["item_code"] = idx
            elif any(term in col for term in ["desc", "bezeichnung", "details", "product"]):
                mapping["desc"] = idx
            elif any(term in col for term in ["qty", "quantity", "menge", "anzahl", "count"]):
                mapping["qty"] = idx
            elif any(term in col for term in ["unit price", "price", "rate", "preis", "einzelpreis"]):
                mapping["unit_price"] = idx
            elif any(term in col for term in ["total", "amount", "gesamt", "betrag", "line total"]):
                mapping["total"] = idx
            elif any(term in col for term in ["vin", "chassis", "fahrgestell"]):
                mapping["chassis"] = idx
        return mapping

    def _extract_line_items_from_text(self, text: str) -> list[CanonicalLineItemCandidate]:
        """Regex line scanner fallback when structured tables cannot be delimited."""
        candidates: list[CanonicalLineItemCandidate] = []
        # Pattern: [item_code] Description [qty] [unit_price] [line_total]
        pattern = r"(?m)^\s*([A-Za-z0-9\-]{2,15})?\s+([A-Za-z0-9\s\-_/]{4,35}?)\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]{2})?)\s+([0-9]+(?:\.[0-9]{2})?)\s*$"
        line_idx = 1
        for match in re.finditer(pattern, text):
            item_code, desc, qty_str, price_str, total_str = match.groups()
            try:
                candidates.append(
                    CanonicalLineItemCandidate(
                        line_number=line_idx,
                        item_code=item_code.strip() if item_code else None,
                        description=desc.strip(),
                        quantity=Decimal(qty_str),
                        unit_price=Decimal(price_str),
                        discount_amount=Decimal("0.0"),
                        taxable_amount=Decimal(total_str),
                        tax_amount=Decimal("0.0"),
                        line_total=Decimal(total_str),
                    )
                )
                line_idx += 1
            except Exception:
                continue
        return candidates

    def _parse_number(self, val: Any) -> Decimal:
        if val is None:
            return Decimal("0.0")
        s = str(val).replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
        try:
            return Decimal(s)
        except Exception:
            # Try finding numeric token
            match = re.search(r"[-+]?\d*\.\d+|\d+", s)
            if match:
                return Decimal(match.group(0))
            return Decimal("0.0")

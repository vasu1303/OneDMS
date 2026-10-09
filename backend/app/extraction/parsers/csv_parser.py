"""Deterministic CSV Extractor for tabular invoice exports."""

from __future__ import annotations

import csv
import io
from typing import Any

from app.extraction.base import BaseExtractor
from app.extraction.exceptions import EmptyDocumentError, MalformedDocumentError
from app.extraction.models import DocumentFormat


class CsvExtractor(BaseExtractor):
    """
    Deterministic extractor for tabular CSV / flat-file invoice exports.
    Automatically detects delimiters and encodes rows into source_data for mapping.
    """

    @property
    def supported_format(self) -> DocumentFormat:
        return DocumentFormat.CSV

    @property
    def method_identifier(self) -> str:
        return "deterministic_csv"

    def _extract_impl(self, content: bytes | str) -> tuple[Any | None, Any | None, list[str], dict[str, Any]]:
        warnings: list[str] = []

        if isinstance(content, bytes):
            # Strip UTF-8 BOM if present
            if content.startswith(b"\xef\xbb\xbf"):
                content = content[3:]
            text = content.decode("utf-8", errors="replace").strip()
        else:
            text = content.strip()

        if not text:
            raise EmptyDocumentError("CSV content is empty")

        # Sniff delimiter (supporting comma, semicolon, tab, pipe)
        sample = text[:4096]
        delimiter = ","
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except Exception:
            # Fallback to inspecting common delimiters
            for candidate in [";", "\t", "|", ","]:
                if candidate in sample.split("\n")[0]:
                    delimiter = candidate
                    break

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            raise MalformedDocumentError("CSV document has no header line or identifiable columns")

        # Clean column names (strip whitespace and null chars)
        cleaned_headers = [h.strip() for h in reader.fieldnames if h]
        if not cleaned_headers:
            raise MalformedDocumentError("CSV header row contains only blank column names")

        rows: list[dict[str, Any]] = []
        for row_idx, row in enumerate(reader, start=1):
            cleaned_row = {
                (k.strip() if k else f"col_{i}"): (v.strip() if v else "")
                for i, (k, v) in enumerate(row.items())
            }
            # Skip empty lines
            if any(cleaned_row.values()):
                rows.append(cleaned_row)

        if not rows:
            warnings.append("CSV document contains headers but zero data rows")

        metadata = {
            "character_count": len(text),
            "table_count": 1,
            "delimiter": delimiter,
            "row_count": len(rows),
            "column_count": len(cleaned_headers),
            "field_confidence": {"header_integrity": 1.0, "format_confidence": 0.95}
        }

        # Deterministic output for Person 3's mapping layer
        return rows, None, warnings, metadata

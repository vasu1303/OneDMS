"""Extraction Service orchestrating format detection, parser dispatch, and boundary handling."""

from __future__ import annotations

from typing import Any

from app.core.logging import log
from app.extraction.base import BaseExtractor
from app.extraction.exceptions import UnsupportedFormatError
from app.extraction.models import (
    DocumentFormat,
    ExtractionMetadata,
    ExtractionResult,
)
from app.extraction.parsers.csv_parser import CsvExtractor
from app.extraction.parsers.json_parser import JsonExtractor
from app.extraction.parsers.pdf_parser import LocalPdfExtractor


class ExtractionService:
    """
    Central service for document format parsing and extraction.
    Ensures deterministic, local processing with zero LLM dependence.
    """

    def __init__(self, extractors: list[BaseExtractor] | None = None):
        if extractors is not None:
            self._extractors = {e.supported_format: e for e in extractors}
        else:
            self._extractors = {
                DocumentFormat.JSON: JsonExtractor(),
                DocumentFormat.CSV: CsvExtractor(),
                DocumentFormat.PDF: LocalPdfExtractor(),
            }

    def detect_format(
        self,
        content: bytes | str,
        filename: str | None = None,
        content_type: str | None = None
    ) -> DocumentFormat:
        """
        Detects document format from MIME type, filename extension, or binary magic signatures.
        """
        # 1. Check Content-Type header
        if content_type:
            ct = content_type.lower()
            if "json" in ct:
                return DocumentFormat.JSON
            if "csv" in ct or "text/comma-separated-values" in ct:
                return DocumentFormat.CSV
            if "pdf" in ct:
                return DocumentFormat.PDF

        # 2. Check filename extension
        if filename:
            fn = filename.lower()
            if fn.endswith(".json"):
                return DocumentFormat.JSON
            if fn.endswith((".csv", ".tsv", ".txt")):
                return DocumentFormat.CSV
            if fn.endswith(".pdf"):
                return DocumentFormat.PDF

        # 3. Inspect binary magic numbers / content signature
        if isinstance(content, bytes):
            if content.startswith(b"%PDF-"):
                return DocumentFormat.PDF
            stripped_bytes = content.lstrip()
            if stripped_bytes.startswith((b"{", b"[")):
                return DocumentFormat.JSON
            if b"," in stripped_bytes[:200] or b";" in stripped_bytes[:200]:
                return DocumentFormat.CSV
        elif isinstance(content, str):
            stripped_str = content.strip()
            if stripped_str.startswith("%PDF-"):
                return DocumentFormat.PDF
            if stripped_str.startswith(("{", "[")):
                return DocumentFormat.JSON
            if "," in stripped_str[:200] or ";" in stripped_str[:200]:
                return DocumentFormat.CSV

        return DocumentFormat.UNKNOWN

    def extract_document(
        self,
        content: bytes | str,
        format_hint: DocumentFormat | str | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> ExtractionResult:
        """
        Main entry point for extracting invoice data.
        Dispatches to the appropriate format extractor without exposing raw document text to logs.
        """
        # Resolve target format
        resolved_format: DocumentFormat
        if format_hint:
            if isinstance(format_hint, str):
                try:
                    resolved_format = DocumentFormat(format_hint.lower())
                except ValueError:
                    resolved_format = DocumentFormat.UNKNOWN
            else:
                resolved_format = format_hint
        else:
            resolved_format = self.detect_format(content, filename=filename, content_type=content_type)

        if resolved_format not in self._extractors:
            log.warning(f"Unsupported format '{resolved_format}' for file '{filename or 'unknown'}'")
            return ExtractionResult(
                format=resolved_format,
                extraction_method="none",
                success=False,
                source_data=None,
                canonical_candidate=None,
                warnings=[f"Format '{resolved_format}' is not supported"],
                metadata=ExtractionMetadata(),
                error_message=f"Unsupported document format: {resolved_format.value}"
            )

        extractor = self._extractors[resolved_format]
        log.info(f"Extracting invoice using '{extractor.method_identifier}' for format '{resolved_format.value}'")

        try:
            result = extractor.extract(content)
            log.info(
                f"Extraction completed: format={resolved_format.value}, "
                f"success={result.success}, duration={result.metadata.duration_ms}ms"
            )
            return result
        except Exception as exc:
            # Defensive containment to never crash the calling API process
            log.error(f"Unexpected extraction failure: {type(exc).__name__}")
            return ExtractionResult(
                format=resolved_format,
                extraction_method=extractor.method_identifier,
                success=False,
                source_data=None,
                canonical_candidate=None,
                warnings=["Unexpected exception occurred during extraction"],
                metadata=ExtractionMetadata(),
                error_message=str(exc)
            )


# Default singleton for application dependency injection
extraction_service = ExtractionService()

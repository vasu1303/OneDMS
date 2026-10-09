"""Service layer alias for the extraction service."""

from app.extraction import ExtractionService, extraction_service
from app.extraction.models import (
    CanonicalInvoiceCandidate,
    CanonicalLineItemCandidate,
    DocumentFormat,
    ExtractionMetadata,
    ExtractionResult,
)

__all__ = [
    "ExtractionService",
    "extraction_service",
    "DocumentFormat",
    "ExtractionResult",
    "ExtractionMetadata",
    "CanonicalInvoiceCandidate",
    "CanonicalLineItemCandidate",
]

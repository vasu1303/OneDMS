"""Typed domain exceptions for the format parsing and extraction layer."""


class ExtractionError(Exception):
    """Base exception for all extraction failures."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedFormatError(ExtractionError):
    """Raised when an unrecognized or unsupported document format is provided."""
    pass


class MalformedDocumentError(ExtractionError):
    """Raised when document content is corrupted, unparseable, or structurally invalid."""
    pass


class EmptyDocumentError(ExtractionError):
    """Raised when document payload is empty (zero bytes or whitespace-only)."""
    pass


class ParsingTimeoutError(ExtractionError):
    """Raised when extraction process exceeds configured execution timeout."""
    pass

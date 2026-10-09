"""Abstract Base Class for invoice document extractors."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from app.extraction.models import DocumentFormat, ExtractionMetadata, ExtractionResult


class BaseExtractor(ABC):
    """Abstract base class defining the contract for format-specific extractors."""

    @property
    @abstractmethod
    def supported_format(self) -> DocumentFormat:
        """The document format handled by this extractor."""
        pass

    @property
    @abstractmethod
    def method_identifier(self) -> str:
        """Unique identifier of the extraction algorithm/engine."""
        pass

    @abstractmethod
    def _extract_impl(self, content: bytes | str) -> tuple[Any | None, Any | None, list[str], dict[str, Any]]:
        """
        Implementation method to parse document.
        Returns:
            (source_data, canonical_candidate, warnings, extra_metadata_dict)
        """
        pass

    def extract(self, content: bytes | str) -> ExtractionResult:
        """
        Public template method that executes extraction with performance timing,
        metadata enrichment, and consistent error containment.
        """
        start_time = time.perf_counter()
        warnings: list[str] = []

        try:
            source_data, canonical_candidate, custom_warnings, extra_meta = self._extract_impl(content)
            warnings.extend(custom_warnings)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            metadata = ExtractionMetadata(
                duration_ms=duration_ms,
                page_count=extra_meta.get("page_count"),
                table_count=extra_meta.get("table_count"),
                character_count=extra_meta.get("character_count"),
                field_confidence=extra_meta.get("field_confidence", {})
            )

            return ExtractionResult(
                format=self.supported_format,
                extraction_method=self.method_identifier,
                success=True,
                source_data=source_data,
                canonical_candidate=canonical_candidate,
                warnings=warnings,
                metadata=metadata,
                error_message=None
            )

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            metadata = ExtractionMetadata(duration_ms=duration_ms)
            return ExtractionResult(
                format=self.supported_format,
                extraction_method=self.method_identifier,
                success=False,
                source_data=None,
                canonical_candidate=None,
                warnings=warnings,
                metadata=metadata,
                error_message=str(exc)
            )

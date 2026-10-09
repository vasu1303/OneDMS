"""Deterministic JSON Extractor for structured invoice payloads."""

from __future__ import annotations

import json
from typing import Any

from app.extraction.base import BaseExtractor
from app.extraction.exceptions import EmptyDocumentError, MalformedDocumentError
from app.extraction.models import DocumentFormat


class JsonExtractor(BaseExtractor):
    """
    Deterministic extractor for native JSON invoice payloads.
    Provides source_data to Person 3's mapping layer with zero LLM overhead.
    """

    @property
    def supported_format(self) -> DocumentFormat:
        return DocumentFormat.JSON

    @property
    def method_identifier(self) -> str:
        return "deterministic_json"

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
            raise EmptyDocumentError("JSON content is empty")

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MalformedDocumentError(f"Invalid JSON document at line {exc.lineno}, column {exc.colno}") from exc

        if not isinstance(parsed, (dict, list)):
            raise MalformedDocumentError("JSON document must be an object or array")

        # Heuristic checks / warnings
        if isinstance(parsed, dict) and not parsed:
            warnings.append("JSON payload is an empty object")
        elif isinstance(parsed, list) and len(parsed) == 0:
            warnings.append("JSON payload is an empty list")

        metadata = {
            "character_count": len(text),
            "table_count": len(parsed) if isinstance(parsed, list) else 1,
            "field_confidence": {"source_integrity": 1.0}
        }

        # Deterministic parsers return source_data for Person 3's mapping engine
        return parsed, None, warnings, metadata

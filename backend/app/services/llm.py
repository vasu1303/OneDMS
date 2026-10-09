import json
import re
from typing import Any

import httpx
from loguru import logger

from app.core.config import Settings, settings


class LLMService:
    def __init__(self, app_settings: Settings | None = None):
        self.settings = app_settings or settings
        self.api_key = self.settings.openrouter_key
        self.model = self.settings.OPENROUTER_MODEL
        self.fallback_model = self.settings.OPENROUTER_FALLBACK_MODEL
        self.base_url = self.settings.OPENROUTER_BASE_URL.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": self.settings.APP_NAME,
        }

    async def _send_completion_request(
        self, client: httpx.AsyncClient, model: str, payload: dict[str, Any]
    ) -> str:
        req_payload = {**payload, "model": model}
        response = await client.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=req_payload,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            error_info = data["error"]
            msg = error_info.get("message", str(error_info)) if isinstance(error_info, dict) else str(error_info)
            raise ValueError(f"OpenRouter error: {msg}")
        choices = data.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            raise ValueError(f"OpenRouter returned empty choices: {data}")
        return choices[0]["message"]["content"]

    async def complete(
        self,
        user_prompt: str,
        system_prompt: str = "You are an intelligent data extraction assistant for automotive dealership systems.",
        model: str | None = None,
        temperature: float = 0.1,
    ) -> str:
        """Call OpenRouter chat completions with automatic fallback."""
        if not self.is_configured:
            raise ValueError("OpenRouter API key is not configured in settings")

        target_model = model or self.model
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                return await self._send_completion_request(client, target_model, payload)
            except Exception as e:
                if target_model != self.fallback_model:
                    logger.warning(
                        f"Model {target_model} failed: {e}. Falling back to {self.fallback_model}"
                    )
                    return await self._send_completion_request(client, self.fallback_model, payload)
                raise

    async def extract_json(
        self,
        raw_document_text: str,
        system_prompt: str = (
            "You are a specialized OEM integration engine for automotive dealers. "
            "Extract all relevant dealer invoice and purchase order data into a clean, "
            "canonical JSON structure. Return ONLY valid JSON."
        ),
        model: str | None = None,
    ) -> dict[str, Any]:
        """Extract structured data from unstructured or semi-structured dealer text."""
        raw_response = await self.complete(
            user_prompt=raw_document_text,
            system_prompt=system_prompt,
            model=model,
            temperature=0.0,
        )

        # Clean markdown formatting if present (```json ... ```)
        cleaned = raw_response.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as err:
            logger.error(f"Failed to parse LLM JSON response: {err}\nResponse was:\n{raw_response}")
            raise ValueError(f"LLM did not return valid JSON: {err}") from err

    async def check(self) -> dict[str, Any]:
        """Verify connectivity to OpenRouter with configured key."""
        if not self.is_configured:
            return {"status": "not_configured", "model": self.model}

        try:
            test_res = await self.extract_json(
                raw_document_text="Ping test for OneDMS. Return JSON with key 'status' set to 'ok'.",
                system_prompt="Return pure JSON.",
            )
            return {"status": "healthy", "model": self.model, "response": test_res}
        except Exception as e:
            logger.error(f"OpenRouter health check failed: {e}")
            return {"status": "failed", "model": self.model, "error": str(e)}


# Singleton helper
llm_service = LLMService()

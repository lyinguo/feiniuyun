"""Real LLM client for OpenAI-compatible chat-completions APIs."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from app.config import Settings, settings
from app.services.llm_output_parser import parse_json_object


class LLMError(RuntimeError):
    """Base error for model calls."""


class LLMConfigurationError(LLMError):
    """Raised when the model provider is not configured."""


class LLMResponseError(LLMError):
    """Raised when the provider returns an invalid response."""


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class OpenAICompatibleLLMClient:
    """Small, dependency-light wrapper around /chat/completions.

    This is intentionally not a mock. If no API key is configured, calls fail
    with LLMConfigurationError so the frontend can tell the user to configure a
    real model provider.
    """

    def __init__(self, app_settings: Settings | None = None):
        self.settings = app_settings or settings

    async def chat_text(
        self,
        messages: Iterable[ChatMessage],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        if not self.settings.llm_configured:
            raise LLMConfigurationError(
                "LLM_API_KEY is not configured. Set it in .env before converting novels."
            )

        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - environment guard
            raise LLMConfigurationError(
                "httpx is not installed. Install requirements.txt before running the backend."
            ) from exc

        payload = {
            "model": self.settings.llm_model,
            "messages": [message.to_dict() for message in messages],
            "temperature": (
                self.settings.llm_temperature if temperature is None else temperature
            ),
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"

        last_error: Exception | None = None
        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                timeout = httpx.Timeout(self.settings.llm_timeout_seconds)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
                if response.status_code >= 400:
                    raise LLMResponseError(
                        f"LLM provider returned HTTP {response.status_code}: "
                        f"{response.text[:500]}"
                    )
                return self._extract_content(response.json())
            except (httpx.TimeoutException, httpx.TransportError, LLMResponseError) as exc:
                last_error = exc
                if attempt >= self.settings.llm_max_retries:
                    break
                await asyncio.sleep(0.8 * (2**attempt))

        raise LLMResponseError(f"LLM call failed after retries: {last_error}")

    async def chat_json(
        self,
        messages: Iterable[ChatMessage],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        content = await self.chat_text(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            return parse_json_object(content)
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMResponseError(
                "The model did not return valid JSON. "
                f"First 500 chars: {content[:500]}"
            ) from exc

    @staticmethod
    def _extract_content(payload: Dict[str, Any]) -> str:
        choices: List[Dict[str, Any]] = payload.get("choices") or []
        if not choices:
            raise LLMResponseError("LLM response has no choices.")

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

        raise LLMResponseError("LLM response has no message.content.")


llm_client = OpenAICompatibleLLMClient()

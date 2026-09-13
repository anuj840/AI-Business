"""Ollama AI provider (spec section 16).

Local, no per-request cost, good for development before revenue exists.
All knobs (model, temperature, timeout, retries) come from configuration,
never hard-coded.
"""
from __future__ import annotations

import asyncio

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.ai.provider import AIProviderInterface, AIResponse

logger = get_logger(__name__)


class OllamaUnavailableError(Exception):
    """Raised for transient errors that are worth retrying."""


class OllamaProvider(AIProviderInterface):
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.default_temperature = settings.OLLAMA_TEMPERATURE
        self.default_max_tokens = settings.OLLAMA_MAX_TOKENS
        self.timeout_seconds = settings.OLLAMA_TIMEOUT_SECONDS
        self.max_retries = settings.OLLAMA_MAX_RETRIES

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AIResponse:
        try:
            raw = await self._call_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature if temperature is not None else self.default_temperature,
                max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
            )
            text = raw.get("message", {}).get("content", "")
            return AIResponse(text=text, model=self.model, provider="ollama", raw=raw)
        except Exception as exc:  # noqa: BLE001 - never crash the caller/job
            logger.error("ollama.generate_failed", error=str(exc), model=self.model)
            return AIResponse(
                text="", model=self.model, provider="ollama", succeeded=False, error=str(exc)
            )

    async def _call_with_retry(
        self, *, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int
    ) -> dict:
        @retry(
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(OllamaUnavailableError),
            reraise=True,
        )
        async def _do_call() -> dict:
            # httpx's `timeout=` is a per-operation (e.g. per-read) timeout, not
            # a ceiling on total request duration. Ollama's non-streaming
            # response only lands after the full generation finishes, and a
            # small model can occasionally ramble well past num_predict
            # tokens before hitting a stop condition, appearing to trickle
            # bytes just often enough to never trip a per-read timeout. Wrap
            # the whole call in asyncio.wait_for for a real hard deadline.
            async def _post() -> dict:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    try:
                        resp = await client.post(
                            f"{self.base_url}/api/chat",
                            json={
                                "model": self.model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt},
                                ],
                                "stream": False,
                                "options": {
                                    "temperature": temperature,
                                    "num_predict": max_tokens,
                                },
                            },
                        )
                    except httpx.TransportError as exc:
                        raise OllamaUnavailableError(str(exc)) from exc

                    if resp.status_code >= 500:
                        raise OllamaUnavailableError(f"Ollama returned {resp.status_code}")
                    resp.raise_for_status()
                    return resp.json()

            try:
                return await asyncio.wait_for(_post(), timeout=self.timeout_seconds)
            except asyncio.TimeoutError as exc:
                raise OllamaUnavailableError(
                    f"Ollama did not respond within {self.timeout_seconds}s"
                ) from exc

        return await _do_call()

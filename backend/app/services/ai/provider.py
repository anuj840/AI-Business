"""AI provider abstraction (spec section 15).

Application code depends only on this interface, never on a concrete
provider. Adding OpenAI later means writing OpenAIProvider and flipping
AI_PROVIDER — no changes to business logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIResponse:
    text: str
    model: str
    provider: str
    raw: dict | None = None
    succeeded: bool = True
    error: str | None = None


class AIProviderInterface(ABC):
    @abstractmethod
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AIResponse:
        """Generate a completion. Must never raise for ordinary provider
        failures — return AIResponse(succeeded=False, error=...) instead so
        callers (jobs) never crash."""
        raise NotImplementedError

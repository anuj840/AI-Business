"""Provider factory — the only place that knows which concrete provider to build."""
from __future__ import annotations

from app.core.config import get_settings
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.provider import AIProviderInterface


def get_ai_provider() -> AIProviderInterface:
    settings = get_settings()
    if settings.AI_PROVIDER == "ollama":
        return OllamaProvider()
    # Future: elif settings.AI_PROVIDER == "openai": return OpenAIProvider()
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.AI_PROVIDER!r}")

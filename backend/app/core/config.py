"""Application configuration.

All behavior that could vary between environments (DB, AI provider, crawler
limits, scoring weights file, etc.) is driven from environment variables so
nothing is hard-coded across the codebase.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "AI Business Growth Platform"
    ENV: str = "development"
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://ai_business:ai_business@localhost:5432/ai_business"
    )

    # --- AI Provider ---
    AI_PROVIDER: str = "ollama"  # "ollama" | "openai" (future)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    OLLAMA_TEMPERATURE: float = 0.2
    OLLAMA_MAX_TOKENS: int = 2048
    OLLAMA_TIMEOUT_SECONDS: int = 90
    OLLAMA_MAX_RETRIES: int = 2

    # --- Crawler ---
    CRAWLER_MAX_PAGES: int = 8
    CRAWLER_TIMEOUT_MS: int = 20000
    CRAWLER_USER_AGENT: str = "AIBusinessGrowthPlatform-Bot/0.1 (+audit-research)"

    # --- Scoring ---
    SCORING_CONFIG_PATH: str = "app/services/scoring/weights.json"

    # --- Security ---
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    # --- Logging ---
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()

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
    OLLAMA_MAX_TOKENS: int = 700
    """Deliberately tight: audit/outreach outputs are meant to be short
    (a few short bullets, a ~150-word email), and a large ceiling mostly
    just gives a small/rambling model more room to run long before hitting
    a natural stop -- observed live taking 3-5x longer than necessary with
    the previous 2048 default for outputs that were a few hundred words."""
    OLLAMA_TIMEOUT_SECONDS: int = 60
    OLLAMA_MAX_RETRIES: int = 2

    # --- Redis / background jobs ---
    REDIS_URL: str = "redis://localhost:6379/0"
    JOB_MAX_RETRIES: int = 1
    JOB_TIMEOUT_SECONDS: int = 600
    """Hard ceiling per analyze job -- generous because it includes a
    real Playwright crawl plus two Ollama calls; see AI.md for why the
    Ollama call itself is already independently bounded."""

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

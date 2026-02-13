"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    OPENAI_API_KEY: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6378/0"

    # ChromaDB
    CHROMA_PERSIST_PATH: str = "./data/chroma"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "info"

    # Rate Limiting
    RATE_LIMIT_MAX_SESSIONS: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 3600

    # Agent Config
    MAX_DEBATE_ROUNDS: int = 3
    ARCHITECT_MODEL: str = "gpt-4o"
    DEVILS_ADVOCATE_MODEL: str = "gpt-4o"
    COST_ANALYZER_MODEL: str = "gpt-4o-mini"
    DOCUMENTATION_MODEL: str = "gpt-4o"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

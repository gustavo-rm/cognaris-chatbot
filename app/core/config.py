"""Application configuration.

All settings are loaded from environment variables via Pydantic Settings.
dev note: never read os.environ directly elsewhere, go through Settings().
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_name: str = "onboarding-chatbot"
    app_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://onboarding:onboarding@localhost:5432/onboarding"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout: int = 30

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 20

    # Session
    session_ttl_seconds: int = 86_400
    session_abandon_after_days: int = 7

    # LLM
    llm_provider: str = "anthropic"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-5"
    llm_timeout_seconds: int = 15

    # Optimization backend
    optimization_backend_url: str = "http://localhost:9000"
    optimization_backend_timeout_seconds: int = 30

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor.

    Using lru_cache makes Settings effectively a singleton without global state.
    Tests can clear the cache via get_settings.cache_clear() to inject overrides.
    """
    return Settings()
"""
Application settings loaded from environment variables.
Uses pydantic-settings for type-safe configuration management.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Global application settings sourced from .env file."""

    # --- LLM ---
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    LLM_MODEL: str = Field(default="gpt-4o", description="LLM model name")

    # --- Redis ---
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for session memory",
    )

    # --- Database ---
    APP_DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:root@localhost:5432/ai_agent_db",
        description="Application database connection URL"
    )

    # --- Security ---
    SECRET_KEY: str = Field(
        default="change-me-to-a-strong-random-secret",
        description="Secret key for JWT signing",
    )
    APP_ENCRYPTION_KEY: str = Field(
        default="",
        description="Fernet key for credential encryption",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRY_MINUTES: int = Field(default=60)

    # --- Server ---
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="info")
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated allowed CORS origins",
    )

    # --- Production Guardrails ---
    MAX_PARALLEL_QUERIES: int = Field(default=5, description="Max concurrent DB executions globally")
    MAX_CONNECTIONS_PER_REPORT: int = Field(default=15, description="Max DB connections per single report")
    DEFAULT_DB_TIMEOUT: float = Field(default=5.0, description="Timeout per database connection in seconds")
    GLOBAL_QUERY_TIMEOUT: float = Field(default=30.0, description="Absolute timeout for all connections in a report")
    SLOW_QUERY_THRESHOLD_MS: int = Field(default=2000, description="Threshold to log a query as slow")
    MAX_RESPONSE_SIZE_MB: int = Field(default=5, description="Maximum allowed response size in Megabytes")


    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        import os
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True



settings = Settings()

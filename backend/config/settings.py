"""
Application settings loaded from environment variables.
Uses pydantic-settings for type-safe configuration management.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Global application settings sourced from .env file."""

    # --- HRMS Database (Direct Connection) ---
    HRMS_DB_HOST: str = Field(default="localhost")
    HRMS_DB_PORT: int = Field(default=5432)
    HRMS_DB_NAME: str = Field(default="horilla_main")
    HRMS_DB_USER: str = Field(default="postgres")
    HRMS_DB_PASS: str = Field(default="root")

    # --- LangChain / LLM ---
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
    PORT: int = Field(default=8001)
    LOG_LEVEL: str = Field(default="info")
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://localhost:5174",
        description="Comma-separated allowed CORS origins",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        import os
        env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True



settings = Settings()

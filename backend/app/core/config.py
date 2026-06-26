"""Application configuration — all settings loaded from environment variables via pydantic-settings."""

import base64
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # "../.env" resolves relative to CWD when running from backend/ (e.g. `alembic upgrade head`)
        # In Docker, env vars are injected directly so this path is a no-op fallback
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432

    # CORS — origins allowed to make credentialed cross-origin requests.
    # Set as a JSON array in .env: ALLOWED_ORIGINS=["https://yourdomain.com"]
    # Defaults cover local Docker (port 80) and local Next.js dev server (port 3000).
    ALLOWED_ORIGINS: list[str] = ["http://localhost", "http://localhost:3000"]

    # LLM provider selection — "gemini" or "cloudflare"
    LLM_PROVIDER: str = "gemini"

    # Gemini — single API key covers both LLM and embedding endpoints
    GEMINI_API_KEY: str
    GEMINI_LLM_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # Cloudflare Workers AI (alternative LLM provider)
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_MODEL: str = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    CLOUDFLARE_SQL_MODEL: str = "@cf/qwen/qwen2.5-coder-32b-instruct"
    CLOUDFLARE_ROUTER_MODEL: str = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

    # Fernet encryption (for data_sources connection_config)
    FERNET_SECRET_KEY: str

    # Tavily
    TAVILY_API_KEY: str

    # Email (Resend)
    RESEND_API_KEY: str
    EMAIL_FROM: str = "onboarding@resend.dev"
    REQUIRE_EMAIL_VERIFICATION: bool = True

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @field_validator("FERNET_SECRET_KEY")
    @classmethod
    def validate_fernet_key(cls, v: str) -> str:
        """Validate that FERNET_SECRET_KEY is a proper 32-byte URL-safe base64 key."""
        try:
            key_bytes = base64.urlsafe_b64decode(v)
        except Exception as exc:
            raise ValueError(
                "FERNET_SECRET_KEY is not valid URL-safe base64. "
                "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from exc
        if len(key_bytes) != 32:
            raise ValueError(
                f"FERNET_SECRET_KEY must decode to exactly 32 bytes, got {len(key_bytes)}. "
                "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate that JWT_SECRET_KEY is at least 32 characters."""
        if len(v) < 32:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least 32 characters, got {len(v)}. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    # App
    ENVIRONMENT: str = "local"
    LOG_LEVEL: str = "info"
    FRONTEND_URL: str = "http://localhost"

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy URL (asyncpg driver) — used by the FastAPI app."""
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+asyncpg://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def database_url_sync(self) -> str:
        """Sync SQLAlchemy URL (psycopg2 driver) — used by Alembic migrations."""
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg2://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


settings = Settings()

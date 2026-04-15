from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    project_name: str = "Novex API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    api_v1_prefix: str = "/api/v1"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    database_url: str = "postgresql://novex:novex@postgres:5432/novex"
    redis_url: str = "redis://redis:6379/0"

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "novex"
    postgres_user: str = "novex"
    postgres_password: str = "novex"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio12345"
    minio_bucket: str = "novex-dev"
    minio_secure: bool = False

    backend_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:80",
            "http://localhost:3000",
        ]
    )

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value

        if isinstance(value, str):
            cleaned = value.strip()

            if not cleaned:
                return []

            if cleaned.startswith("[") and cleaned.endswith("]"):
                import json

                return json.loads(cleaned)

            return [item.strip() for item in cleaned.split(",") if item.strip()]

        raise ValueError("Invalid BACKEND_CORS_ORIGINS value")

    @property
    def sync_database_url(self) -> str:
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
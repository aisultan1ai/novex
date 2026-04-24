from __future__ import annotations

import warnings
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_POSTGRES_PASSWORDS = {"novex", "postgres", "password", "1234", "admin"}
_WEAK_MINIO_SECRETS = {"minio12345", "minio", "minioadmin", "password"}


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

    @model_validator(mode="after")
    def warn_weak_credentials_in_production(self) -> "Settings":
        if self.environment == "production":
            if self.postgres_password in _WEAK_POSTGRES_PASSWORDS:
                raise ValueError(
                    "postgres_password is a known weak default — set a strong POSTGRES_PASSWORD env var"
                )
            if self.minio_secret_key in _WEAK_MINIO_SECRETS:
                raise ValueError(
                    "minio_secret_key is a known weak default — set a strong MINIO_SECRET_KEY env var"
                )
        elif self.environment != "test":
            if self.postgres_password in _WEAK_POSTGRES_PASSWORDS:
                warnings.warn(
                    "postgres_password uses a weak default. Set POSTGRES_PASSWORD before deploying.",
                    stacklevel=2,
                )
            if self.minio_secret_key in _WEAK_MINIO_SECRETS:
                warnings.warn(
                    "minio_secret_key uses a weak default. Set MINIO_SECRET_KEY before deploying.",
                    stacklevel=2,
                )
        return self

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
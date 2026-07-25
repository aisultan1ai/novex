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
    debug: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

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
    minio_public_endpoint: str = ""  # public hostname for presigned URLs; defaults to minio_endpoint
    minio_public_secure: bool = True  # whether presigned URLs use https (independent of internal minio_secure)
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio12345"
    minio_bucket: str = "novex-dev"
    minio_secure: bool = False

    @model_validator(mode="after")
    def warn_weak_credentials_in_production(self) -> Settings:
        if self.environment == "production":
            if self.postgres_password in _WEAK_POSTGRES_PASSWORDS:
                raise ValueError(
                    "postgres_password is a known weak default — "
                    "set a strong POSTGRES_PASSWORD env var"
                )
            if self.minio_secret_key in _WEAK_MINIO_SECRETS:
                raise ValueError(
                    "minio_secret_key is a known weak default — "
                    "set a strong MINIO_SECRET_KEY env var"
                )
        elif self.environment != "test":
            if self.postgres_password in _WEAK_POSTGRES_PASSWORDS:
                warnings.warn(
                    "postgres_password uses a weak default. "
                    "Set POSTGRES_PASSWORD before deploying.",
                    stacklevel=2,
                )
            if self.minio_secret_key in _WEAK_MINIO_SECRETS:
                warnings.warn(
                    "minio_secret_key uses a weak default. "
                    "Set MINIO_SECRET_KEY before deploying.",
                    stacklevel=2,
                )
        return self

    # SMTP (email)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    # Display name shown in the recipient's inbox next to the address.
    # Cyrillic and other non-ASCII are OK — formataddr() encodes automatically.
    smtp_from_name: str = "Novex"
    smtp_tls: bool = True
    # Partner-application inbox. Comma-separated list is accepted so ops can
    # route the alert to multiple mailboxes without touching code.
    partners_email: str = "support@novex.kz"

    # Kaspi Pay (disabled until merchant onboarding is complete)
    kaspi_merchant_id: str = ""
    kaspi_api_key: str = ""
    kaspi_api_url: str = "https://api.kaspi.kz/merchant"
    kaspi_webhook_secret: str = ""
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    secret_key: str = ""
    access_token_expire_minutes: int = 60

    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1

    # CSE (Courier Service Express) carrier
    cse_login: str = ""
    cse_password: str = ""
    cse_api_url: str = "http://web.cse.ru/1c/ws/Web1C.1cws"

    # Internal carrier gateway service
    carrier_gateway_url: str = "http://carrier-gateway:8100"
    gateway_secret: str = ""

    # Carrier polling scheduler
    polling_max_workers: int = 10
    polling_cooldown_seconds: int = 100
    polling_batch_size: int = 200
    polling_creds_ttl_seconds: int = 300
    # Redis-lock TTL for the sync_tracking cron. Must comfortably exceed the
    # longest expected polling run so a second replica cannot start on top of
    # a still-running poll. Rule of thumb:
    #   TTL >= ceil(polling_batch_size / polling_max_workers) * per_carrier_timeout + safety
    # Default 300s covers a 200-item batch × 15s HTTP timeout ÷ 10 workers (≈300s).
    polling_lock_ttl_seconds: int = 300
    # How often the tracking-poller container wakes up between ticks. Kept
    # short so SIGTERM shutdown is snappy (K8s terminationGracePeriodSeconds
    # is typically 30s). Previously this was hard-coded at 30s.
    tracking_poller_tick_interval_seconds: int = 5

    # Dispatch retry backoff (seconds between attempts). Comma-separated in
    # the env, e.g. DISPATCH_RETRY_DELAYS_SECONDS="60,300,900". Length also
    # determines the cap for max_attempts — a 4-attempt job with 3 delays
    # uses the last delay for attempt #3 and beyond.
    dispatch_retry_delays_seconds: list[int] = Field(default_factory=lambda: [60, 300, 900])

    # CSE reference-data cache TTL (TypesOfCargo, Geography GUIDs). Kept as
    # a setting so ops can shorten it if CSE ever refuses to serve a request
    # against a stale GUID after they rename or add a type.
    cse_reference_cache_ttl_seconds: int = 3600

    backend_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:80",
            "http://localhost:3000",
        ]
    )

    @field_validator("dispatch_retry_delays_seconds", mode="before")
    @classmethod
    def parse_retry_delays(cls, value: Any) -> list[int]:
        # Accept both a native list (test / programmatic override) and the
        # env-provided comma-separated string form.
        if isinstance(value, list):
            return [int(v) for v in value]
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return [60, 300, 900]
            if cleaned.startswith("[") and cleaned.endswith("]"):
                import json
                return [int(v) for v in json.loads(cleaned)]
            return [int(x.strip()) for x in cleaned.split(",") if x.strip()]
        raise ValueError("Invalid DISPATCH_RETRY_DELAYS_SECONDS value")

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

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()

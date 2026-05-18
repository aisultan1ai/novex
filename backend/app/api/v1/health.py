from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.project_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }

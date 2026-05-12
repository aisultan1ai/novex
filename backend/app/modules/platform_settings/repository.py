from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.platform_settings.models import PlatformSetting


class PlatformSettingsRepository:
    def get(self, db: Session, key: str, default: str = "") -> str:
        row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
        return row.value if row else default

    def set(self, db: Session, key: str, value: str) -> PlatformSetting:
        row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
        if row:
            row.value = value
        else:
            row = PlatformSetting(key=key, value=value)
            db.add(row)
        db.flush()
        return row

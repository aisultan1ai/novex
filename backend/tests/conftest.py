from __future__ import annotations

import os

# Must run before any app module is imported.
# ENVIRONMENT=test suppresses weak-credential warnings in config.py.
# REDIS_URL=memory:// lets slowapi Limiter use in-process storage (no Redis daemon needed).
# SECRET_KEY must be non-empty; security.py raises RuntimeError if it is missing.
os.environ["ENVIRONMENT"] = "test"
os.environ["REDIS_URL"] = "memory://"
os.environ.setdefault("SECRET_KEY", "a" * 64)
os.environ.setdefault("DATABASE_URL", "postgresql://novex:novex@localhost/novex")

# Bust the lru_cache so Settings() re-reads the env vars we just set above.
from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

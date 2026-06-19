from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


# Sync engine — used by all endpoints except the async quotes path.
# pool_size=5, max_overflow=5 → 10 connections per process.
# 4 API workers × 10 + 1 worker process × 10 = 50 total. Under Postgres default 100.
engine: Engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)

# Async engine — used only by POST /api/shipping/quote (Exline HTTP call path).
# Smaller pool: async releases connections between awaits so fewer are needed.
async_engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=3,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise


def check_database_connection() -> dict[str, Any]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}

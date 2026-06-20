from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Integration tests require a real PostgreSQL instance.
# Set TEST_DATABASE_URL before running:
#   export TEST_DATABASE_URL=postgresql://novex:novex@localhost/novex_test
#   pytest tests/integration/
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

skip_no_db = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not set — skipping integration tests",
)


@pytest.fixture(scope="session")
def db_engine():
    """Create engine and apply schema via SQLAlchemy metadata (no alembic needed)."""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    engine = create_engine(TEST_DATABASE_URL, future=True)

    # Import every ORM model so metadata is fully populated before create_all.
    import app.modules.address_book.models  # noqa: F401
    import app.modules.audit.models  # noqa: F401
    import app.modules.carriers.models  # noqa: F401
    import app.modules.carriers.api_credentials  # noqa: F401
    import app.modules.carriers.integration_log  # noqa: F401
    import app.modules.carriers.webhook_config  # noqa: F401
    import app.modules.commissions.models  # noqa: F401
    import app.modules.dispatch.models  # noqa: F401
    import app.modules.documents.models  # noqa: F401
    import app.modules.identity.models  # noqa: F401
    import app.modules.notifications.models  # noqa: F401
    import app.modules.orders.models  # noqa: F401
    import app.modules.payments.models  # noqa: F401
    import app.modules.platform_settings.models  # noqa: F401
    import app.modules.quotes.models  # noqa: F401
    import app.modules.reviews.models  # noqa: F401
    import app.modules.shipments.models  # noqa: F401
    import app.modules.tracking.models  # noqa: F401
    from app.core.db import Base

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine) -> Session:
    """Provide a transactional session that rolls back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    SessionFactory = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = SessionFactory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

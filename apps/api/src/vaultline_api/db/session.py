"""SQLAlchemy engine and request-scoped session lifecycle."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from vaultline_api.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create a process-wide engine using the configured PostgreSQL URL."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Create a process-wide factory for non-autocommit sessions."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield a session, roll back any unfinished transaction, then always close it."""
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        if session.in_transaction():
            session.rollback()
        session.close()

"""Database connectivity check used by readiness."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from vaultline_api.db.session import get_engine


def check_database_connection() -> bool:
    """Return false for database connection/query failures without leaking details."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True

"""SQLAlchemy declarative base for future application models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata base; feature models will be added in later tasks."""

"""Database setup.

We use SQLAlchemy's declarative style with a small amount of dependency
injection: the engine and session factory live on ``app.state`` so tests can
spin up an isolated in-memory / temp SQLite database per test run.
"""

from __future__ import annotations

from typing import Iterator

from fastapi import Request
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import (
    DEFAULT_DESCRIPTION,
    DEFAULT_SIGNATURE,
    DEFAULT_THEME_COLOR,
    DEFAULT_TITLE,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def build_engine(database_url: str) -> Engine:
    """Create an engine, adding SQLite-specific options when needed."""
    connect_args = {}
    if database_url.startswith("sqlite"):
        # FastAPI may handle requests on a different thread than the one that
        # created the connection, so SQLite must allow cross-thread usage.
        connect_args["check_same_thread"] = False
    return create_engine(database_url, connect_args=connect_args, future=True)


def build_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency that yields a database session per request."""
    session_factory: sessionmaker = request.app.state.session_factory
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def ensure_recipient_design_columns(engine: Engine) -> None:
    """Add design columns to an existing ``recipients`` table if missing.

    This is a tiny, dependency-free migration so a database created before the
    certificate redesign keeps working. ``Base.metadata.create_all`` already
    creates the columns for fresh databases; this only patches old ones.
    """
    if not engine.url.get_backend_name().startswith("sqlite"):
        # Only SQLite is auto-migrated; other backends should use Alembic.
        return

    inspector = inspect(engine)
    if "recipients" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("recipients")}
    additions = {
        "title": f"VARCHAR(255) NOT NULL DEFAULT '{DEFAULT_TITLE}'",
        "description": f"TEXT NOT NULL DEFAULT '{DEFAULT_DESCRIPTION}'",
        "theme_color": f"VARCHAR(7) NOT NULL DEFAULT '{DEFAULT_THEME_COLOR}'",
        "signature_name": f"VARCHAR(255) NOT NULL DEFAULT '{DEFAULT_SIGNATURE}'",
    }

    with engine.begin() as connection:
        for name, ddl in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE recipients ADD COLUMN {name} {ddl}"))

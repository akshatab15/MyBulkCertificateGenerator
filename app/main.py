"""FastAPI application factory.

``create_app`` accepts optional overrides for the database and output
directory. This is what lets the test-suite build fully isolated app
instances that never touch real data.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from . import __version__
from .config import Settings
from .database import (
    Base,
    build_engine,
    build_session_factory,
    ensure_recipient_design_columns,
)
from .routers import certificates, health, jobs


def create_app(
    *,
    database_url: str | None = None,
    output_dir: Path | str | None = None,
    verify_base_url: str | None = None,
) -> FastAPI:
    """Build and configure a FastAPI application instance."""
    settings = Settings.from_env()
    if database_url is not None:
        settings.database_url = database_url
    if output_dir is not None:
        settings.output_dir = Path(output_dir).resolve()
    if verify_base_url is not None:
        settings.verify_base_url = verify_base_url.rstrip("/")

    # Make sure the output directory exists before any request is served.
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    engine = build_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    # Patch older SQLite databases created before the redesign (adds the new
    # design columns if they are missing).
    ensure_recipient_design_columns(engine)
    session_factory = build_session_factory(engine)

    app = FastAPI(
        title="Bulk Certificate Generator API",
        version=__version__,
        description="Generate, track and verify bulk PDF certificates.",
    )
    app.state.settings = settings
    app.state.session_factory = session_factory

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(certificates.router)

    return app


# Default app instance used by `uvicorn app.main:app`.
app = create_app()

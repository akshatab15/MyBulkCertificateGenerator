"""Application configuration.

Settings are read from environment variables so that the app, and especially
the tests, can point at temporary directories/databases without touching real
data. Everything has a sane default so a fresh clone runs with zero setup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Optional convenience: load variables from a local ``.env`` file when the
# ``python-dotenv`` package is available. Real environment variables always
# win (``override=False``), so tests and deployments can still override values.
try:  # pragma: no cover - exercised implicitly when python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is optional
    pass

# Project root = parent of the "app" package.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Certificate design defaults -------------------------------------------------
# Palette derived from the reference certificate image (navy + gold on off-white).
DEFAULT_TITLE = "Certificate of Appreciation"
DEFAULT_DESCRIPTION = (
    "In recognition of your outstanding participation, dedication and "
    "successful completion of the programme."
)
DEFAULT_THEME_COLOR = "#051a2a"  # deep navy
DEFAULT_GOLD = "#c5a04a"  # elegant gold accent
DEFAULT_GOLD_LIGHT = "#e8d7ab"  # light gold highlight
DEFAULT_SIGNATURE = "Programme Director"


def default_output_dir() -> Path:
    """Directory where generated PDFs and ZIP files are written."""
    return Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output")).resolve()


def default_database_url() -> str:
    """SQLAlchemy database URL. Defaults to a local SQLite file."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    db_path = Path(os.getenv("DB_PATH", BASE_DIR / "certificates.db")).resolve()
    # SQLite URLs use forward slashes, even on Windows.
    return f"sqlite:///{db_path.as_posix()}"


def default_verify_base_url() -> str:
    """Base URL embedded in certificate QR codes / verification links.

    Configured through ``CERTIFICATE_VERIFY_BASE_URL`` so that certificates
    scanned on a phone point at a reachable host instead of ``localhost``.
    ``PUBLIC_BASE_URL`` is still honoured as a deprecated fallback, and a
    safe local-development default is used when nothing is set.
    """
    value = (
        os.getenv("CERTIFICATE_VERIFY_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or "http://localhost:8000"
    )
    return value.rstrip("/")


@dataclass
class Settings:
    """Runtime settings for a single app instance.

    Kept as an explicit object (rather than global constants) so the app
    factory can build isolated instances for tests.
    """

    output_dir: Path
    database_url: str
    verify_base_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            output_dir=default_output_dir(),
            database_url=default_database_url(),
            verify_base_url=default_verify_base_url(),
        )

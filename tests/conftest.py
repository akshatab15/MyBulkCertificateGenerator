"""Shared pytest fixtures.

Every test gets its own temporary SQLite database and output directory, so
tests never touch real user data and can run in any order.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "output"
    directory.mkdir()
    return directory


@pytest.fixture
def app(tmp_path: Path, output_dir: Path):
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    return create_app(
        database_url=database_url,
        output_dir=output_dir,
        verify_base_url="http://testserver",
    )


@pytest.fixture
def client(app) -> TestClient:
    # Using the client as a context manager runs startup/shutdown events.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def recipients() -> list[dict]:
    """A small, valid recipient list reused across tests."""
    return [
        {
            "name": "Alice Smith",
            "email": "alice@example.com",
            "course": "Introduction to Python",
            "issue_date": "2026-01-15",
        },
        {
            "name": "Bob Jones",
            "email": "bob@example.com",
            "course": "Data Structures",
            "issue_date": "2026-02-20",
        },
        {
            "name": "Carol Diaz",
            "email": "carol@example.com",
            "course": "Web Development",
            "issue_date": "2026-03-05",
        },
    ]

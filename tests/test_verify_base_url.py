"""Tests for the configurable certificate verification base URL.

The QR code on every certificate encodes
``<CERTIFICATE_VERIFY_BASE_URL>/certificates/<id>/verify``. These tests make
sure the URL comes from the environment (not a hardcoded ``localhost``) and
that the configured value is what actually gets embedded in the QR code.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import pdf_generator
from app.config import default_verify_base_url
from app.main import create_app


def test_verify_base_url_defaults_to_localhost_when_unset(monkeypatch):
    monkeypatch.delenv("CERTIFICATE_VERIFY_BASE_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    assert default_verify_base_url() == "http://localhost:8000"


def test_verify_base_url_reads_new_environment_variable(monkeypatch):
    monkeypatch.setenv("CERTIFICATE_VERIFY_BASE_URL", "https://certs.example.com")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    assert default_verify_base_url() == "https://certs.example.com"


def test_verify_base_url_strips_trailing_slash_and_prefers_new_var(monkeypatch):
    monkeypatch.setenv("CERTIFICATE_VERIFY_BASE_URL", "https://new.example.com/")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://legacy.example.com")
    assert default_verify_base_url() == "https://new.example.com"


def test_verify_base_url_falls_back_to_legacy_public_base_url(monkeypatch):
    monkeypatch.delenv("CERTIFICATE_VERIFY_BASE_URL", raising=False)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://legacy.example.com/")
    assert default_verify_base_url() == "https://legacy.example.com"


def test_configured_verify_base_url_is_embedded_in_qr(monkeypatch, tmp_path: Path):
    """End-to-end: the env var must be what the QR image encodes."""
    monkeypatch.setenv("CERTIFICATE_VERIFY_BASE_URL", "https://certs.example.com")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    application = create_app(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        output_dir=output_dir,
    )

    encoded: list[str] = []
    original = pdf_generator._make_qr_image

    def spy(data: str):
        encoded.append(data)
        return original(data)

    monkeypatch.setattr(pdf_generator, "_make_qr_image", spy)

    recipients = [
        {
            "name": "Alice Smith",
            "email": "alice@example.com",
            "course": "Python 101",
            "issue_date": "2026-01-15",
        },
        {
            "name": "Bob Jones",
            "email": "bob@example.com",
            "course": "Data Structures",
            "issue_date": "2026-02-20",
        },
    ]

    with TestClient(application) as client:
        response = client.post("/jobs", json={"recipients": recipients})
        assert response.status_code == 202

    assert len(encoded) == len(recipients), "one QR code should be generated per certificate"
    for url in encoded:
        assert url.startswith("https://certs.example.com/certificates/")
        assert url.endswith("/verify")
        assert "localhost" not in url

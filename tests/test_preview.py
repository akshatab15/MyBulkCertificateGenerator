"""Tests for the PDF preview endpoint (useful for backend API testing)."""

from __future__ import annotations


def test_preview_returns_pdf(client):
    response = client.post(
        "/certificates/preview",
        json={
            "name": "Preview Person",
            "course": "Demo Programme",
            "issue_date": "2026-01-01",
            "title": "Certificate of Appreciation",
            "description": "A short description.",
            "theme_color": "#051a2a",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_preview_accepts_minimal_payload(client):
    # All fields have defaults except none - an empty object should still work.
    response = client.post("/certificates/preview", json={})
    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"


def test_preview_rejects_invalid_theme(client):
    response = client.post("/certificates/preview", json={"theme_color": "notacolor"})
    assert response.status_code == 422

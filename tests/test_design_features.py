"""Tests for the redesigned certificate: design fields, CSV columns, migration."""

from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, inspect, text

from app.database import ensure_recipient_design_columns
from app.pdf_generator import generate_certificate


def _render(tmp_path, **kwargs):
    output = tmp_path / "cert.pdf"
    generate_certificate(
        output,
        name="Alice Smith",
        course="Introduction to Python",
        issue_date=date(2026, 1, 15),
        certificate_id="CERT-TEST0001",
        **kwargs,
    )
    return output


def test_custom_design_fields_render(tmp_path):
    output = _render(
        tmp_path,
        title="Certificate of Excellence",
        description="Awarded for outstanding work.",
        theme_color="#5b1f2a",
        signature_name="Dean of Studies",
        emblem=True,
    )
    assert output.read_bytes()[:4] == b"%PDF"


def test_emblem_can_be_disabled(tmp_path):
    output = _render(tmp_path, emblem=False)
    assert output.read_bytes()[:4] == b"%PDF"


def test_invalid_theme_color_falls_back(tmp_path):
    # A direct (non-API) caller with a bad colour must still produce a PDF.
    output = _render(tmp_path, theme_color="not-a-colour")
    assert output.read_bytes()[:4] == b"%PDF"


def test_create_job_applies_design_fields(client):
    payload = {
        "recipients": [
            {
                "name": "Alice Smith",
                "email": "alice@example.com",
                "course": "Python 101",
                "issue_date": "2026-01-15",
                "title": "Certificate of Excellence",
                "description": "Great work",
                "theme_color": "#5b1f2a",
                "signature_name": "Dean of Studies",
            }
        ]
    }
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    cert = client.get(f"/jobs/{job_id}/certificates").json()[0]

    assert cert["status"] == "success"
    assert cert["title"] == "Certificate of Excellence"
    assert cert["theme_color"] == "#5b1f2a"
    assert cert["signature_name"] == "Dean of Studies"
    # The generated PDF is downloadable via the exposed URL.
    download = client.get(cert["download_url"])
    assert download.status_code == 200
    assert download.content[:4] == b"%PDF"


def test_invalid_theme_color_rejected_by_api(client):
    payload = {
        "recipients": [
            {
                "name": "A",
                "email": "a@example.com",
                "course": "C",
                "issue_date": "2026-01-01",
                "theme_color": "red",
            }
        ]
    }
    assert client.post("/jobs", json=payload).status_code == 422


def test_csv_with_optional_design_columns(client):
    csv = (
        "name,email,course,issue_date,title,description,theme_color\n"
        "Alice,alice@example.com,Python,2026-01-15,Certificate of Excellence,"
        "Great,#5b1f2a\n"
    )
    files = {"file": ("r.csv", csv, "text/csv")}
    job_id = client.post("/jobs/upload-csv", files=files).json()["job_id"]
    cert = client.get(f"/jobs/{job_id}/certificates").json()[0]
    assert cert["title"] == "Certificate of Excellence"
    assert cert["theme_color"] == "#5b1f2a"


def test_csv_shared_design_defaults_via_form(client):
    csv = "name,email,course,issue_date\nAlice,alice@example.com,Python,2026-01-15\n"
    files = {"file": ("r.csv", csv, "text/csv")}
    data = {"theme_color": "#123d2b", "title": "Certificate of Merit"}
    job_id = client.post("/jobs/upload-csv", files=files, data=data).json()["job_id"]
    cert = client.get(f"/jobs/{job_id}/certificates").json()[0]
    assert cert["theme_color"] == "#123d2b"
    assert cert["title"] == "Certificate of Merit"


def test_migration_adds_design_columns(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE recipients ("
                "id INTEGER PRIMARY KEY, job_id VARCHAR, name VARCHAR, email VARCHAR, "
                "course VARCHAR, issue_date DATE, certificate_id VARCHAR, status VARCHAR, "
                "error TEXT, file_path VARCHAR)"
            )
        )

    ensure_recipient_design_columns(engine)

    columns = {c["name"] for c in inspect(engine).get_columns("recipients")}
    assert {"title", "description", "theme_color", "signature_name"} <= columns

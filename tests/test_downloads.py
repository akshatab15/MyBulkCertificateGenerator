"""Individual certificate download tests."""

from __future__ import annotations


def _create_job(client, recipients) -> str:
    return client.post("/jobs", json={"recipients": recipients}).json()["job_id"]


def test_download_single_certificate(client, recipients):
    job_id = _create_job(client, recipients)
    certs = client.get(f"/jobs/{job_id}/certificates").json()
    cert_id = certs[0]["certificate_id"]

    response = client.get(f"/certificates/{cert_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_download_unknown_certificate_returns_404(client):
    assert client.get("/certificates/CERT-NOPE0000/download").status_code == 404


def test_missing_file_on_disk_returns_404(client, recipients, app):
    """A record that points at a non-existent file must 404, not crash."""
    job_id = _create_job(client, recipients)
    certs = client.get(f"/jobs/{job_id}/certificates").json()
    cert_id = certs[0]["certificate_id"]

    # Delete the generated PDF but keep the DB record.
    settings = app.state.settings
    for pdf in settings.output_dir.rglob("*.pdf"):
        pdf.unlink()

    assert client.get(f"/certificates/{cert_id}/download").status_code == 404

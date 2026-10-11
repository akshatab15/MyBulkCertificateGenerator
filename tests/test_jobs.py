"""Tests for job creation, status and certificate listing."""

from __future__ import annotations


def test_create_job_returns_accepted(client, recipients):
    response = client.post("/jobs", json={"recipients": recipients})
    assert response.status_code == 202
    body = response.json()
    assert body["job_id"]
    assert body["status"] in {"pending", "running", "completed"}


def test_job_completes_and_tracks_progress(client, recipients):
    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]

    # TestClient runs BackgroundTasks before the request returns, so the job
    # should already be finished.
    status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == "completed"
    assert status["total"] == len(recipients)
    assert status["processed"] == len(recipients)
    assert status["success"] == len(recipients)
    assert status["failed"] == 0
    assert status["completed_at"] is not None


def test_list_certificates_for_job(client, recipients):
    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]

    response = client.get(f"/jobs/{job_id}/certificates")
    assert response.status_code == 200
    certs = response.json()
    assert len(certs) == len(recipients)
    for cert in certs:
        assert cert["status"] == "success"
        assert cert["certificate_id"].startswith("CERT-")
        # A download link is exposed, but no filesystem path is.
        assert cert["download_url"].endswith("/download")
        assert "file_path" not in cert

    ids = {c["certificate_id"] for c in certs}
    assert len(ids) == len(recipients)  # all unique


def test_unknown_job_returns_404(client):
    assert client.get("/jobs/DOES-NOT-EXIST").status_code == 404
    assert client.get("/jobs/DOES-NOT-EXIST/certificates").status_code == 404
    assert client.get("/jobs/DOES-NOT-EXIST/download").status_code == 404

"""Certificate verification tests."""

from __future__ import annotations


def test_verify_valid_certificate(client, recipients):
    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]
    certs = client.get(f"/jobs/{job_id}/certificates").json()
    cert_id = certs[0]["certificate_id"]

    response = client.get(f"/certificates/{cert_id}/verify")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["certificate_id"] == cert_id
    assert body["name"] == certs[0]["name"]
    assert body["course"] == certs[0]["course"]
    assert body["job_id"] == job_id


def test_verify_unknown_certificate(client):
    response = client.get("/certificates/CERT-UNKNOWN0/verify")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["message"]


def test_verify_failed_certificate_is_invalid(client, recipients, monkeypatch):
    import app.processor as processor

    monkeypatch.setattr(
        processor, "generate_certificate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nope"))
    )

    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]
    certs = client.get(f"/jobs/{job_id}/certificates").json()
    cert_id = certs[0]["certificate_id"]

    body = client.get(f"/certificates/{cert_id}/verify").json()
    assert body["valid"] is False

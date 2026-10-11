"""Job progress / status transition tests."""

from __future__ import annotations


def test_each_recipient_gets_unique_certificate_id(client, recipients):
    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]
    certs = client.get(f"/jobs/{job_id}/certificates").json()
    ids = [c["certificate_id"] for c in certs]
    assert len(ids) == len(set(ids))


def test_progress_counters_match_recipient_states(client, recipients):
    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]

    status = client.get(f"/jobs/{job_id}").json()
    certs = client.get(f"/jobs/{job_id}/certificates").json()

    successes = sum(1 for c in certs if c["status"] == "success")
    failures = sum(1 for c in certs if c["status"] == "failed")

    assert status["processed"] == status["success"] + status["failed"]
    assert status["success"] == successes
    assert status["failed"] == failures
    assert status["processed"] == status["total"]


def test_download_url_only_present_for_success(client, recipients):
    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]
    certs = client.get(f"/jobs/{job_id}/certificates").json()
    for cert in certs:
        if cert["status"] == "success":
            assert cert["download_url"]
        else:
            assert cert["download_url"] is None

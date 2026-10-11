"""Failure isolation tests.

A failure generating one certificate must not stop the rest of the batch.
"""

from __future__ import annotations

import app.processor as processor


def test_single_failure_does_not_stop_batch(client, recipients, monkeypatch):
    original = processor.generate_certificate

    def flaky(output_path, *, name, course, issue_date, certificate_id, verify_url=None, **kwargs):
        if name == "Bob Jones":
            raise RuntimeError("simulated failure")
        return original(
            output_path,
            name=name,
            course=course,
            issue_date=issue_date,
            certificate_id=certificate_id,
            verify_url=verify_url,
            **kwargs,
        )

    monkeypatch.setattr(processor, "generate_certificate", flaky)

    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]
    status = client.get(f"/jobs/{job_id}").json()

    assert status["status"] == "partial"
    assert status["total"] == 3
    assert status["processed"] == 3
    assert status["success"] == 2
    assert status["failed"] == 1

    certs = client.get(f"/jobs/{job_id}/certificates").json()
    failed = [c for c in certs if c["status"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["name"] == "Bob Jones"
    assert failed[0]["error"] == "simulated failure"
    assert failed[0]["download_url"] is None


def test_all_failures_marks_job_failed(client, recipients, monkeypatch):
    def always_fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(processor, "generate_certificate", always_fail)

    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]
    status = client.get(f"/jobs/{job_id}").json()

    assert status["status"] == "failed"
    assert status["success"] == 0
    assert status["failed"] == 3
    # Nothing to download.
    assert client.get(f"/jobs/{job_id}/download").status_code == 404

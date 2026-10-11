"""ZIP download tests."""

from __future__ import annotations

import io
import zipfile


def test_download_job_as_zip(client, recipients):
    job_id = client.post("/jobs", json={"recipients": recipients}).json()["job_id"]

    response = client.get(f"/jobs/{job_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert len(names) == len(recipients)
        assert all(name.endswith(".pdf") for name in names)

        # Every entry must be a readable PDF.
        for name in names:
            data = archive.read(name)
            assert data[:4] == b"%PDF"


def test_zip_excludes_failed_certificates(client, recipients, monkeypatch):
    import app.processor as processor

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
    response = client.get(f"/jobs/{job_id}/download")
    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        # 3 recipients, 1 intentionally failed -> 2 PDFs.
        assert len(archive.namelist()) == 2

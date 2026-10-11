"""CSV upload tests."""

from __future__ import annotations

VALID_CSV = (
    "name,email,course,issue_date\n"
    "Alice Smith,alice@example.com,Introduction to Python,2026-01-15\n"
    "Bob Jones,bob@example.com,Data Structures,2026-02-20\n"
)


def test_upload_csv_creates_job(client):
    files = {"file": ("recipients.csv", VALID_CSV, "text/csv")}
    response = client.post("/jobs/upload-csv", files=files)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == "completed"
    assert status["total"] == 2
    assert status["success"] == 2

    certs = client.get(f"/jobs/{job_id}/certificates").json()
    assert len(certs) == 2


def test_upload_csv_missing_column_returns_400(client):
    csv = "name,email,course\nAlice,alice@example.com,Python\n"
    files = {"file": ("bad.csv", csv, "text/csv")}
    response = client.post("/jobs/upload-csv", files=files)
    assert response.status_code == 400
    assert "Missing required column" in response.json()["detail"]["message"]


def test_upload_csv_invalid_row_returns_400_with_details(client):
    csv = (
        "name,email,course,issue_date\n"
        "Alice,not-an-email,Python,2026-01-15\n"
    )
    files = {"file": ("badrow.csv", csv, "text/csv")}
    response = client.post("/jobs/upload-csv", files=files)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["errors"]
    assert detail["errors"][0]["row"] == 2


def test_upload_empty_file_returns_400(client):
    files = {"file": ("empty.csv", "", "text/csv")}
    response = client.post("/jobs/upload-csv", files=files)
    assert response.status_code == 400

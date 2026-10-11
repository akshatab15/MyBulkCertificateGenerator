"""Input validation tests."""

from __future__ import annotations

import pytest


def test_empty_recipient_list_rejected(client):
    response = client.post("/jobs", json={"recipients": []})
    assert response.status_code == 422


def test_missing_recipients_field_rejected(client):
    response = client.post("/jobs", json={})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "bad_recipient",
    [
        {"name": "", "email": "a@b.com", "course": "X", "issue_date": "2026-01-01"},
        {"name": "A", "email": "not-an-email", "course": "X", "issue_date": "2026-01-01"},
        {"name": "A", "email": "a@b.com", "course": "", "issue_date": "2026-01-01"},
        {"name": "A", "email": "a@b.com", "course": "X", "issue_date": "01-01-2026"},
        {"name": "A", "email": "a@b.com", "course": "X"},
    ],
)
def test_invalid_recipients_return_422(client, bad_recipient):
    response = client.post("/jobs", json={"recipients": [bad_recipient]})
    assert response.status_code == 422


def test_validation_errors_are_descriptive(client):
    response = client.post(
        "/jobs",
        json={
            "recipients": [
                {"name": "", "email": "bad", "course": "", "issue_date": "nope"}
            ]
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    # Pydantic returns a list of field-level errors.
    assert isinstance(detail, list)
    fields = {err["loc"][-1] for err in detail}
    assert {"name", "email", "course", "issue_date"} & fields

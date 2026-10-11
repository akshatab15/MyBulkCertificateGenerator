"""Database access helpers.

Keeping queries here keeps routers thin and avoids duplicating logic between
the JSON endpoint and the CSV upload endpoint.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .cert_ids import generate_certificate_id, generate_job_id
from .config import (
    DEFAULT_DESCRIPTION,
    DEFAULT_SIGNATURE,
    DEFAULT_THEME_COLOR,
    DEFAULT_TITLE,
)
from .models import Job, Recipient


def _unique_certificate_id(db: Session) -> str:
    """Generate a certificate id that is not already used."""
    for _ in range(10):
        candidate = generate_certificate_id()
        exists = db.scalar(
            select(Recipient.id).where(Recipient.certificate_id == candidate)
        )
        if exists is None:
            return candidate
    # Astronomically unlikely; fail loudly rather than silently collide.
    raise RuntimeError("Could not generate a unique certificate id")


def create_job(db: Session, recipients_data: list[dict], source_filename: str | None = None) -> Job:
    """Create a job and all of its recipient rows in one transaction."""
    job = Job(
        id=generate_job_id(),
        status="pending",
        source_filename=source_filename,
        total=len(recipients_data),
    )
    db.add(job)
    # Flush so the job row exists before adding recipients that reference it.
    db.flush()

    for data in recipients_data:
        recipient = Recipient(
            job_id=job.id,
            name=data["name"],
            email=data["email"],
            course=data["course"],
            issue_date=data["issue_date"],
            title=data.get("title") or DEFAULT_TITLE,
            description=data.get("description") or DEFAULT_DESCRIPTION,
            theme_color=data.get("theme_color") or DEFAULT_THEME_COLOR,
            signature_name=data.get("signature_name") or DEFAULT_SIGNATURE,
            certificate_id=_unique_certificate_id(db),
            status="pending",
        )
        db.add(recipient)

    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> Job | None:
    return db.get(Job, job_id)


def list_recipients(db: Session, job_id: str) -> list[Recipient]:
    return list(
        db.scalars(
            select(Recipient).where(Recipient.job_id == job_id).order_by(Recipient.id)
        )
    )


def get_recipient_by_certificate(db: Session, certificate_id: str) -> Recipient | None:
    return db.scalar(
        select(Recipient).where(Recipient.certificate_id == certificate_id)
    )

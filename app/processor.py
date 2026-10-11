"""Background job processor.

This runs *after* the HTTP response is returned (via FastAPI BackgroundTasks).

Design notes / limitations
--------------------------
* Processing is in-process. If the server restarts while a job is running, the
  job is left in the "running" state and is not resumed automatically. This is
  an accepted limitation of the assignment; a production system would use a
  durable queue (Celery/RQ) with a broker such as Redis.
* Each recipient is handled inside its own try/except and independently
  committed, so a single failure never stops the batch and progress is always
  observable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from .models import Job, Recipient, utcnow
from .pdf_generator import generate_certificate

logger = logging.getLogger(__name__)


def process_job(
    session_factory: sessionmaker,
    output_dir: Path | str,
    verify_base_url: str,
    job_id: str,
) -> None:
    """Generate certificates for every recipient belonging to ``job_id``."""
    db = session_factory()
    try:
        job = db.get(Job, job_id)
        if job is None:
            logger.warning("process_job called for unknown job %s", job_id)
            return

        job.status = "running"
        db.commit()

        output_dir = Path(output_dir)
        # One sub-directory per job keeps files organised and easy to ZIP.
        job_dir = output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        recipients: list[Recipient] = (
            db.query(Recipient).filter(Recipient.job_id == job_id).order_by(Recipient.id).all()
        )

        for recipient in recipients:
            try:
                filename = f"{recipient.certificate_id}.pdf"
                file_path = job_dir / filename
                verify_url = (
                    f"{verify_base_url}/certificates/{recipient.certificate_id}/verify"
                )

                generate_certificate(
                    file_path,
                    name=recipient.name,
                    course=recipient.course,
                    issue_date=recipient.issue_date,
                    certificate_id=recipient.certificate_id,
                    verify_url=verify_url,
                    title=recipient.title,
                    description=recipient.description,
                    theme_color=recipient.theme_color,
                    signature_name=recipient.signature_name,
                )

                recipient.status = "success"
                recipient.error = None
                # Store a *relative* path so absolute filesystem paths never
                # leak into the database or API responses.
                recipient.file_path = f"{job_id}/{filename}"
                job.success += 1
            except Exception as exc:  # noqa: BLE001 - we deliberately isolate failures
                logger.exception("Failed to generate certificate for %s", recipient.email)
                recipient.status = "failed"
                recipient.error = str(exc)
                recipient.file_path = None
                job.failed += 1
            finally:
                job.processed += 1
                db.commit()

        # Derive the final job status from the counters.
        if job.failed == 0:
            job.status = "completed"
        elif job.success == 0:
            job.status = "failed"
        else:
            job.status = "partial"
        job.completed_at = utcnow()
        db.commit()
    finally:
        db.close()

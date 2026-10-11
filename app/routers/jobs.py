"""Job endpoints: create jobs, inspect status, list and download certificates."""

from __future__ import annotations

import os
import tempfile
import zipfile

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import crud
from ..csv_utils import CSVValidationError, parse_recipients_csv
from ..database import get_db
from ..processor import process_job
from ..schemas import JobAccepted, JobCreate, JobOut, RecipientOut
from ..security import UnsafePathError, safe_path

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _queue_processing(app, background_tasks: BackgroundTasks, job_id: str) -> None:
    """Schedule the background generation task for ``job_id``."""
    settings = app.state.settings
    background_tasks.add_task(
        process_job,
        app.state.session_factory,
        settings.output_dir,
        settings.verify_base_url,
        job_id,
    )


def _recipient_out(recipient) -> RecipientOut:
    return RecipientOut(
        certificate_id=recipient.certificate_id,
        name=recipient.name,
        email=recipient.email,
        course=recipient.course,
        issue_date=recipient.issue_date,
        status=recipient.status,
        error=recipient.error,
        title=recipient.title,
        description=recipient.description,
        theme_color=recipient.theme_color,
        signature_name=recipient.signature_name,
        # Only expose a download link once a file actually exists.
        download_url=(
            f"/certificates/{recipient.certificate_id}/download"
            if recipient.status == "success"
            else None
        ),
    )


@router.post("", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> JobAccepted:
    """Create a bulk generation job from a JSON list of recipients."""
    job = crud.create_job(db, [r.model_dump() for r in payload.recipients])
    _queue_processing(request.app, background_tasks, job.id)
    return JobAccepted(job_id=job.id, status=job.status)


@router.post(
    "/upload-csv",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job_from_csv(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    theme_color: str | None = Form(default=None),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    signature_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> JobAccepted:
    """Create a job from an uploaded CSV file.

    Optional form fields apply a shared design to every row that does not
    specify its own value (CSV columns take precedence over these defaults).
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    defaults = {
        "theme_color": theme_color,
        "title": title,
        "description": description,
        "signature_name": signature_name,
    }

    try:
        recipients = parse_recipients_csv(content, defaults=defaults)
    except CSVValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc), "errors": exc.errors},
        ) from exc

    job = crud.create_job(
        db,
        [r.model_dump() for r in recipients],
        source_filename=file.filename,
    )
    _queue_processing(request.app, background_tasks, job.id)
    return JobAccepted(job_id=job.id, status=job.status)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    """Return the status and progress of a job."""
    job = crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut(
        job_id=job.id,
        status=job.status,
        total=job.total,
        processed=job.processed,
        success=job.success,
        failed=job.failed,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get("/{job_id}/certificates", response_model=list[RecipientOut])
def list_job_certificates(job_id: str, db: Session = Depends(get_db)) -> list[RecipientOut]:
    """List every recipient of a job with its certificate status."""
    job = crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return [_recipient_out(r) for r in crud.list_recipients(db, job_id)]


@router.get("/{job_id}/download")
def download_job_zip(
    job_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download all successfully generated certificates as a single ZIP file."""
    job = crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    settings = request.app.state.settings
    recipients = [
        r
        for r in crud.list_recipients(db, job_id)
        if r.status == "success" and r.file_path
    ]
    if not recipients:
        raise HTTPException(
            status_code=404, detail="No successfully generated certificates for this job"
        )

    # Build the ZIP in a temp file inside the output dir so it can be cleaned
    # up automatically after the response is sent (kept out of the way of the
    # per-certificate files).
    tmp = tempfile.NamedTemporaryFile(
        prefix=f"{job_id}_", suffix=".zip", delete=False, dir=settings.output_dir
    )
    tmp.close()

    try:
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as archive:
            for recipient in recipients:
                try:
                    path = safe_path(
                        settings.output_dir, recipient.file_path, must_exist=True
                    )
                except (UnsafePathError, FileNotFoundError):
                    # Skip any file that vanished or is unsafe; the rest still ship.
                    continue
                archive.write(path, arcname=f"{recipient.certificate_id}.pdf")
    except Exception:
        os.unlink(tmp.name)
        raise

    background_tasks.add_task(os.unlink, tmp.name)
    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=f"certificates_{job_id}.zip",
    )

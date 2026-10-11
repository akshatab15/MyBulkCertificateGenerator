"""Certificate endpoints: download a single PDF, verify an id, render previews."""

from __future__ import annotations

import os
import tempfile
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import crud
from ..database import get_db
from ..pdf_generator import generate_certificate
from ..schemas import PreviewIn, VerifyOut
from ..security import UnsafePathError, safe_path

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.post("/preview")
def preview_certificate(
    payload: PreviewIn,
    background_tasks: BackgroundTasks,
    request: Request,
) -> FileResponse:
    """Render a single certificate PDF (useful for API testing/previews).

    This uses the exact same renderer as bulked certificates, so a previewed
    PDF is identical to what a job produces.
    """
    settings = request.app.state.settings
    temp_name = f"preview_{uuid.uuid4().hex}.pdf"
    temp_path = settings.output_dir / temp_name

    generate_certificate(
        temp_path,
        name=payload.name,
        course=payload.course,
        issue_date=payload.issue_date,
        certificate_id="CERT-PREVIEW",
        verify_url=None,
        title=payload.title,
        description=payload.description,
        theme_color=payload.theme_color,
        signature_name=payload.signature_name,
        emblem=payload.emblem,
    )

    background_tasks.add_task(os.unlink, temp_path)
    return FileResponse(
        temp_path,
        media_type="application/pdf",
        filename="certificate_preview.pdf",
    )


@router.get("/{certificate_id}/download")
def download_certificate(
    certificate_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Return the PDF for a single certificate id."""
    recipient = crud.get_recipient_by_certificate(db, certificate_id)
    if recipient is None or recipient.status != "success" or not recipient.file_path:
        raise HTTPException(status_code=404, detail="Certificate not found")

    settings = request.app.state.settings
    try:
        path = safe_path(settings.output_dir, recipient.file_path, must_exist=True)
    except (UnsafePathError, FileNotFoundError) as exc:
        # File recorded in the DB but missing on disk -> treat as not found.
        raise HTTPException(status_code=404, detail="Certificate file not found") from exc

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{certificate_id}.pdf",
    )


@router.get("/{certificate_id}/verify", response_model=VerifyOut)
def verify_certificate(certificate_id: str, db: Session = Depends(get_db)) -> VerifyOut:
    """Check whether a certificate id is valid and return its public details."""
    recipient = crud.get_recipient_by_certificate(db, certificate_id)
    if recipient is None or recipient.status != "success":
        return VerifyOut(
            valid=False,
            certificate_id=certificate_id,
            message="Certificate not found or was not successfully generated",
        )

    return VerifyOut(
        valid=True,
        certificate_id=recipient.certificate_id,
        name=recipient.name,
        course=recipient.course,
        issue_date=recipient.issue_date,
        job_id=recipient.job_id,
        message="Certificate is valid",
    )

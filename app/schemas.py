"""Pydantic schemas for request validation and API responses.

These are intentionally separate from the ORM models so the API contract can
stay stable even if the database evolves.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .config import (
    DEFAULT_DESCRIPTION,
    DEFAULT_SIGNATURE,
    DEFAULT_THEME_COLOR,
    DEFAULT_TITLE,
)

# A #RRGGBB hex colour.
HEX_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class RecipientIn(BaseModel):
    """A single recipient supplied by the client."""

    name: str = Field(..., min_length=1, max_length=255, description="Recipient full name")
    email: EmailStr = Field(..., description="Valid email address")
    course: str = Field(
        ..., min_length=1, max_length=255, description="Course or event name"
    )
    issue_date: date = Field(..., description="Issue date (YYYY-MM-DD)")

    # Optional design fields (default to the navy-and-gold template).
    title: str = Field(default=DEFAULT_TITLE, max_length=255)
    description: str = Field(default=DEFAULT_DESCRIPTION, max_length=1000)
    theme_color: str = Field(default=DEFAULT_THEME_COLOR, pattern=HEX_COLOR_PATTERN)
    signature_name: str = Field(default=DEFAULT_SIGNATURE, max_length=255)


class JobCreate(BaseModel):
    """Payload for POST /jobs."""

    recipients: list[RecipientIn] = Field(
        ..., min_length=1, description="At least one recipient is required"
    )


class JobAccepted(BaseModel):
    """Response returned immediately when a job is created."""

    job_id: str
    status: str


class RecipientOut(BaseModel):
    """A recipient as returned by the API (no filesystem paths exposed)."""

    model_config = ConfigDict(from_attributes=True)

    certificate_id: str
    name: str
    email: str
    course: str
    issue_date: date
    status: str
    error: Optional[str] = None
    download_url: Optional[str] = None
    title: str
    description: str
    theme_color: str
    signature_name: str


class JobOut(BaseModel):
    """Job status/progress as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str
    total: int
    processed: int
    success: int
    failed: int
    created_at: datetime
    completed_at: Optional[datetime] = None


class VerifyOut(BaseModel):
    """Result of certificate verification."""

    valid: bool
    certificate_id: str
    name: Optional[str] = None
    course: Optional[str] = None
    issue_date: Optional[date] = None
    job_id: Optional[str] = None
    message: str


class PreviewIn(BaseModel):
    """Payload for rendering a single certificate PDF (live preview)."""

    name: str = Field(default="Recipient Name", min_length=1, max_length=255)
    course: str = Field(default="Programme / Event Name", max_length=255)
    issue_date: date = Field(default_factory=date.today)
    title: str = Field(default=DEFAULT_TITLE, max_length=255)
    description: str = Field(default=DEFAULT_DESCRIPTION, max_length=1000)
    theme_color: str = Field(default=DEFAULT_THEME_COLOR, pattern=HEX_COLOR_PATTERN)
    signature_name: str = Field(default=DEFAULT_SIGNATURE, max_length=255)
    emblem: bool = True

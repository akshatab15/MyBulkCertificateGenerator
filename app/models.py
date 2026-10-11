"""ORM models.

Two tables:

* ``Job``        - one bulk generation request (metadata + progress counters).
* ``Recipient``  - one recipient within a job, including its certificate id,
                    generation status and generated file path.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .config import (
    DEFAULT_DESCRIPTION,
    DEFAULT_SIGNATURE,
    DEFAULT_THEME_COLOR,
    DEFAULT_TITLE,
)


def utcnow() -> datetime:
    """Timezone-naive UTC timestamp (safe for SQLite's DateTime column)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Job(Base):
    __tablename__ = "jobs"

    # A short random string is used as the public job id.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)

    # pending -> running -> completed | partial | failed
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)

    # Original CSV filename, if the job was created from a CSV upload.
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    recipients: Mapped[list["Recipient"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Recipient(Base):
    __tablename__ = "recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    course: Mapped[str] = mapped_column(String(255), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Customisable design fields (all optional with sensible defaults).
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, default=DEFAULT_TITLE
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default=DEFAULT_DESCRIPTION
    )
    theme_color: Mapped[str] = mapped_column(
        String(7), nullable=False, default=DEFAULT_THEME_COLOR
    )
    signature_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default=DEFAULT_SIGNATURE
    )

    # Public, unique, verifiable certificate identifier.
    certificate_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    # pending -> success | failed
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Path relative to the output directory. Never an absolute path.
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    job: Mapped["Job"] = relationship(back_populates="recipients")

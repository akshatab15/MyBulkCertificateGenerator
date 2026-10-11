"""CSV parsing and validation for bulk uploads.

Required header columns: ``name,email,course,issue_date`` (order-independent).
Optional design columns: ``title,description,theme_color,signature_name``.
``issue_date`` must be an ISO date (YYYY-MM-DD).
"""

from __future__ import annotations

import csv
import io

from pydantic import ValidationError

from .schemas import RecipientIn

REQUIRED_COLUMNS = {"name", "email", "course", "issue_date"}
OPTIONAL_COLUMNS = {"title", "description", "theme_color", "signature_name"}

# All fields that can appear in a row, in a stable order.
FIELDS = (
    "name",
    "email",
    "course",
    "issue_date",
    "title",
    "description",
    "theme_color",
    "signature_name",
)


class CSVValidationError(ValueError):
    """Raised when the uploaded CSV is malformed or contains invalid rows."""

    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(message)
        self.errors = errors or []


def _row_to_fields(normalised: dict, defaults: dict) -> dict:
    """Build a RecipientIn kwargs dict, applying shared defaults for blanks.

    Blank optional cells and blank-but-required cells alike are dropped so the
    Pydantic schema reports "field required" as a clear row error.
    """
    fields: dict = {}
    for key in FIELDS:
        value = normalised.get(key)
        if value in (None, ""):
            value = defaults.get(key)
        if value not in (None, ""):
            fields[key] = value
    return fields


def parse_recipients_csv(content: bytes, defaults: dict | None = None) -> list[RecipientIn]:
    """Parse CSV bytes into validated ``RecipientIn`` objects.

    ``defaults`` lets the caller apply a shared title/description/theme colour
    to rows that do not specify one themselves.

    Raises ``CSVValidationError`` with row-level detail on any problem.
    """
    defaults = defaults or {}

    try:
        text = content.decode("utf-8-sig")  # tolerate BOM from Excel
    except UnicodeDecodeError as exc:
        raise CSVValidationError("CSV must be UTF-8 encoded") from exc

    # Sniff handles comma/semicolon delimiters automatically.
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if reader.fieldnames is None:
        raise CSVValidationError("CSV file is empty")

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise CSVValidationError(
            f"Missing required column(s): {', '.join(sorted(missing))}"
        )

    recipients: list[RecipientIn] = []
    row_errors: list[dict] = []
    for index, row in enumerate(reader, start=2):  # row 1 is the header
        # Normalise header casing/whitespace for each row.
        normalised = {
            (k or "").strip().lower(): (v.strip() if isinstance(v, str) else v)
            for k, v in row.items()
        }
        # Skip completely blank lines.
        if not any(normalised.get(col) for col in REQUIRED_COLUMNS):
            continue
        try:
            recipients.append(RecipientIn(**_row_to_fields(normalised, defaults)))
        except ValidationError as exc:
            row_errors.append({"row": index, "errors": _format_pydantic_errors(exc)})

    if row_errors:
        raise CSVValidationError("One or more rows are invalid", errors=row_errors)
    if not recipients:
        raise CSVValidationError("CSV contains no data rows")

    return recipients


def _format_pydantic_errors(exc: ValidationError) -> list[dict]:
    """Turn a Pydantic error into a compact, JSON-friendly structure."""
    return [
        {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]

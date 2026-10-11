"""Certificate id generation.

Certificate ids are random, URL-safe and non-guessable. Uniqueness is also
enforced by a database constraint, so verification can simply check whether an
id exists in the database.
"""

from __future__ import annotations

import secrets

PREFIX = "CERT"
_TOKEN_BYTES = 5  # ~10 hex chars -> ample space, still short/readable.


def generate_certificate_id() -> str:
    return f"{PREFIX}-{secrets.token_hex(_TOKEN_BYTES).upper()}"


def generate_job_id() -> str:
    return secrets.token_hex(8).upper()

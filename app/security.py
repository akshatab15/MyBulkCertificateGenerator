"""Filesystem safety helpers.

Everything written or read by the API must live inside the configured output
directory. ``safe_path`` resolves a user-influenced relative path and rejects
anything that tries to escape the base directory (path traversal, absolute
paths, symlinks pointing outside).
"""

from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when a path would escape the allowed base directory."""


def safe_path(base_dir: Path | str, relative: str, *, must_exist: bool = False) -> Path:
    """Resolve ``relative`` under ``base_dir`` and guarantee containment.

    Raises ``UnsafePathError`` if the resolved path is outside ``base_dir``.
    """
    base = Path(base_dir).resolve()
    # Reject absolute inputs outright; callers must supply relative names.
    candidate = (base / relative).resolve()

    if candidate != base and base not in candidate.parents:
        raise UnsafePathError(f"Path escapes output directory: {relative!r}")

    if must_exist and not candidate.is_file():
        raise FileNotFoundError(relative)

    return candidate

"""Regression tests for the cross-platform font fallback.

A real deployed job processed two recipients: the **first** certificate failed
with ``Path.replace() takes 2 positional arguments but 3 were given`` while the
**second** succeeded.

Cause: on Linux (e.g. Render) the Windows "Times New Roman" candidate does not
exist, so ``_ensure_fonts`` reached its Windows-separator fallback
``p.replace("/", "\\\\")``. ``p`` is already a :class:`pathlib.Path`, whose
``replace`` takes a single argument, so it raised ``TypeError``. Because
``_FONTS_READY`` was flipped to ``True`` *before* the failure, only the first
certificate of each process crashed; every later one returned early and
succeeded on the built-in fallback font.

These tests force the missing-Windows-font code path and assert the fallback is
now silent on both Windows (local) and Linux (Render).
"""

from __future__ import annotations

from app import pdf_generator

# A candidate set whose paths never exist on any platform, mimicking a Linux
# host that lacks the Windows Times New Roman fonts.
_MISSING_WINDOWS_FONTS = (
    (
        "C:/nonexistent-fonts/times.ttf",
        "C:/nonexistent-fonts/timesbd.ttf",
        "C:/nonexistent-fonts/timesi.ttf",
        "C:/nonexistent-fonts/timesbi.ttf",
    ),
)


def _force_missing_fonts(monkeypatch) -> None:
    """Point the font search at non-existent paths and clear the ready latch."""
    monkeypatch.setattr(pdf_generator, "_FONT_CANDIDATES", _MISSING_WINDOWS_FONTS)
    monkeypatch.setattr(pdf_generator, "_FONTS_READY", False)


def test_ensure_fonts_does_not_raise_when_candidates_are_missing(monkeypatch):
    """The exact crash path: _ensure_fonts must not call Path.replace()."""
    _force_missing_fonts(monkeypatch)

    pdf_generator._ensure_fonts()  # must not raise

    assert pdf_generator._FONTS_READY is True


def test_ensure_fonts_is_idempotent(monkeypatch):
    """A second call is a no-op and still must not raise."""
    _force_missing_fonts(monkeypatch)

    pdf_generator._ensure_fonts()
    pdf_generator._ensure_fonts()

    assert pdf_generator._FONTS_READY is True


def test_two_recipient_job_succeeds_when_system_fonts_are_missing(
    client, recipients, monkeypatch
):
    """Reproduces the deployed symptom end-to-end.

    Before the fix the first recipient failed and the second succeeded (job
    status ``partial``); after the fix both must succeed.
    """
    _force_missing_fonts(monkeypatch)

    payload = {"recipients": recipients[:2]}  # the reported job had two
    job_id = client.post("/jobs", json=payload).json()["job_id"]

    status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == "completed"
    assert status["total"] == 2
    assert status["processed"] == 2
    assert status["success"] == 2
    assert status["failed"] == 0

    certs = client.get(f"/jobs/{job_id}/certificates").json()
    assert all(cert["status"] == "success" for cert in certs)
    assert all(cert["download_url"] for cert in certs)

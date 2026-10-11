# Bulk Certificate Generator API

A small, well-tested, **backend-only REST API** that generates PDF
certificates in bulk, tracks job progress in the background, lets you download
individual certificates or a ZIP of a whole batch, and verifies certificate
IDs (with a QR code printed on each certificate).

Built with **FastAPI + SQLAlchemy + SQLite + ReportLab**, validated with
**Pydantic**, and tested with **Pytest**. There is no web UI: use the
interactive **Swagger UI at `/docs`** or the endpoints directly.

---

## 1. Features

Required features:

- Create a bulk certificate generation job for many recipients.
- Accept recipient name, email, course/event name, issue date and a unique
  certificate ID (generated automatically).
- Strict input validation with clear, field-level errors.
- Generate one PDF certificate per valid recipient from a single template.
- Process jobs **in the background** and track status and progress.
- Track total / processed / successful / failed counts.
- One failed certificate never stops the rest of the batch.
- Check job status and progress.
- Retrieve individual generated certificates.
- Graceful handling of missing files, invalid requests, unknown job IDs and
  generation failures.

Extra improvements:

- **CSV upload** to create bulk jobs.
- **ZIP download** of all successfully generated certificates in a job.
- **Unique certificate IDs** + a **verification API**.
- **QR codes** on each certificate linking to the verification endpoint.

---

## 2. Tech stack

| Concern            | Choice                         |
| ------------------ | ------------------------------ |
| Language           | Python 3.11+ (tested on 3.13)  |
| Web framework      | FastAPI                        |
| ASGI server        | Uvicorn                        |
| ORM / database     | SQLAlchemy 2.x + SQLite        |
| Validation         | Pydantic v2                    |
| PDF generation     | ReportLab                      |
| QR codes           | qrcode + Pillow                |
| Testing            | Pytest + Starlette TestClient  |

---

## 3. Project structure

```
MyBulkCertificateGenerator/
├── app/
│   ├── main.py            # FastAPI app factory + router registration
│   ├── config.py          # Settings + design defaults (navy/gold palette)
│   ├── database.py        # SQLAlchemy engine/session, get_db, mini-migration
│   ├── models.py          # Job + Recipient ORM models
│   ├── schemas.py         # Pydantic request/response models
│   ├── crud.py            # Database access helpers
│   ├── cert_ids.py        # Unique certificate/job id generation
│   ├── pdf_generator.py   # ReportLab certificate template (navy/gold + QR)
│   ├── processor.py       # Background job processing loop
│   ├── csv_utils.py       # CSV parsing + validation
│   ├── security.py        # Safe-path helper (path-traversal protection)
│   └── routers/
│       ├── health.py      # GET /health
│       ├── jobs.py        # /jobs endpoints
│       └── certificates.py# /certificates endpoints + preview
├── tests/                 # Pytest suite (44 tests)
├── examples/
│   └── recipients_sample.csv
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
└── README.md
```

---

## 4. Setup and installation

```powershell
# From the project root
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate           # macOS / Linux

pip install -r requirements.txt
```

All configuration is optional; defaults work out of the box. To override, copy
`.env.example` to `.env` or set environment variables:

| Variable                       | Default                 | Purpose                                              |
| ------------------------------ | ----------------------- | ---------------------------------------------------- |
| `DATABASE_URL`                 | `sqlite:///./certificates.db` | SQLAlchemy database URL                        |
| `OUTPUT_DIR`                   | `./output`              | Where PDFs and ZIP files are written                 |
| `CERTIFICATE_VERIFY_BASE_URL`  | `http://localhost:8000` | Base URL embedded in the verification QR code        |

> **QR verification URLs.** Each certificate prints a QR code that links to
> `CERTIFICATE_VERIFY_BASE_URL/certificates/{certificate_id}/verify`. Set
> `CERTIFICATE_VERIFY_BASE_URL` to a host your phone can reach (a LAN IP,
> tunnel or deployed domain) — otherwise the default `localhost` resolves to
> the phone itself and verification fails. The legacy `PUBLIC_BASE_URL`
> variable is still honoured as a fallback.

---

## 5. Running the app

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then open the interactive API docs (Swagger UI) at
<http://localhost:8000/docs>. The alternative ReDoc view is at
<http://localhost:8000/redoc>, and the raw OpenAPI schema is at
<http://localhost:8000/openapi.json>.

This is a backend-only project - there is no web UI. You can exercise every
endpoint from Swagger UI. For a quick PDF sanity check without creating a job,
use `POST /certificates/preview` (see below).

---

## 5b. Certificate design

A single predefined, fully vector template (landscape A4) with these elements,
matching the reference design:

- Dark navy panel on the left with a gently curved edge.
- Gold curved accents (and a lighter gold highlight) between the panel and the
  white area.
- White background with subtle thin vertical decorative lines.
- Large "CERTIFICATE OF APPRECIATION" heading (driven by the `title` field).
- Recipient name in gold serif typography.
- Event/course name and a short description.
- Date and signature areas at the bottom.
- An original award emblem (rings + laurel + star) drawn from basic shapes,
  shown in the navy panel.
- A verification QR code.

Customisable fields (all optional, with defaults): `title`, `description`,
`theme_color` (`#rrggbb`, default navy `#051a2a`), `signature_name`, and an
`emblem` toggle for previews. There is intentionally **one template** with
styling options - not a multi-template editor.

The palette was derived from the reference image (navy `#051a2a`, gold
`#b78d2f`, light gold `#e2cfa5`, off-white `#f3f1ec`).

---

## 6. API reference

| Method | Endpoint                                  | Description                                  |
| ------ | ----------------------------------------- | -------------------------------------------- |
| GET    | `/health`                                 | Liveness check                               |
| POST   | `/jobs`                                   | Create a bulk job from a JSON list           |
| POST   | `/jobs/upload-csv`                        | Create a bulk job from a CSV file            |
| GET    | `/jobs/{job_id}`                          | Job status and progress                      |
| GET    | `/jobs/{job_id}/certificates`             | List recipients + certificate status         |
| GET    | `/jobs/{job_id}/download`                 | ZIP of all successful certificates           |
| POST   | `/certificates/preview`                   | Render a single certificate PDF (preview)    |
| GET    | `/certificates/{certificate_id}/download` | Download one certificate PDF                 |
| GET    | `/certificates/{certificate_id}/verify`   | Verify a certificate ID                      |

### Example: create a job (JSON)

```powershell
curl -X POST http://localhost:8000/jobs `
  -H "Content-Type: application/json" `
  -d '{
        "recipients": [
          {"name":"Alice Smith","email":"alice@example.com","course":"Python 101","issue_date":"2026-01-15"},
          {"name":"Bob Jones","email":"bob@example.com","course":"Data Structures","issue_date":"2026-02-20"}
        ]
      }'
```

Optional per-recipient design fields (any may be omitted; defaults apply):
`title`, `description`, `theme_color`, `signature_name`. Example:

```json
{
  "recipients": [
    {
      "name": "Alice Smith",
      "email": "alice@example.com",
      "course": "Python 101",
      "issue_date": "2026-01-15",
      "title": "Certificate of Excellence",
      "description": "Awarded for outstanding work.",
      "theme_color": "#5b1f2a",
      "signature_name": "Dean of Studies"
    }
  ]
}
```

Response (`202 Accepted`):

```json
{ "job_id": "AC7E302D1FA67236", "status": "pending" }
```

### Example: check status

```powershell
curl http://localhost:8000/jobs/AC7E302D1FA67236
```

```json
{
  "job_id": "AC7E302D1FA67236",
  "status": "completed",
  "total": 2,
  "processed": 2,
  "success": 2,
  "failed": 0,
  "created_at": "2026-01-01T12:00:00",
  "completed_at": "2026-01-01T12:00:02"
}
```

Job `status` is one of: `pending`, `running`, `completed`, `partial`
(some succeeded, some failed) or `failed` (none succeeded).

### Example: upload a CSV

```powershell
curl -X POST http://localhost:8000/jobs/upload-csv `
  -F "file=@examples/recipients_sample.csv"
```

The CSV must have the columns `name,email,course,issue_date`
(`issue_date` in `YYYY-MM-DD`). Optional design columns: `title`,
`description`, `theme_color`, `signature_name`. You can also pass shared
defaults as form fields (applied to rows without their own value):

```powershell
curl -X POST http://localhost:8000/jobs/upload-csv `
  -F "file=@examples/recipients_sample.csv" `
  -F "theme_color=#123d2b" -F "title=Certificate of Merit"
```

Invalid rows return `400` with row-level details.

### Example: PDF preview

```powershell
curl -X POST http://localhost:8000/certificates/preview `
  -H "Content-Type: application/json" `
  -d '{"name":"Alice","course":"Python 101","issue_date":"2026-01-15","theme_color":"#051a2a"}' `
  --output preview.pdf
```

### Example: download

```powershell
curl -OJ http://localhost:8000/jobs/AC7E302D1FA67236/download
curl -OJ http://localhost:8000/certificates/CERT-1D69D1B0F6/download
```

### Example: verify

```powershell
curl http://localhost:8000/certificates/CERT-1D69D1B0F6/verify
```

```json
{
  "valid": true,
  "certificate_id": "CERT-1D69D1B0F6",
  "name": "Alice Smith",
  "course": "Python 101",
  "issue_date": "2026-01-15",
  "job_id": "AC7E302D1FA67236",
  "message": "Certificate is valid"
}
```

---

## 7. Testing

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The suite covers: job creation, input validation, PDF generation, progress and
status, single-recipient failure isolation, individual downloads, ZIP
downloads, CSV upload and certificate verification. It also covers the
redesign: custom title/description/colour/signature fields, the emblem toggle,
the preview endpoint, optional CSV design columns, and the legacy-DB
migration. It also verifies that the configured
`CERTIFICATE_VERIFY_BASE_URL` is what gets embedded in each certificate's QR
code. Each test runs against a temporary SQLite database and a temporary
output directory, so **no real user data is touched**.

Current result: **55 passed**.

---

## 8. Design decisions

- **App factory (`create_app`)** lets tests build fully isolated instances
  (temp DB + temp output dir) with no globals leaking between runs.
- **Relational schema** (`jobs` 1—* `recipients`) mirrors the domain: a job
  owns many recipient rows, each with its own status and certificate ID.
- **Certificate IDs** are short random tokens (`CERT-XXXXXXXXXXXXXXXX`),
  unique-constrained in the DB, so verification is a simple existence check and
  IDs are not guessable.
- **File safety:** only *relative* paths are stored. Every read resolves the
  path and rejects anything escaping the output directory
  (`app/security.py`), preventing path traversal. Absolute filesystem paths are
  never returned in API responses.
- **Progress tracking** updates counters after every recipient and commits
  independently, so status is observable mid-run and a crash loses at most one
  record.
- **Failure isolation:** each certificate is generated inside its own
  `try/except`; failures are recorded per recipient while the batch continues.
- **One renderer:** `POST /certificates/preview` and the bulk generator call
  the same `generate_certificate` function, so a previewed PDF is identical to
  what a job produces.
- **Backend-only by design:** no UI code or static assets are shipped; the API
  contract is documented through OpenAPI (Swagger UI at `/docs`).

## 9. Background processing limitation

Jobs run via FastAPI `BackgroundTasks`, i.e. **in the same process** as the API.

- Simple and dependency-free (no broker/worker to run).
- **Not durable:** if the server restarts mid-job, that job stays `running`
  and is not resumed automatically.
- **Not horizontally scalable** on its own (each worker would need its own
  queue).
- For production, swap the task dispatch in `app/routers/jobs.py` for a real
  queue such as **Celery/RQ + Redis**. The `processor.process_job` logic is
  already isolated, so only the dispatch call would change.

---

## 10. What is intentionally NOT built

Per the assignment, there is **no template editor and no multiple certificate
designs** — a single predefined template is used.

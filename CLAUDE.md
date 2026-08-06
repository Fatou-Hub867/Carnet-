# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Carnet+ — a medical practice management web app connecting **patients** and **doctors**, with an **admin** space for moderation. A patient books appointments, messages their doctor, and consults their prescriptions and health record. A doctor publishes availability, accepts/refuses appointments, writes prescriptions, and tracks chronic-care patients. An admin validates doctor accounts (against a diploma upload) and moderates reviews/complaints.

Repo layout:
```
CarnetPlus/
├── Backend-API/    # FastAPI (async) REST API — see Backend-API/Readme.md
├── frontend/       # Static HTML/CSS/JS, no framework/build step — see frontend/README.md
└── docs/           # Specs and plans (docs/superpowers/)
```

## Commands

### All-in-Docker (recommended)

A single `docker compose up` at the repo root runs everything — API, frontend, Postgres, MinIO — with hot-reload and automatic Alembic migrations. Requires `Backend-API/.env` to exist first (see `Backend-API/.env.example`).

```bash
docker compose up -d --build
# Frontend: http://localhost:8010/index.html
# Swagger:  http://localhost:8010/docs
# Health:   http://localhost:8010/health

# Tests / lint inside the running container
docker compose exec api python -m pytest -q
docker compose exec api ruff check .

# New migration after changing models
docker compose exec api alembic revision --autogenerate -m "message"
```

### Local (without Docker)

All backend commands run from `Backend-API/`. `docker-compose.yml` now lives at the repo root and defines all three services (`db`, `minio`, `api`) — for this local path, only start `db`/`minio` and run the API yourself with `uv`.

```bash
# Infra (Postgres :5432, MinIO API :6002 / console :6001) — from the repo root
docker compose up -d db minio

cd Backend-API

# Deps (uv-based project)
uv venv
uv pip install -r requirements-dev.txt      # runtime + test/dev tooling
# uv pip install -r requirements.text       # runtime only (prod)

# Migrations (Alembic, async template)
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "message"
uv run alembic downgrade -1

# Run (backend + frontend in one process — FastAPI mounts frontend/ as static files)
uv run uvicorn app:app --port 8010 --reload
# Frontend: http://localhost:8010/index.html
# Swagger:  http://localhost:8010/docs
# Health:   http://localhost:8010/health

# Tests (pytest, asyncio_mode=auto, SQLite async — no external services needed)
uv run python -m pytest -q
uv run python -m pytest tests/test_appointments_flow.py -q   # single file
uv run python -m pytest tests/test_appointments_flow.py::test_name -q   # single test

# Lint/format
uv run ruff check .
uv run ruff format .
```

Dev-only admin seed (no UI creates the first admin account — it must exist in DB, as `tests/conftest.py`'s `admin_token` fixture does):
```bash
uv run python scripts/seed_admin.py
```

Dev-only data reset (wipes patients/doctors and everything derived from them, keeps admins — no "reset the database" API route by design):
```bash
uv run python scripts/reset_dev_data.py
```

## Architecture (Backend-API/)

**Feature-based** modules under `features/`, each a self-contained 4-layer slice: `models.py` (SQLAlchemy), `schemas.py` (Pydantic), `logic.py` (business logic, no FastAPI dependency besides `HTTPException`), `routes.py` (endpoints, wires auth + calls into `logic`). Modules: `Auth`, `Patients`, `Doctors`, `Appointments`, `Prescriptions`, `HealthRecords`, `Messaging`, `Admin`, `ChronicCare`, `Notifications`.

`core/` holds cross-cutting pieces:
- `config.py` — settings via `.env` (Pydantic Settings)
- `database.py` — async engine/session, declarative `Base`
- `security.py` — bcrypt password hashing + JWT
- `storage.py` — S3/MinIO: upload, presigned URLs, `ensure_bucket_exists` (called at app startup via lifespan)
- `email.py` — Resend
- `deps.py` — auth dependencies: `get_current_patient` / `get_current_doctor` / `get_current_admin` / `get_current_participant` (bi-role, used by Messaging — resolves either a patient or a doctor from the JWT since messaging endpoints serve both)

`app.py` is the entrypoint: registers each feature's router, then mounts `frontend/` as static files at `/` — **one process serves both the API and the UI**, so there's no CORS to configure locally.

### Architectural decisions worth knowing before touching this code

- **Private files**: only object *keys* are stored in the DB, never public URLs — presigned URLs are generated on demand (`core/storage.py`). Don't add public bucket access or store raw URLs.
- **View vs download**: `core/storage.get_file_url()` takes an optional `download_filename` — omitted, the URL renders inline (view); passed, it adds a presigned `Content-Disposition: attachment` override (download). Every `/download` endpoint returns both as `{view_url, download_url}` (`HealthRecords.DocumentUrlsOut`). Objects with no stored original filename (the doctor diploma) recover it from the storage key via `original_filename_from_key()` — safe because `upload_file()` always prefixes with a fixed-width 36-char `uuid4()`.
- **Vital signs share one table**: `VitalSignBilan` holds both patient-entered bilans (tension/glycemia/heart rate) and the automatic weight snapshot written inline by `Patients/logic.update_patient_profile` whenever `weight_kg` changes — the profile stays the only place a patient edits their weight, the carnet only ever displays it.
- **Doctor access to a patient's carnet**: gated by `_authorize_doctor_for_patient` (`HealthRecords/logic.py`) — at least one `confirmed`/`completed` appointment between that doctor and patient, else 404 (never 403, so an unrelated doctor can't even confirm the patient_id exists). Same guard on read and on the doctor's document-upload endpoint.
- **Passive dashboards**: reminders (treatments, upcoming appointments) and chronic-care alerts are computed **at read time**, not via a scheduler or background job. There is deliberately no cron/worker in this project — don't introduce one for a "simple" reminder feature; compute it in the query/logic layer instead.
- **Snapshotted price**: `Appointment.amount` is copied from `Doctor.consultation_fee` at confirmation time, not looked up live afterward — changing a doctor's fee must never retroactively change past/pending appointments.
- **Anti double-booking**: appointment reservation takes a `SELECT ... FOR UPDATE` lock on the availability slot.
- **Health record auto-fill**: prescriptions and doctor-sent message attachments are filed into the patient's health record automatically, written *inline by the producing feature* (e.g. `Prescriptions` writes its own `HealthRecordDocument`) rather than via a shared callback/hook from `HealthRecords`.
- **Prescription without an appointment**: `POST /prescriptions` accepts either `appointment_id` (must be `COMPLETED`, the original flow) or `patient_id` alone — allowed as soon as the doctor already has a `Conversation` with that patient (messaging-initiated prescribing), 404 otherwise. `Prescription.appointment_id` is nullable to support this second path.
- **Soft delete only**: deleting a patient or doctor account sets `status = deleted`; health data is never hard-deleted.
- **Doctor suspension**: automatic at the 5th *active* complaint (`Complaint.status`, not a raw count — a resolved batch doesn't count toward the next suspension), 1-month suspension, automatic reactivation lazily triggered on next doctor login (`Auth/logic.authenticate_doctor`), no scheduler.
- **Messaging**: REST + polling by design, not WebSocket, for V1.
- **Testing**: the suite runs against SQLite (`aiosqlite`) via `tests/conftest.py`, with S3 and email network calls patched out — it needs no Docker services. Don't assume Postgres-only SQL features in code paths covered by tests.

Full endpoint-by-endpoint reference: [Backend-API/Readme.md](Backend-API/Readme.md).

## Frontend (frontend/)

Static HTML/CSS/JS, one page per screen, no framework and no build step. `auth.js` manages the session (JWT in `localStorage`, plus the logged-in user's identity since 2026-08-04); `api.js` centralizes `fetch` calls to the API. `app.js` holds shared UI behavior (multi-step signup flows, modals, avatar rendering, sidebar identity, etc.) — see [frontend/README.md](frontend/README.md) for the page inventory and what's already wired to the backend vs. still showing hardcoded sample data (as of 2026-08-04, only the patient/doctor dashboard's "traitements en cours" tile remains hardcoded).

## Conventions

- Feature module and directory names are in English (`Auth`, `Patients`, ...) per the global code-identifier convention; everything else (docs, commit history, this file) is French — see the user's global CLAUDE.md.
- New DB schema changes go through Alembic (`alembic revision --autogenerate`), never manual DDL.
- SQLAlchemy queries are always parameterized; don't build SQL from f-strings.
- Secrets live in `Backend-API/.env` (gitignored) — see `.env.example` for the required keys (`DATABASE_URL`, S3/MinIO creds, `JWT_SECRET_KEY`, `RESEND_API_KEY`).

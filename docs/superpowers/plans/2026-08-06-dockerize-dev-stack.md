# Dockerize Dev Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docker compose up` at the repo root run the entire dev stack — FastAPI API (which also serves the static frontend), Postgres, and MinIO — with hot-reload and automatic Alembic migrations, with no local Python/uv install required.

**Architecture:** One `Dockerfile` in `Backend-API/` (installs `requirements-dev.txt` + the `tesseract-ocr` system package pytesseract shells out to), built from a repo-root build context so it can also copy `frontend/`. One `docker-compose.yml` moved from `Backend-API/` to the repo root, keeping the existing `db`/`minio` services (plus a `db` healthcheck) and adding a new `api` service that bind-mounts the whole repo for hot-reload and overrides only the two network-dependent env vars (`DATABASE_URL`, `S3_ENDPOINT_URL`) on top of the existing `Backend-API/.env`.

**Tech Stack:** Docker, Docker Compose, Python 3.14-slim, FastAPI/uvicorn, Alembic, pytest (existing project stack — no new application dependencies).

Reference spec: `docs/superpowers/specs/2026-08-06-dockerize-dev-stack-design.md`

---

### Task 1: Add `.dockerignore` at the repo root

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Create the file**

```
.git
**/__pycache__
**/*.pyc
Backend-API/.venv
Backend-API/.pytest_cache
Backend-API/htmlcov
Backend-API/*.egg-info
**/.env
docs/superpowers
```

Note: `**/.env` excludes the real `Backend-API/.env` from the build context (it's read at container runtime via `env_file:`, not needed at build time, and must never end up baked into an image layer).

- [ ] **Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore: add .dockerignore for the repo-root Docker build context"
```

---

### Task 2: Write `Backend-API/Dockerfile`

**Files:**
- Create: `Backend-API/Dockerfile`

- [ ] **Step 1: Write the Dockerfile**

```dockerfile
FROM python:3.14-slim

# tesseract-ocr: pytesseract shells out to the `tesseract` binary at runtime
# (doctor diploma OCR verification at sign-up) — the Python package alone is not enough.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/Backend-API

COPY Backend-API/requirements-dev.txt Backend-API/requirements.text ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY Backend-API /app/Backend-API
COPY frontend /app/frontend

EXPOSE 8010

CMD ["sh", "-c", "alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port 8010 --reload"]
```

- [ ] **Step 2: Build the image standalone to verify it compiles**

Run: `cd "c:\Users\PC\Documents\CarnetPlus" && docker build -f Backend-API/Dockerfile -t carnetplus-api .`

Expected: build succeeds, ends with `Successfully tagged carnetplus-api:latest` (or the buildkit equivalent final `naming to docker.io/library/carnetplus-api done`). If `tesseract-ocr` fails to install, check the base image's `apt` sources are reachable (network access required for this step).

- [ ] **Step 3: Commit**

```bash
git add Backend-API/Dockerfile
git commit -m "feat: add Dockerfile for the FastAPI API service"
```

---

### Task 3: Move and extend `docker-compose.yml` to the repo root

**Files:**
- Create: `docker-compose.yml` (repo root)
- Delete: `Backend-API/docker-compose.yml`

- [ ] **Step 1: Move the file with git so history is preserved**

Run: `cd "c:\Users\PC\Documents\CarnetPlus" && git mv Backend-API/docker-compose.yml docker-compose.yml`

- [ ] **Step 2: Edit the moved file to add the healthcheck on `db` and the new `api` service**

Replace the full contents of `docker-compose.yml` with:

```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: medical_practice
      POSTGRES_PASSWORD: medical_practice
      POSTGRES_DB: medical_practice
    ports:
      - "5432:5432"
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medical_practice"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "6002:9000"
      - "6001:9001"
    volumes:
      - minio_data:/data

  api:
    build:
      context: .
      dockerfile: Backend-API/Dockerfile
    working_dir: /app/Backend-API
    command: sh -c "alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port 8010 --reload"
    volumes:
      - .:/app
    ports:
      - "8010:8010"
    env_file:
      - Backend-API/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://medical_practice:medical_practice@db:5432/medical_practice
      S3_ENDPOINT_URL: http://minio:9000
    depends_on:
      db:
        condition: service_healthy

volumes:
  db_data:
  minio_data:
```

- [ ] **Step 3: Validate the compose file syntax**

Run: `cd "c:\Users\PC\Documents\CarnetPlus" && docker compose config --quiet`

Expected: no output, exit code 0. If it errors, fix the YAML before continuing (common culprit: indentation).

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml Backend-API/docker-compose.yml
git commit -m "feat: move docker-compose.yml to repo root and add the api service"
```

---

### Task 4: Bring up the full stack and verify it actually works

This task has no code changes — it's the end-to-end verification that Tasks 1-3 produce a working stack. Requires `Backend-API/.env` to already exist locally with real values (it's gitignored, already a prerequisite for running this project at all per the project's own CLAUDE.md).

**Files:** none (verification only)

- [ ] **Step 1: Start the stack**

Run: `cd "c:\Users\PC\Documents\CarnetPlus" && docker compose up -d --build`

Expected: three containers created and started (`carnetplus-db-1` or similar, `-minio-1`, `-api-1` — exact names depend on the folder name Compose derives as project name).

- [ ] **Step 2: Watch the API container logs for migrations + successful startup**

Run: `docker compose logs api --tail 50`

Expected: log lines showing Alembic running (`Running upgrade ... -> ..., <migration message>`) followed by uvicorn's `Application startup complete.` with no traceback in between. If `alembic upgrade head` fails, it's almost always because `db` wasn't actually ready yet — re-check the `depends_on: condition: service_healthy` wiring from Task 3, or that `db`'s healthcheck is passing (`docker compose ps` should show `db` as `healthy`).

- [ ] **Step 3: Hit the health endpoint from the host**

Run: `curl -s http://localhost:8010/health`

Expected: `{"status":"ok"}`

- [ ] **Step 4: Hit the frontend from the host**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8010/index.html`

Expected: `200`

- [ ] **Step 5: Confirm hot-reload works**

Make a trivial whitespace-only edit to `Backend-API/app.py` (e.g. add a blank line at the end), save it, then re-run:

Run: `docker compose logs api --tail 10`

Expected: a line like `WARNING: WatchFiles detected changes ... Reloading...` shortly after the save. Revert the whitespace edit afterward (`git checkout -- Backend-API/app.py`) — it's not a real change to commit.

- [ ] **Step 6: Run the test suite inside the container**

Run: `docker compose exec api pytest -q`

Expected: all tests pass (81 tests as of the last recorded run in `Backend-API/CLAUDE.md` — the exact count may have grown since, but there should be zero failures).

- [ ] **Step 7: Run ruff inside the container**

Run: `docker compose exec api ruff check .`

Expected: `All checks passed!` (or pre-existing lint issues unrelated to this change — do not fix unrelated lint issues as part of this task).

- [ ] **Step 8: Tear down**

Run: `docker compose down`

This stops and removes the containers but keeps the named volumes (`db_data`, `minio_data`), so data persists across restarts — consistent with the pre-existing `db`/`minio` behavior.

No commit for this task (verification only, no files changed).

---

### Task 5: Update documentation to point at the new Docker-first workflow

**Files:**
- Modify: `CLAUDE.md:17-41` (root)
- Modify: `Backend-API/Readme.md:56-57`, `Backend-API/Readme.md` (Commands/setup section around line 95)
- Modify: `README.md` (repo root, around line 59)

- [ ] **Step 1: Update the root `CLAUDE.md` Commands section**

In `CLAUDE.md`, replace the block from `## Commands` through the closing ` ``` ` after `uv run ruff format .` (currently lines 17-51) with:

```markdown
## Commands

### All-in-Docker (recommended)

A single `docker compose up` at the repo root runs everything — API, frontend, Postgres, MinIO — with hot-reload and automatic Alembic migrations. Requires `Backend-API/.env` to exist first (see `Backend-API/.env.example`).

```bash
docker compose up -d --build
# Frontend: http://localhost:8010/index.html
# Swagger:  http://localhost:8010/docs
# Health:   http://localhost:8010/health

# Tests / lint inside the running container
docker compose exec api pytest -q
docker compose exec api ruff check .

# New migration after changing models
docker compose exec api alembic revision --autogenerate -m "message"
```

### Local (without Docker)

All backend commands run from `Backend-API/`.

```bash
cd Backend-API

# Infra (Postgres :5432, MinIO API :6002 / console :6001)
docker compose up -d db minio

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
```

Note the `docker compose up -d db minio` in the local path: since `docker-compose.yml` is now at the repo root and defines all three services, running it from `Backend-API/` no longer applies — commands in this section must run from the repo root, and the local (non-Docker) path only needs `db`+`minio`, not the `api` service.

- [ ] **Step 2: Update `Backend-API/Readme.md`**

Change line 57 from:
```
├── docker-compose.yml         # PostgreSQL (5432) + MinIO (6000 API / 6001 console)
```
to (drop the line — the file no longer lives under `Backend-API/`; also fixes the pre-existing stale port `6000` which doesn't match the actual `6002:9000` mapping in the compose file):
```
```
(i.e. remove that line entirely from the tree listing)

Change line 95 from:
```
docker compose up -d          # PostgreSQL:5432, MinIO API:6000, console:6001
```
to:
```
docker compose up -d          # from the repo root — runs API + PostgreSQL:5432 + MinIO API:6002/console:6001
```

- [ ] **Step 3: Update the repo-root `README.md`**

Change line 59 (`docker compose up -d`) to clarify it must run from the repo root and now also starts the API — read the surrounding 10 lines first with `Read` to match the existing tone/format before editing, since this file's structure wasn't inspected in detail during planning.

- [ ] **Step 4: Verify no other stale references remain**

Run: `cd "c:\Users\PC\Documents\CarnetPlus" && grep -rn "Backend-API/docker-compose\|cd Backend-API" CLAUDE.md Backend-API/Readme.md README.md`

Expected: no leftover instruction telling the reader to `cd Backend-API` before running `docker compose up` for the full stack. (References to `cd Backend-API` for the *local, non-Docker* workflow are fine and expected to remain.)

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md Backend-API/Readme.md README.md
git commit -m "docs: document the Docker-first workflow after moving docker-compose.yml to repo root"
```

---

## Post-plan note

`Backend-API/CLAUDE.md` (the session-history file, not the repo-root `CLAUDE.md`) is a running log of past sessions and is normally appended to at the end of a work session summarizing what changed — that's a documentation habit visible in its existing content, not a scripted step here. Consider appending a short entry there once this plan is fully executed and verified, following the existing format of prior dated entries.

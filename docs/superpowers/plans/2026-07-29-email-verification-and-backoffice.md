# Patient Email Verification + Admin Back-Office Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real email verification to patient registration (register → confirmation email → click link → log in; login blocked until confirmed), add a login link to the existing doctor-validation email, and build the admin back-office (login, pending-doctor validation, complaints review with contextual account deletion).

**Architecture:** Backend: one new token table (`EmailVerificationToken`, deliberately separate from `PasswordResetToken`), one new field (`Patient.email_verified`), one new endpoint (`POST /auth/patients/confirm-email`), one new admin read endpoint (`GET /admin/complaints`), and small edits to existing Auth/Admin/Notifications logic. Frontend: no framework, plain HTML/CSS/JS as everywhere else — one new patient-facing page (`confirmer-email.html`), a panel-swap on `inscription-patient.html` (no more auto-login), a 403-specific error on `index.html`, and 4 new pages under a new `frontend/admin/` + `frontend/admin-connexion.html`, all gated by `CarnetAuth.requireAuth('admin')`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, pytest-asyncio; vanilla HTML/CSS/JS reusing `auth.js`/`api.js`/`styles.css` from the existing Auth tranche.

**Specs:** `docs/superpowers/specs/2026-07-29-patient-email-verification.md`, `docs/superpowers/specs/2026-07-29-admin-backoffice.md` — both approved.

---

### Task 1: Backend — data layer for email verification (config, models, migration)

**Files:**
- Modify: `Backend-API/core/config.py`
- Modify: `Backend-API/features/Auth/models.py`
- Create: `Backend-API/alembic/versions/f2a66aa2414c_add_patient_email_verification.py`

- [ ] **Step 1: Add the new config setting**

In `Backend-API/core/config.py`, find:
```python
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    password_reset_token_expire_minutes: int = 30
```
Replace with:
```python
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    password_reset_token_expire_minutes: int = 30
    email_verification_token_expire_minutes: int = 1440
```

- [ ] **Step 2: Add `email_verified` to `Patient` and the new `EmailVerificationToken` model**

In `Backend-API/features/Auth/models.py`, find:
```python
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    blood_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
```
Replace with:
```python
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(default=False)
    blood_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
```
(This is inside the `Patient` class — `Doctor` also has a `password_hash` line but its surrounding context, the `specialty` column right after, is different, so this `old_string` only matches the `Patient` class. Read the file first to confirm before editing if anything looks different.)

Then, at the very end of the same file, after the `PasswordResetToken` class, add:
```python


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_type: Mapped[UserType] = mapped_column(Enum(UserType))
    user_id: Mapped[int]
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 3: Verify the module still imports cleanly**

Run: `cd Backend-API && python -c "import features.Auth.models"` (use whichever Python has the project's deps — the committed `.venv` if it runs on this OS, or a scratch venv per the project's established pattern if not; `uv run python -c "import features.Auth.models"` from `Backend-API/` is the normal path).
Expected: no output, exit code 0.

- [ ] **Step 4: Write the Alembic migration**

Create `Backend-API/alembic/versions/f2a66aa2414c_add_patient_email_verification.py`:

```python
"""add patient email verification

Revision ID: f2a66aa2414c
Revises: 0861d4fe9f97
Create Date: 2026-07-29 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f2a66aa2414c"
down_revision: Union[str, Sequence[str], None] = "0861d4fe9f97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "patients", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false())
    )

    # user_type reuses the existing "usertype" Postgres enum (created by the initial
    # migration for password_reset_tokens) — create_type=False so this migration
    # doesn't try to CREATE TYPE usertype a second time and fail.
    usertype_enum = postgresql.ENUM("PATIENT", "DOCTOR", "ADMIN", name="usertype", create_type=False)
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_type", usertype_enum, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_verification_tokens_token"), "email_verification_tokens", ["token"], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_email_verification_tokens_token"), table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_column("patients", "email_verified")
```

- [ ] **Step 5: Apply the migration against the real Postgres instance**

Run: `cd Backend-API && uv run alembic upgrade head` (or via whatever Python/venv actually has `alembic`+`asyncpg` installed and a reachable `DATABASE_URL` — this project's `.env` already points at a real Postgres; if `uv run` doesn't resolve in this environment, connect directly with a small `asyncpg`/`alembic` script the same way earlier migrations in this project were verified).
Expected: migration runs without error; confirm afterward that `patients.email_verified` exists and defaults to `false`, and that `email_verification_tokens` exists, e.g.:
```sql
SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name = 'patients' AND column_name = 'email_verified';
SELECT to_regclass('email_verification_tokens');
```
Also confirm existing patient rows were NOT affected/lost (row count and their other columns unchanged) — this is an additive `ADD COLUMN` with a server default, so it should apply cleanly to any existing rows.

- [ ] **Step 6: Commit**

```bash
git add Backend-API/core/config.py Backend-API/features/Auth/models.py Backend-API/alembic/versions/f2a66aa2414c_add_patient_email_verification.py
git commit -m "feat: add patient email_verified field and verification token table"
```

## Context

This is Task 1 of a plan implementing two things together: (1) patient email verification
(register no longer auto-logs-in; must click a confirmation link before login works) and
(2) an admin back-office (login, doctor validation, complaints, contextual deletion).
This task only lays the data-layer foundation for part (1) — no behavior changes yet
(nothing reads/writes `email_verified` or `EmailVerificationToken` until Task 3). The
`EmailVerificationToken` table is deliberately separate from the existing
`PasswordResetToken` table — reusing one polymorphic table for both purposes would mean a
confirmation-email token could potentially be replayed against the password-reset
endpoint, which would be a real security regression.

The project already has one prior migration in this branch's history
(`0861d4fe9f97_rename_gender_enum_values_to_french.py`) that renamed the `Gender` Postgres
enum in place — that's the current migration head, hence `down_revision = "0861d4fe9f97"`
here. A live Postgres instance (via `docker-compose.yml`, creds `medical_practice`/`medical_practice`,
database `medical_practice`, port 5432) is what this project runs against in dev — some
earlier tasks in this session found the committed `Backend-API/.venv` doesn't run on this
Windows machine (it was built on Linux/WSL) and had to build a fresh venv via `uv venv` +
`uv pip install -r requirements-dev.txt` in a scratch location; do the same if needed.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

Read `Backend-API/features/Auth/models.py` in full before editing — confirm the `Patient`
class's `password_hash`/`blood_type` lines match what's shown above exactly (this file has
been edited by prior tasks in this session, e.g. the `Gender` enum rename, so re-verify
rather than assuming). If anything differs, ask before proceeding.

## Your Job

1. Implement exactly what's specified
2. Verify per the steps above (import check, then a real migration run against the live DB with before/after data preserved)
3. Commit
4. Self-review
5. Report back

## Code Organization

Only touch the three files listed. Don't modify `Auth/logic.py`, `Auth/routes.py`, `Auth/schemas.py`, or `Notifications/*` — those are later tasks.

## When You're in Over Your Head

If the migration fails (e.g. the `usertype` enum name/values don't match what's in the live DB, or the DB is unreachable), stop and report BLOCKED with the exact error rather than guessing a fix.

## Before Reporting Back: Self-Review

- Completeness: config setting added, `Patient.email_verified` added in the right class, `EmailVerificationToken` model added, migration created and applied.
- Quality: migration's `create_type=False` detail present (a very common Alembic footgun otherwise).
- Discipline: no behavior changes, no other files touched.
- Testing: confirmed via direct DB query that the column/table exist and existing data survived.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- What you verified (import check + live migration run, with the actual query output showing the column/table exist and data preserved)
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 2: Backend — Notifications templates and logic (confirmation email + doctor validation link)

**Files:**
- Modify: `Backend-API/features/Notifications/templates.py`
- Modify: `Backend-API/features/Notifications/logic.py`

- [ ] **Step 1: Replace `templates.py`'s content**

Read `Backend-API/features/Notifications/templates.py` first to confirm its current exact
content matches what's shown below (it should be unchanged since the start of this
session). Replace the whole file with:

```python
"""HTML email templates for transactional notifications sent via Resend."""


def patient_confirm_email_email(first_name: str, confirm_link: str) -> str:
    return (
        f"<p>Bonjour {first_name},</p>"
        f"<p>Merci de votre inscription sur Carnet+. Veuillez confirmer votre adresse email "
        f'en cliquant sur le lien ci-dessous :</p><p><a href="{confirm_link}">{confirm_link}</a></p>'
    )


def new_doctor_request_admin_email(doctor_full_name: str) -> str:
    return f"<p>A new doctor account request from {doctor_full_name} is awaiting validation.</p>"


def doctor_validated_email(first_name: str, login_link: str) -> str:
    return (
        f"<p>Bonjour Dr {first_name},</p>"
        f"<p>Votre compte a été validé. Vous pouvez maintenant vous connecter.</p>"
        f'<p><a href="{login_link}">{login_link}</a></p>'
    )


def doctor_rejected_email(first_name: str, reason: str) -> str:
    return f"<p>Hello Dr. {first_name},</p><p>Your account request was rejected: {reason}</p>"


def doctor_suspended_email(first_name: str, suspended_until: str) -> str:
    return (
        f"<p>Hello Dr. {first_name},</p>"
        f"<p>Your account has been suspended following multiple patient complaints, "
        f"until {suspended_until}.</p>"
    )


def password_reset_email(reset_link: str) -> str:
    return f'<p>Click the link below to reset your password:</p><p><a href="{reset_link}">{reset_link}</a></p>'
```

Note: `welcome_patient_email` is removed (no longer called by anything after Task 3).
`new_doctor_request_admin_email`, `doctor_rejected_email`, `doctor_suspended_email`,
`password_reset_email` are untouched — left in English, out of scope for this plan.

- [ ] **Step 2: Replace `logic.py`'s content**

Read `Backend-API/features/Notifications/logic.py` first to confirm its current content.
Replace the whole file with:

```python
"""Thin wrappers tying email templates to core.email.send_email.

Called from Auth/Admin logic at the relevant account lifecycle events.
"""

from core.email import send_email
from features.Notifications import templates


def notify_patient_confirm_email(to: str, first_name: str, confirm_link: str) -> None:
    send_email(to, "Confirmez votre adresse email", templates.patient_confirm_email_email(first_name, confirm_link))


def notify_admin_new_doctor_request(admin_email: str, doctor_full_name: str) -> None:
    send_email(
        admin_email, "New doctor validation request", templates.new_doctor_request_admin_email(doctor_full_name)
    )


def notify_doctor_validated(to: str, first_name: str, login_link: str) -> None:
    send_email(to, "Votre compte a été validé", templates.doctor_validated_email(first_name, login_link))


def notify_doctor_rejected(to: str, first_name: str, reason: str) -> None:
    send_email(to, "Your account request was rejected", templates.doctor_rejected_email(first_name, reason))


def notify_doctor_suspended(to: str, first_name: str, suspended_until: str) -> None:
    send_email(to, "Your account has been suspended", templates.doctor_suspended_email(first_name, suspended_until))


def notify_password_reset(to: str, reset_link: str) -> None:
    send_email(to, "Reset your password", templates.password_reset_email(reset_link))
```

- [ ] **Step 3: Verify the module imports cleanly**

Run: `cd Backend-API && uv run python -c "import features.Notifications.logic"` (adjust to whichever venv resolves — see Task 1's note).
Expected: no output, exit 0. This will NOT yet catch the fact that `notify_patient_welcome`
and the old 1-arg `notify_doctor_validated` are still called elsewhere with the old
signature — `Auth/logic.py` (calls `notify_patient_welcome`) and `Admin/logic.py` (calls
`notify_doctor_validated` with 2 args) still reference the old names/arities until Tasks 3
and 4 update them. That's expected and fine — those two files are out of scope for this
task; don't touch them here. The whole test suite will NOT pass yet after this task alone
(it will fail at collection/runtime wherever `notify_patient_welcome` or the 2-arg
`notify_doctor_validated` call happens) — that's expected until Tasks 3 and 4 land; don't
try to fix it from this task.

- [ ] **Step 4: Commit**

```bash
git add Backend-API/features/Notifications/templates.py Backend-API/features/Notifications/logic.py
git commit -m "feat: add patient confirmation email template, add link to doctor validation email"
```

## Context

This is Task 2 of the same plan as Task 1 (patient email verification + admin
back-office). It only touches the `Notifications` feature — the email *content* layer.
The callers (`Auth/logic.py`'s `register_patient`, `Admin/logic.py`'s
`validate_doctor_account`) are updated in Tasks 3 and 4, which will break if this task
isn't done first (they'll call functions with the new signatures). This ordering
dependency is intentional — Task 1 → Task 2 → Task 3 → Task 4 must land in that order.

Per the approved specs, all *new* or *modified* templates are written in French
(`patient_confirm_email_email`, `doctor_validated_email`) to match the rest of the
product's user-facing language; templates this plan doesn't touch stay in English as
they already were — not this plan's job to translate everything.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

If the current file content differs from what's assumed above, stop and ask rather than
guessing how to reconcile it.

## Your Job

1. Implement exactly what's specified
2. Verify per Step 3 (import check only — full-suite green is not expected yet)
3. Commit
4. Self-review
5. Report back

## Code Organization

Only touch the two `Notifications` files. Do not touch `Auth/*` or `Admin/*` even though
you'll notice they now call these functions with stale signatures — that's Tasks 3/4.

## When You're in Over Your Head

If you're unsure whether a failure you're seeing is the "expected, not yet fixed" kind
described in Step 3, report DONE_WITH_CONCERNS with the exact error rather than guessing.

## Before Reporting Back: Self-Review

- Completeness: both files replaced exactly as specified.
- Quality: no leftover reference to `welcome_patient_email` anywhere in these two files.
- Discipline: didn't touch `Auth/logic.py` or `Admin/logic.py` even though they now have stale calls.
- Testing: confirmed both files import cleanly in isolation.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- What you verified
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 3: Backend — Auth logic, schemas, routes (confirm-email endpoint + login gate) and test updates

**Files:**
- Modify: `Backend-API/features/Auth/schemas.py`
- Modify: `Backend-API/features/Auth/routes.py`
- Modify: `Backend-API/features/Auth/logic.py`
- Modify: `Backend-API/tests/conftest.py`
- Modify: `Backend-API/tests/test_smoke.py`

- [ ] **Step 1: Add `ConfirmEmailRequest` schema**

Read `Backend-API/features/Auth/schemas.py` first. Find the end of the file:
```python
class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10)
    new_password_confirmation: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.new_password_confirmation:
            raise ValueError("new_password and new_password_confirmation must match")
        return self
```
Add right after it (end of file):
```python


class ConfirmEmailRequest(BaseModel):
    token: str
```

- [ ] **Step 2: Add the confirm-email route**

Read `Backend-API/features/Auth/routes.py` first. In the schema import block, find:
```python
from features.Auth.schemas import (
    DoctorRegisterRequest,
    DoctorRegisterResponse,
    ForgotPasswordRequest,
    LoginRequest,
    PatientOut,
    PatientRegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
```
Replace with:
```python
from features.Auth.schemas import (
    ConfirmEmailRequest,
    DoctorRegisterRequest,
    DoctorRegisterResponse,
    ForgotPasswordRequest,
    LoginRequest,
    PatientOut,
    PatientRegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
```
Then find the end of the file:
```python
@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await logic.reset_password(db, data.token, data.new_password)
    return {"status": "password updated"}
```
Add right after it:
```python


@router.post("/patients/confirm-email")
async def confirm_patient_email(data: ConfirmEmailRequest, db: AsyncSession = Depends(get_db)):
    await logic.confirm_patient_email(db, data.token)
    return {"status": "email confirmed"}
```

- [ ] **Step 3: Update `Auth/logic.py` — imports, register_patient, new confirm_patient_email, login gate**

Read `Backend-API/features/Auth/logic.py` first (it was fully read during planning; confirm
it still matches). Find:
```python
from features.Auth.models import (
    DOCTOR_LOGIN_ALLOWED_STATUSES,
    Admin,
    Doctor,
    Patient,
    PatientStatus,
    PasswordResetToken,
    UserType,
)
```
Replace with:
```python
from features.Auth.models import (
    DOCTOR_LOGIN_ALLOWED_STATUSES,
    Admin,
    Doctor,
    EmailVerificationToken,
    Patient,
    PatientStatus,
    PasswordResetToken,
    UserType,
)
```

Find:
```python
_PASSWORD_RESET_TOKEN_BYTES = 32
```
Replace with:
```python
_PASSWORD_RESET_TOKEN_BYTES = 32
_EMAIL_VERIFICATION_TOKEN_BYTES = 32
```

Find:
```python
    db.add(patient)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from exc
    await db.refresh(patient)

    background_tasks.add_task(notifications.notify_patient_welcome, patient.email, patient.first_name)
    return patient
```
Replace with:
```python
    db.add(patient)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from exc
    await db.refresh(patient)

    token = secrets.token_urlsafe(_EMAIL_VERIFICATION_TOKEN_BYTES)
    db.add(
        EmailVerificationToken(
            user_type=UserType.PATIENT,
            user_id=patient.id,
            token=token,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.email_verification_token_expire_minutes),
        )
    )
    await db.commit()

    confirm_link = f"{settings.frontend_base_url}/confirmer-email.html?token={token}"
    background_tasks.add_task(notifications.notify_patient_confirm_email, patient.email, patient.first_name, confirm_link)
    return patient
```

Find:
```python
async def authenticate_patient(db: AsyncSession, email: str, password: str) -> Patient:
    patient = (await db.scalars(select(Patient).where(Patient.email == email))).first()
    if (
        patient is None
        or patient.status != PatientStatus.ACTIVE
        or not verify_password(password, patient.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return patient
```
Replace with:
```python
async def authenticate_patient(db: AsyncSession, email: str, password: str) -> Patient:
    patient = (await db.scalars(select(Patient).where(Patient.email == email))).first()
    if (
        patient is None
        or patient.status != PatientStatus.ACTIVE
        or not verify_password(password, patient.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not patient.email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Veuillez confirmer votre adresse email avant de vous connecter."
        )
    return patient
```

Finally, add the new `confirm_patient_email` function at the end of the file (after
`reset_password`):
```python


async def confirm_patient_email(db: AsyncSession, token: str) -> None:
    verification_token = (
        await db.scalars(select(EmailVerificationToken).where(EmailVerificationToken.token == token))
    ).first()
    if (
        verification_token is None
        or verification_token.used
        or _is_expired(verification_token.expires_at)
        or verification_token.user_type != UserType.PATIENT
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired confirmation token")

    patient = await db.get(Patient, verification_token.user_id)
    if patient is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired confirmation token")

    patient.email_verified = True
    verification_token.used = True
    await db.commit()
```

- [ ] **Step 4: Update `tests/conftest.py` to simulate email confirmation before login**

Read `Backend-API/tests/conftest.py` first. Find:
```python
from features.Auth.models import Admin  # noqa: E402
```
Replace with:
```python
from features.Auth.models import Admin, EmailVerificationToken  # noqa: E402
```

Find (near the top, in the block of stdlib/third-party imports):
```python
from httpx import ASGITransport, AsyncClient  # noqa: E402
```
Replace with:
```python
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
```

Find:
```python
async def register_and_login_patient(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/patients/register", json=_patient_payload(email))
    assert resp.status_code == 201, resp.text
    patient_id = resp.json()["id"]
    login = await client.post("/auth/patients/login", json={"email": email, "password": "supersecret1"})
    assert login.status_code == 200, login.text
    return {"id": patient_id, "token": login.json()["access_token"], "email": email}
```
Replace with:
```python
async def register_and_login_patient(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/patients/register", json=_patient_payload(email))
    assert resp.status_code == 201, resp.text
    patient_id = resp.json()["id"]

    async with async_session_factory() as session:
        token_row = (
            await session.scalars(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == patient_id)
            )
        ).first()
    confirm = await client.post("/auth/patients/confirm-email", json={"token": token_row.token})
    assert confirm.status_code == 200, confirm.text

    login = await client.post("/auth/patients/login", json={"email": email, "password": "supersecret1"})
    assert login.status_code == 200, login.text
    return {"id": patient_id, "token": login.json()["access_token"], "email": email}
```
(`async_session_factory` is already imported in this file — used by the `client` fixture
and `admin_token` fixture right below.)

- [ ] **Step 5: Add new tests to `tests/test_smoke.py`**

Read `Backend-API/tests/test_smoke.py` first. Append these three tests at the end of the file:
```python


async def test_unverified_patient_cannot_login(client):
    from tests.conftest import _patient_payload

    email = "unverified@example.com"
    resp = await client.post("/auth/patients/register", json=_patient_payload(email))
    assert resp.status_code == 201

    login = await client.post("/auth/patients/login", json={"email": email, "password": "supersecret1"})
    assert login.status_code == 403


async def test_confirm_email_then_login_succeeds(client):
    from sqlalchemy import select

    from core.database import async_session_factory
    from features.Auth.models import EmailVerificationToken
    from tests.conftest import _patient_payload

    email = "confirmable@example.com"
    resp = await client.post("/auth/patients/register", json=_patient_payload(email))
    assert resp.status_code == 201
    patient_id = resp.json()["id"]

    async with async_session_factory() as session:
        token_row = (
            await session.scalars(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == patient_id)
            )
        ).first()

    confirm = await client.post("/auth/patients/confirm-email", json={"token": token_row.token})
    assert confirm.status_code == 200

    login = await client.post("/auth/patients/login", json={"email": email, "password": "supersecret1"})
    assert login.status_code == 200


async def test_confirm_email_invalid_token_returns_400(client):
    resp = await client.post("/auth/patients/confirm-email", json={"token": "not-a-real-token"})
    assert resp.status_code == 400


async def test_register_patient_sends_confirmation_link(client, monkeypatch):
    import features.Notifications.logic as notifications
    from tests.conftest import _patient_payload

    captured = {}

    def fake_send_email(to, subject, html):
        captured["to"] = to
        captured["html"] = html

    monkeypatch.setattr(notifications, "send_email", fake_send_email)

    email = "confirm-link-check@example.com"
    resp = await client.post("/auth/patients/register", json=_patient_payload(email))
    assert resp.status_code == 201

    assert captured["to"] == email
    assert "confirmer-email.html?token=" in captured["html"]
```

- [ ] **Step 6: Run the full backend test suite**

Run: `cd Backend-API && uv run pytest -q` (or via whichever venv resolves in this environment).
Expected: all tests pass, including the 4 new ones above and every existing test that
depends on `register_and_login_patient` (which is most of the suite — `test_smoke.py`,
and via the `patient`/`completed_appointment` fixtures, `test_appointments_flow.py`,
`test_prescriptions_and_carnet.py`, `test_moderation.py`, `test_chronic_care.py`). If
anything other than these new tests fails, that's a real regression from this task — investigate and fix
before moving on. Note: at this point `Admin/logic.py` still calls `notify_doctor_validated`
with the OLD 2-argument signature (Task 4 fixes this) — this WILL cause a `TypeError` at
runtime for any test that exercises `validate_doctor_account` (e.g. inside the
`validated_doctor` fixture, used by `test_appointments_flow.py`,
`test_prescriptions_and_carnet.py`, some of `test_moderation.py`, `test_chronic_care.py`).
This is expected and will be fixed by Task 4 — if you see failures specifically inside
`validate_doctor_account`/`notify_doctor_validated` with a `TypeError` about argument
count, note it in your report as an expected, not-yet-fixed gap (do NOT fix `Admin/logic.py`
from this task — that's Task 4's job, keep the tasks' diffs clean and separable). Report
the exact pass/fail breakdown so the controller can confirm the failure set matches this
expectation exactly.

- [ ] **Step 7: Commit**

```bash
git add Backend-API/features/Auth/schemas.py Backend-API/features/Auth/routes.py Backend-API/features/Auth/logic.py Backend-API/tests/conftest.py Backend-API/tests/test_smoke.py
git commit -m "feat: add patient email confirmation endpoint and login gate"
```

## Context

This is Task 3 of the plan (after Task 1's data layer and Task 2's email content layer).
It wires the actual behavior: registration now creates an unverified patient and sends a
confirmation-link email instead of a welcome email; a new endpoint lets the frontend
(Task 6) confirm that link; login now refuses unverified patients. The credential check
happens BEFORE the verified check in `authenticate_patient` — this ordering matters: it
means a wrong password still returns a generic 401 regardless of verification status, so
an attacker probing an email address can't distinguish "wrong password" from "right
password but unverified" without already knowing the correct password.

This task is expected to leave the suite in a known-broken state for anything that
exercises doctor validation, purely because Task 2 already changed `notify_doctor_validated`'s
signature but Task 4 (not yet done) hasn't updated its one caller in `Admin/logic.py` yet.
This is intentional sequencing, not a mistake — don't try to fix `Admin/logic.py` here.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

Read all five files first and confirm their content matches what's assumed in each step
above (some were read fully during planning, `test_smoke.py` and `conftest.py` mostly but
not 100% verbatim re-confirmed this session — re-check before editing). Ask if anything
differs meaningfully.

## Your Job

1. Implement exactly what's specified
2. Run the full suite and report the EXACT pass/fail breakdown (per Step 6's expectation)
3. Commit
4. Self-review
5. Report back

## Code Organization

Touch exactly the five files listed. Do not touch `Admin/logic.py` (Task 4) or any frontend file (later tasks).

## When You're in Over Your Head

If the test failures don't match the expected pattern (only doctor-validation-related
`TypeError`s), or something else breaks, stop and report BLOCKED or DONE_WITH_CONCERNS
with the exact failure output rather than guessing a fix outside this task's scope.

## Before Reporting Back: Self-Review

- Completeness: schema, route, logic changes, conftest update, and all 4 new tests present exactly as specified.
- Quality: `confirm_patient_email` mirrors `reset_password`'s existing style/error handling closely.
- Discipline: credential check before verified-check in `authenticate_patient` (ordering matters for the reason explained above) — did not reorder or simplify it.
- Testing: ran the full suite, captured the exact failure set, confirmed it matches only the expected (Task-4-pending) gap.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- Full test run output/summary (pass count, and the exact list of any failures with a one-line diagnosis each)
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 4: Backend — wire the login link into the doctor validation email

**Files:**
- Modify: `Backend-API/features/Admin/logic.py`

- [ ] **Step 1: Add the `settings` import and update `validate_doctor_account`**

Read `Backend-API/features/Admin/logic.py` first. Find:
```python
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_file_url
```
Replace with:
```python
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.storage import get_file_url
```

Find:
```python
async def validate_doctor_account(
    db: AsyncSession, doctor_id: int, background_tasks: BackgroundTasks
) -> Doctor:
    doctor = await _get_pending_doctor(db, doctor_id)
    doctor.status = DoctorStatus.VALIDATED
    await db.commit()
    await db.refresh(doctor)
    background_tasks.add_task(notifications.notify_doctor_validated, doctor.email, doctor.first_name)
    return doctor
```
Replace with:
```python
async def validate_doctor_account(
    db: AsyncSession, doctor_id: int, background_tasks: BackgroundTasks
) -> Doctor:
    doctor = await _get_pending_doctor(db, doctor_id)
    doctor.status = DoctorStatus.VALIDATED
    await db.commit()
    await db.refresh(doctor)
    login_link = f"{settings.frontend_base_url}/index.html"
    background_tasks.add_task(notifications.notify_doctor_validated, doctor.email, doctor.first_name, login_link)
    return doctor
```

- [ ] **Step 2: Add a test verifying the email contains the login link**

Read `Backend-API/tests/test_moderation.py` first (to confirm the fixture/import style
used there matches what's assumed below). Append this test at the end of the file:
```python


async def test_validate_doctor_sends_email_with_login_link(client, admin_token, monkeypatch):
    import features.Notifications.logic as notifications
    from tests.conftest import _auth, _doctor_payload

    email = "link-check-doctor@example.com"
    reg = await client.post("/auth/doctors/register", json=_doctor_payload(email))
    assert reg.status_code == 201, reg.text
    doctor_id = reg.json()["id"]

    login = await client.post("/auth/doctors/login", json={"email": email, "password": "diagnostics1"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    diploma = await client.post(
        "/auth/doctors/me/diploma",
        files={"diploma_file": ("diploma.pdf", b"%PDF-fake", "application/pdf")},
        headers=_auth(token),
    )
    assert diploma.status_code == 200, diploma.text

    captured = {}

    def fake_send_email(to, subject, html):
        captured["to"] = to
        captured["html"] = html

    monkeypatch.setattr(notifications, "send_email", fake_send_email)

    decision = await client.post(
        f"/admin/doctors/{doctor_id}/validate",
        json={"approve": True},
        headers=_auth(admin_token),
    )
    assert decision.status_code == 200, decision.text
    assert captured["to"] == email
    assert "index.html" in captured["html"]
```

- [ ] **Step 3: Run the full backend test suite**

Run: `cd Backend-API && uv run pytest -q`.
Expected: **all tests pass now** — this was the last piece needed to fix the
`notify_doctor_validated` signature mismatch flagged as expected-and-pending in Task 3.
Confirm the total count matches Task 3's suite plus this task's one new test.

- [ ] **Step 4: Commit**

```bash
git add Backend-API/features/Admin/logic.py Backend-API/tests/test_moderation.py
git commit -m "feat: include login link in the doctor validation email"
```

## Context

This is Task 4, the last backend task for the email-verification/notification half of this
plan. It's a small, surgical change: `validate_doctor_account` (the function behind
`POST /admin/doctors/{id}/validate` when `approve: true`) now builds a login link and
passes it to `notify_doctor_validated`, whose signature Task 2 already changed to expect
a third argument. Before this task, every test that goes through doctor validation
(directly or via the `validated_doctor` fixture) was expected to fail with a `TypeError`
— this task is what fixes that, and after it the full suite should be green again.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

Confirm `Admin/logic.py` and `tests/test_moderation.py`'s current content matches what's
assumed (particularly that `core.config` isn't already imported under a different alias,
and that `_doctor_payload`/`_auth` exist in `tests/conftest.py` with those exact names —
they do, per this session's earlier work, but re-verify). Ask if anything differs.

## Your Job

1. Implement exactly what's specified
2. Run the full suite and confirm it's fully green
3. Commit
4. Self-review
5. Report back

## Code Organization

Only touch `Admin/logic.py` and `tests/test_moderation.py`.

## When You're in Over Your Head

If the suite still isn't fully green after this change, or you find a DIFFERENT failure
than the one this task is meant to fix, stop and report BLOCKED with full details.

## Before Reporting Back: Self-Review

- Completeness: import added, function updated, test added.
- Quality: `login_link` construction matches the pattern already used for `reset_link` in `Auth/logic.py` (`f"{settings.frontend_base_url}/..."`).
- Discipline: didn't touch `reject_doctor_account` (out of scope — its email has no link per the approved spec) or anything else in the file.
- Testing: full suite green, count matches expectation.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- Full test run output/summary (should be all green now — give the exact final count)
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 5: Frontend — `inscription-patient.html` (no more auto-login, "check your email" panel)

**Files:**
- Modify: `frontend/inscription-patient.html`

- [ ] **Step 1: Read the file and add a panel id + success panel**

Read `frontend/inscription-patient.html` first. Find the opening of the registration
panel:
```html
        <div class="fade">
          <h2 style="font-size:30px;font-weight:800;letter-spacing:-.02em;margin:0 0 6px;">Vos informations</h2>
```
Replace with:
```html
        <div class="fade" id="register-panel">
          <h2 style="font-size:30px;font-weight:800;letter-spacing:-.02em;margin:0 0 6px;">Vos informations</h2>
```

Then find the closing of that same panel — it's the `</div>` that closes the `.fade` div,
immediately before the closing `</div>` of `.auth__inner`. Find:
```html
        </div>
      </div>
    </div>
  </div>
  <script src="auth.js"></script>
```
Replace with:
```html
        </div>
        <div class="fade hidden" id="register-success" style="text-align:center;">
          <div style="width:84px;height:84px;border-radius:24px;background:var(--amber-bg);display:flex;align-items:center;justify-content:center;margin:0 auto 24px;">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="5" width="18" height="14" rx="2" />
              <path d="m3 7 9 6 9-6" />
            </svg>
          </div>
          <h2 style="font-size:28px;font-weight:800;letter-spacing:-.02em;margin:0 0 12px;">Vérifiez votre boîte mail</h2>
          <p style="color:var(--muted);font-size:15px;line-height:1.6;margin:0 auto 26px;max-width:400px;">Nous avons envoyé un lien de confirmation à <strong id="register-success-email"></strong>. Cliquez dessus pour activer votre compte, puis connectez-vous.</p>
          <a href="index.html" style="text-decoration:none;display:block;">
            <button class="btn btn--primary btn--block">Aller à la connexion</button>
          </a>
        </div>
      </div>
    </div>
  </div>
  <script src="auth.js"></script>
```

- [ ] **Step 2: Replace the submit handler's success path**

Find:
```javascript
        try {
          await apiPost('/auth/patients/register', payload);
          var loginData = await apiPost('/auth/patients/login', { email: email, password: password });
          CarnetAuth.saveSession(loginData.access_token, 'patient');
          window.location.href = 'patient/dashboard.html';
        } catch (err) {
```
Replace with:
```javascript
        try {
          await apiPost('/auth/patients/register', payload);
          document.getElementById('register-success-email').textContent = email;
          document.getElementById('register-panel').classList.add('hidden');
          document.getElementById('register-success').classList.remove('hidden');
        } catch (err) {
```

- [ ] **Step 3: Manual verification**

Confirm well-formedness (tag balance) and that all ids referenced in the script
(`register-panel`, `register-success`, `register-success-email`) exist exactly once in
the markup. If a backend server is reachable, register a fresh test patient through this
page's flow (or via `curl` mimicking the same payload) and confirm: no more automatic
login/redirect happens; instead confirm the panel swap would occur (the `apiPost` call
succeeds with 201). If you have DB/email-capture access (per this session's established
pattern of monkeypatching or reading `Backend-API/.env`/direct Postgres access), confirm
that the created patient row has `email_verified = false`.

- [ ] **Step 4: Commit**

```bash
git add frontend/inscription-patient.html
git commit -m "feat: show check-your-email panel instead of auto-login after patient registration"
```

## Context

This is Task 5, the first frontend task of this plan. It depends on Task 3 being done
(the backend no longer supports the old auto-login-after-register flow meaningfully,
since a freshly registered patient can't log in until they confirm their email — so this
frontend change must land, otherwise users would hit a confusing "email ou mot de passe
incorrect"-shaped error immediately after registering). `frontend/inscription-patient.html`
was last touched in an earlier tranche of this session (Auth wiring) — its exact current
content should still match what's shown here, but re-read it first since several small
follow-up fixes have landed on this file since (gender field values, password show/hide
toggle, country field simplification).

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

Read the file first and confirm the two `old_string` blocks above match exactly (in
particular, the exact wrapping div/closing-tag structure — HTML nesting errors are easy
to introduce with this kind of edit). If either doesn't match verbatim, stop and ask
rather than guessing where to insert things.

## Your Job

1. Implement exactly what's specified
2. Verify per Step 3
3. Commit
4. Self-review
5. Report back

## Code Organization

Only touch this one file.

## When You're in Over Your Head

If the file's actual structure around the panel boundaries doesn't match what's assumed
(e.g. different nesting), stop and report BLOCKED or NEEDS_CONTEXT with the actual content
you found, rather than improvising a different insertion point.

## Before Reporting Back: Self-Review

- Completeness: panel id added, success panel added, script's success path replaced (no more login/redirect).
- Quality: HTML well-formed (tag balance check).
- Discipline: didn't touch the error path (409/generic message) — only the try block's success branch changed.
- Testing: confirmed ids match, confirmed (if backend reachable) that a fresh registration no longer attempts a login call.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- What you verified
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 6: Frontend — `confirmer-email.html` (new page)

**Files:**
- Create: `frontend/confirmer-email.html`

- [ ] **Step 1: Create the page**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Confirmation d'email — Carnet+</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="auth">
    <div class="auth__brand">
      <div class="auth__blob" style="top:-90px;right:-60px;width:340px;height:340px;"></div>
      <div class="auth__blob" style="bottom:60px;right:-40px;width:260px;height:260px;background:rgba(255,255,255,.06);"></div>
      <div class="row" style="gap:13px;position:relative;">
        <div class="logo-mark" style="width:52px;height:52px;">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
            <path d="M2 21c0-3 1.85-5.36 5.08-6" />
          </svg>
        </div>
        <div style="font-size:26px;font-weight:800;letter-spacing:-.02em;">Carnet<span class="brand-accent">+</span>
        </div>
      </div>
      <div style="position:relative;">
        <h1>Votre santé,
          <br>
          <span class="brand-accent">connectée</span> et
          <br>simplifiée.
        </h1>
        <p>Téléconsultation, ordonnances, carnet de santé et suivi médical — tout le cabinet en un seul endroit.</p>
      </div>
      <div style="position:relative;font-size:13px;color:rgba(255,255,255,.7);">© 2026 Carnet+ — Plateforme de santé numérique</div>
    </div>
    <div class="auth__form">
      <div class="auth__inner">
        <div class="fade" id="confirm-loading" style="text-align:center;">
          <p style="color:var(--muted);font-size:15px;">Confirmation de votre email en cours…</p>
        </div>
        <div class="fade hidden" id="confirm-success" style="text-align:center;">
          <div style="width:84px;height:84px;border-radius:24px;background:var(--green-soft);display:flex;align-items:center;justify-content:center;margin:0 auto 24px;">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </div>
          <h2 style="font-size:28px;font-weight:800;letter-spacing:-.02em;margin:0 0 12px;">Email confirmé !</h2>
          <p style="color:var(--muted);font-size:15px;line-height:1.6;margin:0 auto 26px;max-width:360px;">Votre compte est activé. Vous pouvez maintenant vous connecter.</p>
          <a href="index.html" style="text-decoration:none;display:block;">
            <button class="btn btn--primary btn--block">Se connecter</button>
          </a>
        </div>
        <div class="fade hidden" id="confirm-error" style="text-align:center;">
          <div style="width:84px;height:84px;border-radius:24px;background:var(--red-bg);display:flex;align-items:center;justify-content:center;margin:0 auto 24px;">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#e5484d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="9" />
              <path d="M15 9l-6 6M9 9l6 6" />
            </svg>
          </div>
          <h2 style="font-size:28px;font-weight:800;letter-spacing:-.02em;margin:0 0 12px;">Lien invalide ou expiré</h2>
          <p style="color:var(--muted);font-size:15px;line-height:1.6;margin:0 auto 26px;max-width:360px;">Ce lien de confirmation n'est plus valide. Réessayez de vous inscrire ou de vous connecter.</p>
          <a href="index.html" style="text-decoration:none;display:block;">
            <button class="btn btn--ghost" style="width:100%;padding:15px;font-weight:700;font-size:15px;">Retour à la connexion</button>
          </a>
        </div>
      </div>
    </div>
  </div>
  <script src="auth.js"></script>
  <script src="api.js"></script>
  <script src="app.js"></script>
  <script>
    (function () {
      function showPanel(id) {
        ['confirm-loading', 'confirm-success', 'confirm-error'].forEach(function (panelId) {
          document.getElementById(panelId).classList.toggle('hidden', panelId !== id);
        });
      }

      var token = new URLSearchParams(window.location.search).get('token');
      if (!token) {
        showPanel('confirm-error');
        return;
      }

      apiPost('/auth/patients/confirm-email', { token: token })
        .then(function () {
          showPanel('confirm-success');
        })
        .catch(function () {
          showPanel('confirm-error');
        });
    })();
  </script>
</body>
</html>
```

- [ ] **Step 2: Manual verification**

Confirm well-formedness (tag balance) and that `confirm-loading`/`confirm-success`/
`confirm-error` each appear exactly once and match the script. If a backend server is
reachable: register a fresh patient, fetch their real confirmation token from the DB
(`email_verification_tokens` table, most recent row for that patient's `user_id`,
`used = false`), and load `confirmer-email.html?token=<token>` behavior via `curl -X POST
http://localhost:8010/auth/patients/confirm-email -H "Content-Type: application/json" -d
'{"token":"<token>"}'` to confirm the underlying call this page makes returns 200; then
confirm the same call a second time now returns 400 (token already used) — this validates
what the error panel would show on a re-visit/replay. Also confirm
`?token=not-a-real-token` yields 400 via the same curl approach.

- [ ] **Step 3: Commit**

```bash
git add frontend/confirmer-email.html
git commit -m "feat: add email confirmation landing page"
```

## Context

This is Task 6. `confirmer-email.html` is the page a patient lands on after clicking the
link in the confirmation email (built server-side in Task 3 as
`f"{settings.frontend_base_url}/confirmer-email.html?token={token}"`). Unlike
`reinitialiser-mot-de-passe.html` (which requires the user to fill a form), this page acts
immediately on load — no user input needed, matching the spec's description of the flow
("clique sur le lien... la page valide le token automatiquement").

`frontend/auth.js`/`frontend/api.js` (with `apiPost`) already exist and work, from the
earlier Auth tranche in this session — this page reuses them exactly as
`reinitialiser-mot-de-passe.html` does.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

If anything about the panel-swap approach or the DB-token-lookup verification step is
unclear given what tools you actually have access to, ask now.

## Your Job

1. Create the file exactly as specified
2. Verify per Step 2 (adapt the depth of verification to what's actually reachable — code review + the curl-based contract check are the minimum bar, DB token lookup if feasible)
3. Commit
4. Self-review
5. Report back

## Code Organization

Only create this one new file.

## When You're in Over Your Head

If DB access isn't feasible in your environment, don't fabricate results — report exactly
what you could verify (e.g. the invalid-token 400 case, which needs no DB access at all)
and what you couldn't.

## Before Reporting Back: Self-Review

- Completeness: file matches spec exactly.
- Quality: well-formed HTML, panel ids consistent.
- Discipline: no extra features (no resend button, no retry logic — explicitly out of scope per the spec).
- Testing: at minimum, confirmed the invalid-token 400 contract; ideally also a real token's 200-then-400-on-replay round trip.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- What you verified and actual output
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 7: Frontend — `index.html` (403 error message for unverified patients)

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Update the error branch**

Read `frontend/index.html` first. Find:
```javascript
        } catch (err) {
          errorEl.textContent = err.status === 401
            ? 'Email ou mot de passe incorrect.'
            : 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
```
Replace with:
```javascript
        } catch (err) {
          errorEl.textContent = err.status === 401
            ? 'Email ou mot de passe incorrect.'
            : err.status === 403
            ? 'Veuillez confirmer votre adresse email avant de vous connecter.'
            : 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
```

- [ ] **Step 2: Manual verification**

If a backend server is reachable: register a fresh patient (without confirming their
email), then attempt to log in as that patient via `curl -X POST
http://localhost:8010/auth/patients/login -H "Content-Type: application/json" -d
'{"email":"...","password":"..."}'` and confirm the response is `403` with a `detail`
string — this is exactly what the JS's `err.status === 403` branch will react to. Confirm
via code review that the ternary chain is syntactically correct (no dangling
operators) and that the 401/403/generic branches are mutually exclusive.

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat: show a specific error message for unconfirmed patient accounts"
```

## Context

This is Task 7, the last patient-facing frontend task. Task 3 made `authenticate_patient`
raise a 403 for a patient whose `email_verified` is still `false`. Without this change,
such a login attempt would fall into `index.html`'s generic "Une erreur est survenue,
réessayez." branch, which is technically not wrong but far less helpful than telling the
user exactly what to do (check their email).

`frontend/index.html` was last substantially touched in an earlier tranche of this
session — re-read it first, since the exact surrounding code shown here should still
match but re-verify rather than assume.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

Confirm the `old_string` above matches exactly before editing.

## Your Job

1. Implement exactly what's specified
2. Verify per Step 2
3. Commit
4. Self-review
5. Report back

## Code Organization

Only touch this one file, only this one ternary chain.

## When You're in Over Your Head

If the file's current catch block looks different, stop and ask rather than guessing.

## Before Reporting Back: Self-Review

- Completeness: 403 branch added, in the right position (checked before the generic fallback).
- Quality: ternary chain reads correctly, no syntax error.
- Discipline: 401 and generic branches unchanged.
- Testing: confirmed the real backend 403 response shape if reachable.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- What you verified and actual output
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 8: Backend — `GET /admin/complaints` endpoint

**Files:**
- Modify: `Backend-API/features/Admin/schemas.py`
- Modify: `Backend-API/features/Admin/logic.py`
- Modify: `Backend-API/features/Admin/routes.py`
- Test: `Backend-API/tests/test_moderation.py`

- [ ] **Step 1: Add the `ComplaintOut` schema**

Read `Backend-API/features/Admin/schemas.py` first. Add at the very end of the file:
```python


class ComplaintOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    doctor_id: int
    doctor_name: str
    doctor_status: str
    reason: str
    description: str
    status: str
    created_at: datetime
```
This needs a new import at the top of the file — find:
```python
from pydantic import BaseModel, EmailStr, Field
```
Replace with:
```python
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field
```

- [ ] **Step 2: Add `list_complaints` logic**

Read `Backend-API/features/Admin/logic.py` first (note: Task 4 already added a
`from core.config import settings` import to this file — confirm it's present). Find:
```python
from features.Admin.models import Complaint, ComplaintStatus, Review
from features.Admin.schemas import ComplaintCreateRequest, PendingDoctorOut, ReviewCreateRequest
from features.Appointments.models import Appointment, AppointmentStatus
from features.Auth.models import Doctor, DoctorStatus, Patient, PatientStatus
```
Replace with:
```python
from features.Admin.models import Complaint, ComplaintStatus, Review
from features.Admin.schemas import ComplaintCreateRequest, ComplaintOut, PendingDoctorOut, ReviewCreateRequest
from features.Appointments.models import Appointment, AppointmentStatus
from features.Auth.models import Doctor, DoctorStatus, Patient, PatientStatus
```

Then add this new function right after `list_pending_doctors` (before `_get_pending_doctor`):
```python


async def list_complaints(db: AsyncSession) -> list[ComplaintOut]:
    rows = (
        await db.execute(
            select(Complaint, Patient, Doctor)
            .join(Patient, Complaint.patient_id == Patient.id)
            .join(Doctor, Complaint.doctor_id == Doctor.id)
            .order_by(Complaint.created_at.desc())
        )
    ).all()
    return [
        ComplaintOut(
            id=complaint.id,
            patient_id=complaint.patient_id,
            patient_name=f"{patient.first_name} {patient.last_name}",
            doctor_id=complaint.doctor_id,
            doctor_name=f"{doctor.first_name} {doctor.last_name}",
            doctor_status=doctor.status.value,
            reason=complaint.reason,
            description=complaint.description,
            status=complaint.status.value,
            created_at=complaint.created_at,
        )
        for complaint, patient, doctor in rows
    ]
```

- [ ] **Step 3: Add the route**

Read `Backend-API/features/Admin/routes.py` first. Find:
```python
from features.Admin.schemas import (
    AccountDeletionRequest,
    ComplaintCreateRequest,
    DoctorValidationDecision,
    PendingDoctorOut,
    ReviewCreateRequest,
)
```
Replace with:
```python
from features.Admin.schemas import (
    AccountDeletionRequest,
    ComplaintCreateRequest,
    ComplaintOut,
    DoctorValidationDecision,
    PendingDoctorOut,
    ReviewCreateRequest,
)
```

Find:
```python
@router.get("/doctors/pending", response_model=list[PendingDoctorOut])
async def list_pending_doctors(
    _admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_pending_doctors(db)
```
Add right after it:
```python


@router.get("/complaints", response_model=list[ComplaintOut])
async def list_complaints(
    _admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_complaints(db)
```

- [ ] **Step 4: Add a test**

Read `Backend-API/tests/test_moderation.py` first (it should already have the
`test_validate_doctor_sends_email_with_login_link` test from Task 4 at the end). Append
this test:
```python


async def test_admin_lists_complaints_with_names_and_doctor_status(
    client, admin_token, patient, validated_doctor
):
    from tests.conftest import _auth

    complaint = await client.post(
        f"/doctors/{validated_doctor['id']}/complaints",
        json={"doctor_id": validated_doctor["id"], "reason": "Retard", "description": "Very late."},
        headers=_auth(patient["token"]),
    )
    assert complaint.status_code == 201, complaint.text

    listing = await client.get("/admin/complaints", headers=_auth(admin_token))
    assert listing.status_code == 200, listing.text
    complaints = listing.json()
    assert len(complaints) == 1
    entry = complaints[0]
    assert entry["patient_id"] == patient["id"]
    assert entry["doctor_id"] == validated_doctor["id"]
    assert entry["reason"] == "Retard"
    assert entry["status"] == "active"
    assert entry["doctor_status"] == "validated"
    assert " " in entry["patient_name"]
    assert " " in entry["doctor_name"]
```

- [ ] **Step 5: Run the full backend test suite**

Run: `cd Backend-API && uv run pytest -q`.
Expected: all tests pass, count increased by 1 versus Task 4's total.

- [ ] **Step 6: Commit**

```bash
git add Backend-API/features/Admin/schemas.py Backend-API/features/Admin/logic.py Backend-API/features/Admin/routes.py Backend-API/tests/test_moderation.py
git commit -m "feat: add GET /admin/complaints endpoint"
```

## Context

This is Task 8, the first backend task for the admin back-office half of this plan
(independent of Tasks 1-7's email-verification work — could technically run in parallel,
but this plan executes tasks sequentially). Nothing currently exposes `Complaint` rows to
an admin — `submit_complaint` (patient-facing, already implemented) only writes them.
`GET /admin/doctors/pending`, `POST /admin/doctors/{id}/validate`,
`DELETE /admin/{user_type}/{user_id}`, and `POST /auth/admin/login` are already fully
implemented and tested from before this session — Tasks 9-12 (frontend) will call those
directly, no backend changes needed for them.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

Read all three backend files and `tests/test_moderation.py` first, confirm the assumed
content (especially that Task 4's `from core.config import settings` import already
landed in `Admin/logic.py` — if this task runs before Task 4 for some reason, that import
won't be there yet; this task doesn't need it itself, just don't be confused by its
presence or absence). Ask if anything differs.

## Your Job

1. Implement exactly what's specified
2. Run the full suite and confirm green
3. Commit
4. Self-review
5. Report back

## Code Organization

Only touch the three Admin files plus the one test file.

## When You're in Over Your Head

If the join query doesn't behave as expected (e.g. `db.execute(select(...))` returning
something other than tuples of ORM instances — confirm via the test, which asserts on
`patient_name`/`doctor_name` containing a space, a cheap sanity check that the join
actually populated real names), stop and report BLOCKED with the exact error.

## Before Reporting Back: Self-Review

- Completeness: schema, logic, route, test all present exactly as specified.
- Quality: follows `list_pending_doctors`'s existing style (same file, same gating pattern).
- Discipline: no filter/pagination query params added (explicitly out of scope per the spec).
- Testing: full suite green, new test passes and actually exercises the join (not just an empty-list happy path).

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- Full test run output/summary
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 9: Frontend — `admin-connexion.html` (new page)

**Files:**
- Create: `frontend/admin-connexion.html`

- [ ] **Step 1: Create the page**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Connexion admin — Carnet+</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="auth">
    <div class="auth__brand">
      <div class="auth__blob" style="top:-90px;right:-60px;width:340px;height:340px;"></div>
      <div class="auth__blob" style="bottom:60px;right:-40px;width:260px;height:260px;background:rgba(255,255,255,.06);"></div>
      <div class="row" style="gap:13px;position:relative;">
        <div class="logo-mark" style="width:52px;height:52px;">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
            <path d="M2 21c0-3 1.85-5.36 5.08-6" />
          </svg>
        </div>
        <div style="font-size:26px;font-weight:800;letter-spacing:-.02em;">Carnet<span class="brand-accent">+</span>
        </div>
      </div>
      <div style="position:relative;">
        <h1>Espace
          <br>
          <span class="brand-accent">administrateur</span>
        </h1>
        <p>Validation des comptes médecin, suivi des réclamations et modération.</p>
      </div>
      <div style="position:relative;font-size:13px;color:rgba(255,255,255,.7);">© 2026 Carnet+ — Plateforme de santé numérique</div>
    </div>
    <div class="auth__form">
      <div class="auth__inner">
        <div class="fade">
          <h2 style="font-size:34px;font-weight:800;letter-spacing:-.02em;margin:0 0 8px;">Connexion admin</h2>
          <p class="subtitle" style="margin-bottom:30px;">Réservé aux administrateurs de la plateforme.</p>
          <div class="card" style="border-radius:20px;padding:28px;box-shadow:var(--sh-form);">
            <form id="admin-login-form">
              <label class="label">ADRESSE EMAIL</label>
              <div class="input-group" style="margin-bottom:20px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="5" width="18" height="14" rx="2" />
                  <path d="m3 7 9 6 9-6" />
                </svg>
                <input type="email" id="admin-login-email" placeholder="admin@carnetplus.com" required>
              </div>
              <label class="label">MOT DE PASSE</label>
              <div class="input-group">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="4" y="10" width="16" height="10" rx="2" />
                  <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                </svg>
                <input type="password" id="admin-login-password" placeholder="Mot de passe" required>
                <button type="button" class="password-toggle" data-toggle-password="admin-login-password" aria-label="Afficher le mot de passe" tabindex="-1">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z" /><circle cx="12" cy="12" r="3" /></svg>
                </button>
              </div>
              <p class="form-error hidden" id="admin-login-error"></p>
              <button type="submit" class="btn btn--primary btn--block" style="margin-top:20px;">Se connecter</button>
            </form>
          </div>
          <div style="text-align:center;margin-top:26px;">
            <a href="index.html" style="font-weight:700;font-size:15px;">← Retour à l'espace patient/médecin</a>
          </div>
        </div>
      </div>
    </div>
  </div>
  <script src="auth.js"></script>
  <script src="api.js"></script>
  <script src="app.js"></script>
  <script>
    (function () {
      document.getElementById('admin-login-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        var errorEl = document.getElementById('admin-login-error');
        errorEl.classList.add('hidden');
        var email = document.getElementById('admin-login-email').value;
        var password = document.getElementById('admin-login-password').value;
        try {
          var data = await apiPost('/auth/admin/login', { email: email, password: password });
          CarnetAuth.saveSession(data.access_token, 'admin');
          window.location.href = 'admin/dashboard.html';
        } catch (err) {
          errorEl.textContent = err.status === 401
            ? 'Email ou mot de passe incorrect.'
            : 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
      });
    })();
  </script>
</body>
</html>
```

- [ ] **Step 2: Manual verification**

Confirm well-formedness and that all referenced ids exist exactly once. If a backend
server is reachable and an admin account exists (per this project's existing
`admin_token`-style test fixture pattern, or a real admin row if one exists in the dev
DB), confirm `POST /auth/admin/login` with correct credentials returns 200 with an
`access_token`, and with wrong credentials returns 401 — matching what this page's script
expects.

- [ ] **Step 3: Commit**

```bash
git add frontend/admin-connexion.html
git commit -m "feat: add admin login page"
```

## Context

This is Task 9, the first frontend task for the admin back-office half of this plan. It's
a near-identical sibling of the existing patient/doctor login flow on `index.html` but
targeting `/auth/admin/login` (already implemented and tested server-side, just never
called by any frontend page before now) and saving the session with role `'admin'`. It
reuses the password show/hide toggle (`data-toggle-password`, wired via a delegated
listener already in `frontend/app.js` from an earlier tranche) exactly like every other
password field in the app.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

If anything about the admin login flow is unclear, ask now.

## Your Job

1. Create the file exactly as specified
2. Verify per Step 2
3. Commit
4. Self-review
5. Report back

## Code Organization

Only create this one new file.

## When You're in Over Your Head

If `/auth/admin/login` doesn't behave as expected when you test it, stop and report
BLOCKED/NEEDS_CONTEXT with the exact response rather than guessing.

## Before Reporting Back: Self-Review

- Completeness: form, ids, script all match spec.
- Quality: consistent with `index.html`'s established login pattern and error handling.
- Discipline: no extra fields (no role tabs — this page is admin-only, unlike `index.html`).
- Testing: confirmed the `/auth/admin/login` contract (200/401) if reachable.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- What you verified and actual output
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 10: Frontend — `admin/dashboard.html` (new page)

**Files:**
- Create: `frontend/admin/dashboard.html`

- [ ] **Step 1: Create the page**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tableau de bord admin — Carnet+</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="sidebar__head">
        <button class="hamburger" data-action="toggle-sidebar" title="Réduire le menu">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>
        <div class="logo-mark" style="width:40px;height:40px;background:linear-gradient(135deg,#13b98a,#0d9488);">
          <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
            <path d="M2 21c0-3 1.85-5.36 5.08-6" />
          </svg>
        </div>
        <div class="sidebar__logo">Carnet<span style="color:var(--green-2);">+</span>
        </div>
      </div>
      <nav class="sidebar__nav">
        <a class="nav-link active" href="dashboard.html">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 10.5 12 3l9 7.5" />
            <path d="M5 9.5V21h14V9.5" />
          </svg>Tableau de bord
        </a>
        <a class="nav-link" href="demandes-medecins.html">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 3v5a5 5 0 0 0 10 0V3" />
            <path d="M10 13v2a6 6 0 0 0 12 0v-2" />
          </svg>Demandes médecins
        </a>
        <a class="nav-link" href="reclamations.html">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 9v4M12 17h.01" />
            <path d="M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0Z" />
          </svg>Réclamations
        </a>
      </nav>
      <div class="sidebar__foot">
        <div class="user-row">
          <div class="avatar avatar-round" style="width:38px;height:38px;background:linear-gradient(135deg,#5b6ef5,#7c3aed);">AD</div>
          <div style="flex:1;min-width:0;">
            <div class="name">Administrateur</div>
          </div>
          <button class="icon-btn" id="logout-btn" title="Se déconnecter" type="button">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
    <button class="hamburger--float" data-action="toggle-sidebar" title="Ouvrir le menu">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 6h18M3 12h18M3 18h18" />
      </svg>
    </button>
    <main class="main">
      <div class="fade container">
        <div class="between mb-22">
          <div>
            <h1 class="h1">Espace admin</h1>
            <p class="subtitle" style="margin:0;">Validation des médecins et suivi des réclamations.</p>
          </div>
        </div>
        <div class="grid-2">
          <a class="tile" href="demandes-medecins.html" style="text-decoration:none;color:inherit;">
            <div class="tile__icon" style="background:#5b6ef5;">
              <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M5 3v5a5 5 0 0 0 10 0V3" />
                <path d="M10 13v2a6 6 0 0 0 12 0v-2" />
              </svg>
            </div>
            <div class="t">Demandes médecins</div>
            <div style="color:var(--muted);font-size:13px;margin-top:4px;"><span id="pending-count">…</span> en attente de validation</div>
          </a>
          <a class="tile" href="reclamations.html" style="text-decoration:none;color:inherit;">
            <div class="tile__icon" style="background:#f59e0b;">
              <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 9v4M12 17h.01" />
                <path d="M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0Z" />
              </svg>
            </div>
            <div class="t">Réclamations</div>
            <div style="color:var(--muted);font-size:13px;margin-top:4px;"><span id="complaints-count">…</span> réclamation(s)</div>
          </a>
        </div>
      </div>
    </main>
  </div>
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('admin');

      document.getElementById('logout-btn').addEventListener('click', function () {
        CarnetAuth.logout();
      });

      apiGet('/admin/doctors/pending')
        .then(function (doctors) {
          document.getElementById('pending-count').textContent = doctors.length;
        })
        .catch(function () {
          document.getElementById('pending-count').textContent = '—';
        });

      apiGet('/admin/complaints')
        .then(function (complaints) {
          document.getElementById('complaints-count').textContent = complaints.length;
        })
        .catch(function () {
          document.getElementById('complaints-count').textContent = '—';
        });
    })();
  </script>
</body>
</html>
```

- [ ] **Step 2: Manual verification**

Confirm well-formedness. If a backend server is reachable with a real admin token: log in
as admin via `curl`, then confirm `GET /admin/doctors/pending` and `GET /admin/complaints`
both work with that token (matching what this page's `apiGet` calls expect) — these were
already exercised by Task 8's tests, so this step is really about confirming the page's
JS calls the right paths, not re-deriving new backend behavior. Confirm
`CarnetAuth.requireAuth('admin')` correctly redirects to `../admin-connexion.html`... note:
`requireAuth` (in `frontend/auth.js`, written in an earlier tranche) redirects to
`/index.html` unconditionally, not to `admin-connexion.html` — this is a real gap this
task's dependency introduces: review `frontend/auth.js`'s `requireAuth` function before
writing this task's script and decide whether it needs a parameter for the redirect
target, or whether redirecting an unauthenticated admin to the patient/doctor login page
is acceptable for this V1 (it is technically safe — just not ideal UX). Flag this
explicitly in your report rather than silently choosing one way.

- [ ] **Step 3: Commit**

```bash
git add frontend/admin/dashboard.html
git commit -m "feat: add admin dashboard with pending-doctor and complaint counts"
```

## Context

This is Task 10. `frontend/admin/dashboard.html` reuses the exact same app-shell markup
pattern (`.app`/`.sidebar`/`.main`, hamburger toggle via `data-action="toggle-sidebar"`
already wired in `app.js`) already used by `frontend/patient/dashboard.html` and
`frontend/medecin/*.html` — read `frontend/patient/dashboard.html` for reference before
implementing this task if the pattern isn't already familiar from earlier tasks in this
session. Note the relative script/stylesheet paths (`../styles.css`, `../auth.js`, etc.)
since this file lives one directory deeper than the root pages.

This is the FIRST page in the whole project to actually call `CarnetAuth.requireAuth(...)`
— it was written during the original Auth tranche but never used, since no protected
page existed until now. Read `frontend/auth.js`'s `requireAuth` implementation before
writing this task, to confirm exactly what it does (redirect target, parameter shape).

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

Read `frontend/auth.js` in full and flag, before writing any code, whether
`requireAuth('admin')`'s current redirect target (likely `/index.html`) is acceptable
for this task or needs adjusting — this affects every one of Tasks 10-12, so raise it
once, here, rather than each task guessing independently.

## Your Job

1. Implement exactly what's specified
2. Verify per Step 2, and explicitly report on the `requireAuth` redirect-target question
3. Commit
4. Self-review
5. Report back

## Code Organization

Create this one new file (and the `frontend/admin/` directory it lives in, if it doesn't exist yet).

## When You're in Over Your Head

If `CarnetAuth.requireAuth` doesn't exist or has a different signature than expected,
stop and report BLOCKED/NEEDS_CONTEXT — don't invent a new session-gating mechanism from
scratch.

## Before Reporting Back: Self-Review

- Completeness: page matches spec, both counts wired.
- Quality: consistent with `patient/dashboard.html`'s established shell pattern.
- Discipline: no extra dashboard content beyond what the spec asks for (no fake stats, no unrelated widgets).
- Testing: confirmed both `apiGet` calls target real, working endpoints.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- The `requireAuth` redirect-target finding (explicit answer, not just "seems fine")
- What you verified and actual output
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 11: Frontend — `admin/demandes-medecins.html` (new page)

**Files:**
- Create: `frontend/admin/demandes-medecins.html`

- [ ] **Step 1: Create the page**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Demandes médecins — Carnet+</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="sidebar__head">
        <button class="hamburger" data-action="toggle-sidebar" title="Réduire le menu">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>
        <div class="logo-mark" style="width:40px;height:40px;background:linear-gradient(135deg,#13b98a,#0d9488);">
          <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
            <path d="M2 21c0-3 1.85-5.36 5.08-6" />
          </svg>
        </div>
        <div class="sidebar__logo">Carnet<span style="color:var(--green-2);">+</span>
        </div>
      </div>
      <nav class="sidebar__nav">
        <a class="nav-link" href="dashboard.html">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 10.5 12 3l9 7.5" />
            <path d="M5 9.5V21h14V9.5" />
          </svg>Tableau de bord
        </a>
        <a class="nav-link active" href="demandes-medecins.html">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 3v5a5 5 0 0 0 10 0V3" />
            <path d="M10 13v2a6 6 0 0 0 12 0v-2" />
          </svg>Demandes médecins
        </a>
        <a class="nav-link" href="reclamations.html">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 9v4M12 17h.01" />
            <path d="M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0Z" />
          </svg>Réclamations
        </a>
      </nav>
      <div class="sidebar__foot">
        <div class="user-row">
          <div class="avatar avatar-round" style="width:38px;height:38px;background:linear-gradient(135deg,#5b6ef5,#7c3aed);">AD</div>
          <div style="flex:1;min-width:0;">
            <div class="name">Administrateur</div>
          </div>
          <button class="icon-btn" id="logout-btn" title="Se déconnecter" type="button">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
    <button class="hamburger--float" data-action="toggle-sidebar" title="Ouvrir le menu">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 6h18M3 12h18M3 18h18" />
      </svg>
    </button>
    <main class="main">
      <div class="fade container">
        <div class="between mb-22">
          <div>
            <h1 class="h1">Demandes médecins</h1>
            <p class="subtitle" style="margin:0;">Comptes en attente de validation.</p>
          </div>
        </div>
        <p class="form-error hidden" id="doctors-error"></p>
        <div class="card card--flush" id="doctors-list"></div>
        <div class="empty hidden" id="doctors-empty">Aucune demande en attente.</div>
      </div>
    </main>
  </div>
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('admin');

      document.getElementById('logout-btn').addEventListener('click', function () {
        CarnetAuth.logout();
      });

      function renderRow(doctor) {
        var row = document.createElement('div');
        row.className = 'list-row';
        row.dataset.doctorId = doctor.id;

        var info = document.createElement('div');
        info.style.flex = '1';
        info.innerHTML =
          '<div style="font-weight:700;font-size:15px;">' + doctor.first_name + ' ' + doctor.last_name + '</div>' +
          '<div style="color:var(--muted);font-size:13px;">' + doctor.specialty + ' · ' + doctor.practice_name + ' · N° ' + doctor.license_number + '</div>' +
          '<div style="color:var(--muted);font-size:13px;">' + doctor.email + '</div>';
        row.appendChild(info);

        if (doctor.diploma_url) {
          var diplomaLink = document.createElement('a');
          diplomaLink.href = doctor.diploma_url;
          diplomaLink.target = '_blank';
          diplomaLink.rel = 'noopener';
          diplomaLink.className = 'btn btn--soft btn--sm';
          diplomaLink.textContent = 'Voir le diplôme';
          diplomaLink.style.marginRight = '8px';
          row.appendChild(diplomaLink);
        }

        var validateBtn = document.createElement('button');
        validateBtn.className = 'btn btn--primary btn--sm';
        validateBtn.textContent = 'Valider';
        validateBtn.style.marginRight = '8px';
        validateBtn.addEventListener('click', function () {
          decide(doctor.id, true, null, row);
        });
        row.appendChild(validateBtn);

        var rejectBtn = document.createElement('button');
        rejectBtn.className = 'btn btn--ghost btn--sm';
        rejectBtn.textContent = 'Rejeter';
        rejectBtn.addEventListener('click', function () {
          var reason = window.prompt('Motif du rejet (optionnel) :', '');
          if (reason === null) return;
          decide(doctor.id, false, reason, row);
        });
        row.appendChild(rejectBtn);

        return row;
      }

      async function decide(doctorId, approve, rejectionReason, row) {
        try {
          await apiPost('/admin/doctors/' + doctorId + '/validate', {
            approve: approve,
            rejection_reason: rejectionReason || null,
          });
          row.remove();
          var list = document.getElementById('doctors-list');
          if (!list.children.length) {
            document.getElementById('doctors-empty').classList.remove('hidden');
          }
        } catch (err) {
          document.getElementById('doctors-error').textContent = 'Une erreur est survenue, réessayez.';
          document.getElementById('doctors-error').classList.remove('hidden');
        }
      }

      apiGet('/admin/doctors/pending')
        .then(function (doctors) {
          var list = document.getElementById('doctors-list');
          if (!doctors.length) {
            document.getElementById('doctors-empty').classList.remove('hidden');
            return;
          }
          doctors.forEach(function (doctor) {
            list.appendChild(renderRow(doctor));
          });
        })
        .catch(function () {
          document.getElementById('doctors-error').textContent = 'Impossible de charger les demandes.';
          document.getElementById('doctors-error').classList.remove('hidden');
        });
    })();
  </script>
</body>
</html>
```

- [ ] **Step 2: Manual verification**

Confirm well-formedness. If a backend server is reachable with a real admin token and at
least one pending doctor (register a fresh test doctor + upload a diploma to create one),
confirm `GET /admin/doctors/pending` returns it and that
`POST /admin/doctors/{id}/validate` with `{"approve": true, "rejection_reason": null}`
(matching this page's exact payload shape) returns 200 — this is the same contract
already covered by Task 8's/earlier session's backend tests, so this is about confirming
the frontend sends the right shape, not re-deriving backend behavior.

- [ ] **Step 3: Commit**

```bash
git add frontend/admin/demandes-medecins.html
git commit -m "feat: add admin page to review and validate/reject pending doctors"
```

## Context

This is Task 11. It lists doctors from `GET /admin/doctors/pending` (already implemented,
returns `PendingDoctorOut[]` — `id, first_name, last_name, email, specialty,
license_number, practice_name, diploma_url`) and lets the admin act via the existing
`POST /admin/doctors/{id}/validate` endpoint (`{approve: bool, rejection_reason: str |
null}`). Rows are built with plain DOM APIs (`createElement`/`appendChild`) rather than
`innerHTML` for the whole row, matching the pattern of trusting-but-controlling dynamic
content — though note `info.innerHTML` IS used for the text block since doctor
names/specialties are plain strings from a trusted backend, not user-supplied HTML in a
context where that matters here (same level of trust already extended elsewhere in this
codebase, e.g. `frontend/patient/dashboard.html`'s static content).

`window.prompt` is used for the optional rejection reason — this is the one place in the
whole app it appears; it's a deliberate, minimal choice (no new modal component needed for
a single optional text field) rather than a full custom UI. If this feels out of place in
review, flag it — not a hard requirement, just the plan's chosen simplest option per YAGNI.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

Confirm `frontend/auth.js`'s `requireAuth` behavior (per Task 10's finding — read that
task's report if it already ran, or re-derive it yourself) before finalizing this page's
guard call.

## Your Job

1. Implement exactly what's specified
2. Verify per Step 2
3. Commit
4. Self-review
5. Report back

## Code Organization

Only create this one new file.

## When You're in Over Your Head

If `PendingDoctorOut`'s actual field names differ from what's assumed here (they
shouldn't — this schema hasn't changed all session — but re-verify against
`Backend-API/features/Admin/schemas.py` before assuming), stop and report NEEDS_CONTEXT.

## Before Reporting Back: Self-Review

- Completeness: list rendering, validate/reject actions, empty state, error state all present.
- Quality: consistent sidebar/shell with Task 10's dashboard page.
- Discipline: no pagination/filtering/search added (out of scope per spec).
- Testing: confirmed the validate/reject payload shape against the real backend contract.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- What you verified and actual output
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 12: Frontend — `admin/reclamations.html` (new page, contextual doctor deletion)

**Files:**
- Create: `frontend/admin/reclamations.html`

- [ ] **Step 1: Create the page**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Réclamations — Carnet+</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="sidebar__head">
        <button class="hamburger" data-action="toggle-sidebar" title="Réduire le menu">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>
        <div class="logo-mark" style="width:40px;height:40px;background:linear-gradient(135deg,#13b98a,#0d9488);">
          <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
            <path d="M2 21c0-3 1.85-5.36 5.08-6" />
          </svg>
        </div>
        <div class="sidebar__logo">Carnet<span style="color:var(--green-2);">+</span>
        </div>
      </div>
      <nav class="sidebar__nav">
        <a class="nav-link" href="dashboard.html">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 10.5 12 3l9 7.5" />
            <path d="M5 9.5V21h14V9.5" />
          </svg>Tableau de bord
        </a>
        <a class="nav-link" href="demandes-medecins.html">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 3v5a5 5 0 0 0 10 0V3" />
            <path d="M10 13v2a6 6 0 0 0 12 0v-2" />
          </svg>Demandes médecins
        </a>
        <a class="nav-link active" href="reclamations.html">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 9v4M12 17h.01" />
            <path d="M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0Z" />
          </svg>Réclamations
        </a>
      </nav>
      <div class="sidebar__foot">
        <div class="user-row">
          <div class="avatar avatar-round" style="width:38px;height:38px;background:linear-gradient(135deg,#5b6ef5,#7c3aed);">AD</div>
          <div style="flex:1;min-width:0;">
            <div class="name">Administrateur</div>
          </div>
          <button class="icon-btn" id="logout-btn" title="Se déconnecter" type="button">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
    <button class="hamburger--float" data-action="toggle-sidebar" title="Ouvrir le menu">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 6h18M3 12h18M3 18h18" />
      </svg>
    </button>
    <main class="main">
      <div class="fade container">
        <div class="between mb-22">
          <div>
            <h1 class="h1">Réclamations</h1>
            <p class="subtitle" style="margin:0;">Signalements de patients contre des médecins.</p>
          </div>
        </div>
        <p class="form-error hidden" id="complaints-error"></p>
        <div class="card card--flush" id="complaints-list"></div>
        <div class="empty hidden" id="complaints-empty">Aucune réclamation.</div>
      </div>
    </main>
  </div>
  <div class="modal__backdrop hidden" id="delete-modal">
    <div class="modal" style="max-width:440px;">
      <div class="row" style="justify-content:space-between;margin-bottom:6px;">
        <div style="font-size:19px;font-weight:800;">Supprimer ce compte médecin</div>
        <button class="modal__close" id="delete-modal-close" type="button">✕</button>
      </div>
      <p style="color:var(--muted);font-size:13.5px;margin:0 0 16px;">Cette action supprime (désactive) le compte du médecin. Indiquez le motif.</p>
      <label class="label">MOTIF</label>
      <textarea class="input" id="delete-reason" style="min-height:80px;margin-bottom:16px;" required></textarea>
      <p class="form-error hidden" id="delete-modal-error"></p>
      <button class="btn btn--primary btn--block" id="delete-confirm-btn" type="button">Confirmer la suppression</button>
    </div>
  </div>
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('admin', '../admin-connexion.html');

      document.getElementById('logout-btn').addEventListener('click', function () {
        CarnetAuth.logout();
      });

      var pendingDeleteDoctorId = null;

      function statusBadge(status) {
        var labels = { validated: 'Actif', suspended: 'Suspendu', pending_validation: 'En attente', rejected: 'Rejeté', deleted: 'Supprimé' };
        var classes = { validated: 'badge--green', suspended: 'badge--amber' };
        var span = document.createElement('span');
        span.className = 'badge ' + (classes[status] || 'badge--muted');
        span.textContent = labels[status] || status;
        return span;
      }

      function renderRow(complaint) {
        var row = document.createElement('div');
        row.className = 'list-row';
        row.dataset.doctorId = complaint.doctor_id;

        var info = document.createElement('div');
        info.style.flex = '1';

        var doctorNameEl = document.createElement('div');
        doctorNameEl.style.fontWeight = '700';
        doctorNameEl.style.fontSize = '15px';
        doctorNameEl.textContent = complaint.doctor_name;
        info.appendChild(doctorNameEl);

        var reasonEl = document.createElement('div');
        reasonEl.style.color = 'var(--muted)';
        reasonEl.style.fontSize = '13px';
        reasonEl.textContent = 'Patient : ' + complaint.patient_name + ' · ' + complaint.reason;
        info.appendChild(reasonEl);

        var descriptionEl = document.createElement('div');
        descriptionEl.style.color = 'var(--muted)';
        descriptionEl.style.fontSize = '13px';
        descriptionEl.textContent = complaint.description;
        info.appendChild(descriptionEl);

        row.appendChild(info);
        row.appendChild(statusBadge(complaint.doctor_status));

        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn--ghost btn--sm';
        deleteBtn.style.marginLeft = '8px';
        deleteBtn.textContent = 'Supprimer ce compte médecin';
        deleteBtn.addEventListener('click', function () {
          pendingDeleteDoctorId = complaint.doctor_id;
          document.getElementById('delete-reason').value = '';
          document.getElementById('delete-modal-error').classList.add('hidden');
          document.getElementById('delete-modal').classList.remove('hidden');
        });
        row.appendChild(deleteBtn);

        return row;
      }

      document.getElementById('delete-modal-close').addEventListener('click', function () {
        document.getElementById('delete-modal').classList.add('hidden');
      });

      document.getElementById('delete-confirm-btn').addEventListener('click', async function () {
        var reason = document.getElementById('delete-reason').value.trim();
        var errorEl = document.getElementById('delete-modal-error');
        if (!reason) {
          errorEl.textContent = 'Le motif est obligatoire.';
          errorEl.classList.remove('hidden');
          return;
        }
        try {
          await apiRequest('DELETE', '/admin/doctors/' + pendingDeleteDoctorId, { json: { reason: reason } });
          document.getElementById('delete-modal').classList.add('hidden');
          var rows = document.querySelectorAll('[data-doctor-id="' + pendingDeleteDoctorId + '"]');
          rows.forEach(function (row) {
            row.remove();
          });
          var list = document.getElementById('complaints-list');
          if (!list.children.length) {
            document.getElementById('complaints-empty').classList.remove('hidden');
          }
        } catch (err) {
          errorEl.textContent = 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
      });

      apiGet('/admin/complaints')
        .then(function (complaints) {
          var list = document.getElementById('complaints-list');
          if (!complaints.length) {
            document.getElementById('complaints-empty').classList.remove('hidden');
            return;
          }
          complaints.forEach(function (complaint) {
            list.appendChild(renderRow(complaint));
          });
        })
        .catch(function () {
          document.getElementById('complaints-error').textContent = 'Impossible de charger les réclamations.';
          document.getElementById('complaints-error').classList.remove('hidden');
        });
    })();
  </script>
</body>
</html>
```

- [ ] **Step 2: Manual verification**

Confirm well-formedness. Note the delete action uses `apiRequest('DELETE', ..., { json:
{...} })` directly rather than `apiPost`/`apiGet` — `frontend/api.js` (from an earlier
tranche) exposes `apiRequest(method, path, options)` as the underlying function beneath
`apiGet`/`apiPost`/`apiPostForm`, but has no `apiDelete` convenience wrapper; using
`apiRequest` directly for the one DELETE call in this codebase is the correct, minimal
choice — don't add a new `apiDelete` wrapper for a single call site. If a backend server
is reachable with a real admin token, a complaint, and a doctor: confirm
`DELETE /admin/doctor/{id}` (singular — the real route is `/admin/{user_type}/{user_id}`,
and `delete_account` compares `user_type` literally against `"patient"`/`"doctor"`) with a
JSON body `{"reason": "..."}` returns 204 (per
`Backend-API/features/Admin/routes.py`'s existing, already-tested implementation) —
this confirms the exact call this page makes actually works end-to-end.

- [ ] **Step 3: Commit**

```bash
git add frontend/admin/reclamations.html
git commit -m "feat: add admin page to review complaints with contextual doctor account deletion"
```

## Context

This is Task 12, the last new admin page. It lists complaints from the `GET
/admin/complaints` endpoint built in Task 8 (`patient_name`, `doctor_name`,
`doctor_status`, `reason`, `description`, `status`, `doctor_id`), and lets the admin
delete a doctor's account directly from a complaint row via the already-existing
`DELETE /admin/{user_type}/{user_id}` endpoint (here always `user_type=doctor`), with a
required reason, via a confirmation modal reusing the `.modal__backdrop`/`.modal` CSS
pattern already established elsewhere in this codebase (e.g.
`frontend/patient/dashboard.html`'s `#rdv-list-modal`, `frontend/choix-compte.html`'s
"Bientôt disponible" modal).

Per the approved spec, this is deliberately the ONLY place account deletion is reachable
from in this tranche — no general patient/doctor search page.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

Read `frontend/api.js` first to confirm `apiRequest`'s exact signature (`method, path,
options` where `options.json`/`options.form`/`options.token` are the supported keys) —
this task's DELETE call depends on getting that call right.

## Your Job

1. Implement exactly what's specified
2. Verify per Step 2
3. Commit
4. Self-review
5. Report back

## Code Organization

Only create this one new file.

## When You're in Over Your Head

If `apiRequest`'s actual signature differs from what's assumed, or the
`DELETE /admin/{user_type}/{user_id}` endpoint's actual request/response shape differs
from what's assumed (re-check `Backend-API/features/Admin/routes.py` and
`Backend-API/features/Admin/schemas.py`'s `AccountDeletionRequest` before assuming), stop
and report NEEDS_CONTEXT.

## Before Reporting Back: Self-Review

- Completeness: list rendering, status badges, delete modal with required-reason validation, all present.
- Quality: consistent sidebar/shell with Tasks 10-11; modal reuses existing CSS classes, no new ones invented.
- Discipline: only doctor deletion is wired (no patient deletion — out of scope per spec); no search/filter added.
- Testing: confirmed the DELETE call's exact contract against the real backend.

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- What you verified and actual output
- Files changed
- Self-review findings
- Any issues or concerns

---

### Task 13: Full end-to-end walkthrough

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite one more time**

Run: `cd Backend-API && uv run pytest -q`.
Expected: all tests pass (should be Task 8's count — this task adds no new backend
tests, just re-confirms nothing regressed from the frontend-only Tasks 9-12).

- [ ] **Step 2: Patient email-verification walkthrough (curl-based, no browser available)**

With a backend server reachable:
1. `POST /auth/patients/register` a fresh patient. Confirm 201, and confirm (via direct
   DB query on `email_verification_tokens` and `patients.email_verified`) that a token
   row was created and the patient's `email_verified` is `false`.
2. `POST /auth/patients/login` with that patient's credentials. Confirm 403.
3. Fetch the real token from the DB, `POST /auth/patients/confirm-email` with it. Confirm
   200, and confirm `patients.email_verified` is now `true` for that row.
4. `POST /auth/patients/login` again with the same credentials. Confirm 200 with an
   `access_token`.
5. `POST /auth/patients/confirm-email` again with the SAME (now-used) token. Confirm 400.
6. Clean up the test patient row and its token row from the DB afterward.

- [ ] **Step 3: Admin back-office walkthrough (curl-based)**

1. `POST /auth/admin/login` with a real admin account (if one exists in the dev DB; if
   not, note this rather than fabricating credentials — this is pre-existing setup, not
   something this plan creates).
2. `GET /admin/doctors/pending` with that token. Confirm 200.
3. `GET /admin/complaints` with that token. Confirm 200.
4. If at least one pending doctor exists (register one via the existing doctor
   registration flow + diploma upload if needed), `POST
   /admin/doctors/{id}/validate` with `{"approve": true}`. Confirm 200 and confirm (via
   monkeypatch-free real DB check, or by re-reading `Backend-API/features/Auth/models.py`'s
   `Doctor.status` for that row) that it's now `validated`.
5. If at least one complaint exists (submit one via the existing patient complaint flow
   against any existing, non-deleted doctor — `submit_complaint` has no appointment
   prerequisite, only an authenticated patient and a live doctor, confirmed during Task
   12), `DELETE /admin/doctor/{id}` (singular) with `{"reason": "test cleanup"}`. Confirm
   204 and that the doctor's status is now `deleted`.
6. Clean up any test rows created for this walkthrough.

- [ ] **Step 4: Confirm no stack-trace leakage**

Trigger at least one error case from each new endpoint (e.g. `POST
/auth/patients/confirm-email` with a garbage token, `GET /admin/complaints` with no
auth header) and confirm the response body is clean JSON/text, never a raw Python
traceback.

- [ ] **Step 5: Commit**

No git repository commit needed for this task (verification only, nothing to add).
Report the final state instead.

## Context

This is Task 13, the last task of this plan — a comprehensive verification pass across
both halves (patient email verification, Tasks 1-7; admin back-office, Tasks 8-12), not
new development. Mirrors the same rigor as the final walkthrough task from the earlier
Auth-wiring plan in this session (`docs/superpowers/plans/2026-07-28-auth-frontend-backend.md`,
its Task 10) — report precisely what works and what's blocked, with root causes, rather
than a pass/fail summary alone.

A git repository exists at `c:\Users\PC\Documents\CarnetPlus`, branch `features/integrations`.
Work from: `c:\Users\PC\Documents\CarnetPlus`.

## Before You Begin

If admin credentials or existing pending-doctor/complaint fixtures aren't available in
the live dev DB, don't fabricate them — report exactly what you could and couldn't
verify, and why.

## Your Job

1. Run the verification steps above
2. Report back precisely — no fixing, no commits (beyond what earlier tasks already committed)
3. Self-review

## When You're in Over Your Head

If you find something that looks like a genuine NEW regression (not explained by
anything this plan's own tasks changed), don't try to fix it yourself — report it clearly
so the controller can decide how to handle it.

## Before Reporting Back: Self-Review

- Did you distinguish any known/expected gaps (e.g. missing admin credentials in this
  environment) from genuine regressions, with evidence?
- Did you check for stack-trace leakage on the new endpoints specifically?
- Did you clean up every test row you created?

## Report Format

- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- Test suite result
- Patient email-verification walkthrough results (real status codes, root causes for anything unexpected)
- Admin back-office walkthrough results (real status codes; explicit note if admin credentials/fixtures weren't available)
- Stack-trace leakage check result
- Any genuinely new issue found
- Overall assessment: is this plan's work sound and ready, independent of any environment-specific gaps (e.g. no admin account existing yet in dev)?

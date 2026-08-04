# Branchement frontend patient/médecin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the static patient-space pages (profil, carnet, consultations, ordonnances, messages) and the minimum doctor-space pages (calendrier, dashboard, creer-ordonnance, profil, messages) to the already-implemented backend API, add patient weight + profile photos (patient and doctor), and clean out leftover test data.

**Architecture:** Same pattern as the existing Auth/Admin pages — an inline `<script>` at the bottom of each HTML file calling `apiGet`/`apiPost`/`apiPostForm`/`apiRequest` (`frontend/api.js`) and manipulating the DOM directly, no framework. Backend changes are additive: a few new columns (migration), a few enriched response schemas (name/photo joins, following the existing `ComplaintOut`/`DoctorCalendarEntryOut` pattern of building the Pydantic model explicitly instead of relying on ORM attribute passthrough), and two new endpoints.

**Tech Stack:** FastAPI (async) + SQLAlchemy 2.0 + Alembic + PostgreSQL, vanilla JS + `api.js`/`auth.js`/`app.js`, pytest (`tests/conftest.py` harness, SQLite in-memory, fake S3 client).

**Spec:** `docs/superpowers/specs/2026-08-02-patient-doctor-frontend-wiring.md`

---

## Before you start

Run the existing suite once to confirm a clean baseline:

```bash
cd Backend-API
uv run python -m pytest -q
```

Expected: `37 passed`. If this doesn't pass, stop and fix it before starting — nothing in this plan depends on failures that predate it.

---

## Tranche 1 — Nettoyage des données de test

### Task 1: `reset_dev_data.py` script

**Files:**
- Create: `Backend-API/scripts/reset_dev_data.py`

No pytest test for this one — it's an operational script in the same spirit as `scripts/seed_admin.py`, which also has no automated test. Verification is a manual run against the dev database.

- [ ] **Step 1: Write the script**

```python
"""Dev-only: wipe test data (patients, doctors, and everything derived from
them), keeping admins. Mirrors seed_admin.py's pattern of a small standalone
script rather than an API endpoint — there is no "reset the database" route
by design."""

import argparse
import asyncio

from sqlalchemy import text

from core.database import async_session_factory

TABLES = [
    "care_plans",
    "chronic_follow_ups",
    "complaints",
    "reviews",
    "messages",
    "conversations",
    "health_record_documents",
    "treatment_intakes",
    "treatment_schedules",
    "treatments",
    "prescriptions",
    "appointments",
    "availabilities",
    "email_verification_tokens",
    "password_reset_tokens",
    "doctors",
    "patients",
]


async def reset_dev_data() -> None:
    async with async_session_factory() as session:
        await session.execute(
            text(f"TRUNCATE TABLE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
        )
        await session.commit()
    print(f"Tables videes : {', '.join(TABLES)} (admins conserves)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Vide les donnees patients/medecins/RDV/etc. Garde les admins."
    )
    parser.add_argument(
        "--yes", action="store_true", help="Confirme sans prompt interactif."
    )
    args = parser.parse_args()
    if not args.yes:
        confirm = input(
            "Ceci va supprimer TOUTES les donnees patients/medecins/RDV/etc. "
            "Continuer ? [y/N] "
        )
        if confirm.strip().lower() != "y":
            print("Annule.")
            raise SystemExit(0)
    asyncio.run(reset_dev_data())
```

- [ ] **Step 2: Run it against the dev database and verify**

```bash
cd Backend-API
uv run python scripts/reset_dev_data.py --yes
```

Expected: prints `Tables videes : ...`. Then verify counts:

```bash
uv run python -c "
import asyncio
from sqlalchemy import select, func
from core.database import async_session_factory
from features.Auth.models import Doctor, Patient, Admin

async def main():
    async with async_session_factory() as session:
        for label, model in [('doctors', Doctor), ('patients', Patient), ('admins', Admin)]:
            print(label, await session.scalar(select(func.count()).select_from(model)))

asyncio.run(main())
"
```

Expected: `doctors 0`, `patients 0`, `admins 2` (the admins already seeded stay untouched).

- [ ] **Step 3: Commit**

```bash
git add Backend-API/scripts/reset_dev_data.py
git commit -m "feat: add dev data reset script"
```

---

## Tranche 2 — Profil patient + médecin (poids, photo) + Carnet de santé

### Task 2: Migration — `weight_kg` and `photo_file_key` columns

**Files:**
- Create: `Backend-API/alembic/versions/<new_revision>_add_weight_and_photo_fields.py`

- [ ] **Step 1: Generate the revision id and write the migration**

Alembic revision ids are content-addressed hashes you pick yourself (12 lowercase hex chars, following the existing files' style — e.g. run `python -c "import uuid; print(uuid.uuid4().hex[:12])"` to get one, or pick any unused 12-hex-char string). For this plan, use `a1b2c3d4e5f6` as the revision id — substitute your own if it collides.

```python
"""add weight_kg and photo_file_key fields

Revision ID: a1b2c3d4e5f6
Revises: f2a66aa2414c
Create Date: 2026-08-02 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f2a66aa2414c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("patients", sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True))
    op.add_column(
        "patients", sa.Column("photo_file_key", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "doctors", sa.Column("photo_file_key", sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("doctors", "photo_file_key")
    op.drop_column("patients", "photo_file_key")
    op.drop_column("patients", "weight_kg")
```

- [ ] **Step 2: Apply it against the dev database and verify**

```bash
cd Backend-API
uv run python -m alembic upgrade head
uv run python -c "
import asyncio
from sqlalchemy import text
from core.database import engine

async def main():
    async with engine.begin() as conn:
        result = await conn.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='patients' AND column_name IN ('weight_kg','photo_file_key')\"))
        print(result.fetchall())
        result = await conn.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='doctors' AND column_name='photo_file_key'\"))
        print(result.fetchall())

asyncio.run(main())
"
```

Expected: both queries return the new column names.

- [ ] **Step 3: Commit**

```bash
git add Backend-API/alembic/versions/a1b2c3d4e5f6_add_weight_and_photo_fields.py
git commit -m "feat: add patient weight_kg and photo_file_key columns (patient+doctor)"
```

### Task 3: `Patient`/`Doctor` models gain the new columns

**Files:**
- Modify: `Backend-API/features/Auth/models.py:61-62` (Patient), `:90` (Doctor)

- [ ] **Step 1: Edit `Patient`**

In `features/Auth/models.py`, in the `Patient` class, add after the `allergies` line (currently line 62):

```python
    allergies: Mapped[str | None] = mapped_column(String(500), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    photo_file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

This needs `Decimal` and `Numeric` imported — both are already imported at the top of the file (`from decimal import Decimal`, `from sqlalchemy import ... Numeric ...`), used already by `Doctor.consultation_fee`.

- [ ] **Step 2: Edit `Doctor`**

In the `Doctor` class, add after the `diploma_file_key` line (currently line 90):

```python
    diploma_file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    photo_file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 3: Verify the app still imports cleanly**

```bash
cd Backend-API
uv run python -c "import app"
```

Expected: no error (this doesn't run a DB query, just checks the module graph and model class bodies are valid Python/SQLAlchemy).

- [ ] **Step 4: Commit**

```bash
git add Backend-API/features/Auth/models.py
git commit -m "feat: add weight_kg and photo_file_key to Patient/Doctor models"
```

### Task 4: Patient profile — schema, logic, routes (weight + photo)

**Files:**
- Modify: `Backend-API/features/Patients/schemas.py:11-37`
- Modify: `Backend-API/features/Patients/logic.py:1-32`
- Modify: `Backend-API/features/Patients/routes.py`
- Test: `Backend-API/tests/test_profile_and_photos.py` (new file)

- [ ] **Step 1: Write the failing tests**

Create `Backend-API/tests/test_profile_and_photos.py`:

```python
"""Patient/doctor profile extras: weight, and profile photo upload+display."""

from tests.conftest import _auth


async def test_patient_can_set_weight_and_it_persists(client, patient):
    resp = await client.patch(
        "/patients/me", json={"weight_kg": 68.5}, headers=_auth(patient["token"])
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["weight_kg"] == 68.5

    again = await client.get("/patients/me", headers=_auth(patient["token"]))
    assert again.json()["weight_kg"] == 68.5


async def test_patient_profile_has_no_photo_by_default(client, patient):
    resp = await client.get("/patients/me", headers=_auth(patient["token"]))
    assert resp.status_code == 200
    assert resp.json()["photo_url"] is None


async def test_patient_can_upload_a_photo(client, patient):
    resp = await client.post(
        "/patients/me/photo",
        files={"photo": ("me.jpg", b"\xff\xd8\xfffake-jpeg", "image/jpeg")},
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["photo_url"].startswith("https://fake-s3.local/")

    again = await client.get("/patients/me", headers=_auth(patient["token"]))
    assert again.json()["photo_url"].startswith("https://fake-s3.local/")
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd Backend-API
uv run python -m pytest tests/test_profile_and_photos.py -v
```

Expected: FAIL — `weight_kg`/`photo_url` unknown fields (422 or KeyError), and `POST /patients/me/photo` returns 404 (route doesn't exist yet).

- [ ] **Step 3: Update `PatientProfileOut`/`PatientProfileUpdateRequest`**

In `features/Patients/schemas.py`, replace the two classes:

```python
class PatientProfileOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    date_of_birth: date
    place_of_birth: str
    address: str
    phone_number: str
    country_of_residence: str
    gender: Gender
    city: str
    email: EmailStr
    blood_type: str | None
    allergies: str | None
    weight_kg: float | None
    photo_url: str | None

    model_config = {"from_attributes": True}


class PatientProfileUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    address: str | None = None
    phone_number: str | None = None
    country_of_residence: str | None = None
    city: str | None = None
    blood_type: str | None = None
    allergies: str | None = None
    weight_kg: float | None = None
```

- [ ] **Step 4: Add a profile-builder helper and photo update to `logic.py`**

In `features/Patients/logic.py`, add the import and two functions. At the top, add:

```python
from core.storage import get_file_url
from features.Patients.schemas import PatientProfileOut
```

(add these next to the existing `from features.Patients.schemas import (...)` block — merge into one import line for `PatientProfileOut` alongside the others already imported).

Replace `update_patient_profile` and add the two new functions:

```python
def build_profile_out(patient: Patient) -> PatientProfileOut:
    return PatientProfileOut(
        id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        place_of_birth=patient.place_of_birth,
        address=patient.address,
        phone_number=patient.phone_number,
        country_of_residence=patient.country_of_residence,
        gender=patient.gender,
        city=patient.city,
        email=patient.email,
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        weight_kg=float(patient.weight_kg) if patient.weight_kg is not None else None,
        photo_url=get_file_url(patient.photo_file_key) if patient.photo_file_key else None,
    )


async def update_patient_profile(
    db: AsyncSession, patient: Patient, data: PatientProfileUpdateRequest
) -> PatientProfileOut:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    await db.commit()
    await db.refresh(patient)
    return build_profile_out(patient)


async def update_patient_photo(db: AsyncSession, patient: Patient, file_key: str) -> PatientProfileOut:
    patient.photo_file_key = file_key
    await db.commit()
    await db.refresh(patient)
    return build_profile_out(patient)
```

- [ ] **Step 5: Update `routes.py`**

Replace the full file `features/Patients/routes.py`:

```python
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_patient
from core.storage import upload_file
from features.Auth.models import Patient
from features.Patients import logic
from features.Patients.schemas import (
    PatientDashboardOut,
    PatientProfileOut,
    PatientProfileUpdateRequest,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/me", response_model=PatientProfileOut)
async def get_my_profile(current_patient: Patient = Depends(get_current_patient)):
    return logic.build_profile_out(current_patient)


@router.patch("/me", response_model=PatientProfileOut)
async def update_my_profile(
    data: PatientProfileUpdateRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    return await logic.update_patient_profile(db, current_patient, data)


@router.post("/me/photo", response_model=PatientProfileOut)
async def upload_my_photo(
    photo: UploadFile,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    file_key = upload_file(await photo.read(), photo.filename, photo.content_type)
    return await logic.update_patient_photo(db, current_patient, file_key)


@router.get("/me/dashboard", response_model=PatientDashboardOut)
async def get_my_dashboard(
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    return await logic.get_patient_dashboard(db, current_patient.id)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd Backend-API
uv run python -m pytest tests/test_profile_and_photos.py -v
```

Expected: `3 passed`.

- [ ] **Step 7: Run the full suite to check nothing else broke**

```bash
uv run python -m pytest -q
```

Expected: `40 passed` (37 existing + 3 new).

- [ ] **Step 8: Commit**

```bash
git add Backend-API/features/Patients/ Backend-API/tests/test_profile_and_photos.py
git commit -m "feat: add patient weight and profile photo upload"
```

### Task 5: Doctor profile — schema, logic, routes (photo)

**Files:**
- Modify: `Backend-API/features/Doctors/schemas.py`
- Modify: `Backend-API/features/Doctors/logic.py`
- Modify: `Backend-API/features/Doctors/routes.py`
- Test: `Backend-API/tests/test_profile_and_photos.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `Backend-API/tests/test_profile_and_photos.py`:

```python
async def test_doctor_can_upload_a_photo(client, validated_doctor):
    resp = await client.post(
        "/doctors/me/photo",
        files={"photo": ("me.jpg", b"\xff\xd8\xfffake-jpeg", "image/jpeg")},
        headers=_auth(validated_doctor["token"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["photo_url"].startswith("https://fake-s3.local/")


async def test_doctor_photo_visible_in_public_search(client, validated_doctor):
    await client.post(
        "/doctors/me/photo",
        files={"photo": ("me.jpg", b"\xff\xd8\xfffake-jpeg", "image/jpeg")},
        headers=_auth(validated_doctor["token"]),
    )
    search = await client.get("/doctors")
    assert search.status_code == 200
    assert search.json()[0]["photo_url"].startswith("https://fake-s3.local/")

    single = await client.get(f"/doctors/{validated_doctor['id']}")
    assert single.json()["photo_url"].startswith("https://fake-s3.local/")
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd Backend-API
uv run python -m pytest tests/test_profile_and_photos.py -v -k doctor
```

Expected: FAIL — 404 on `POST /doctors/me/photo`, and `photo_url` missing from search/single responses.

- [ ] **Step 3: Add `photo_url` to the schemas**

In `features/Doctors/schemas.py`, add `photo_url: str | None` to `DoctorPublicOut` (inherited automatically by `DoctorProfileOut`):

```python
class DoctorPublicOut(BaseModel):
    """What a patient sees when searching for a doctor to book with."""

    id: int
    first_name: str
    last_name: str
    specialty: str
    practice_name: str
    city: str
    consultation_fee: float
    photo_url: str | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Add builder helpers and photo update to `logic.py`**

In `features/Doctors/logic.py`, add the import, and add `DoctorProfileOut`/`DoctorPublicOut` to the existing schemas import line:

```python
from core.storage import get_file_url
from features.Doctors.schemas import (
    DoctorDashboardOut,
    DoctorProfileOut,
    DoctorProfileUpdateRequest,
    DoctorPublicOut,
)
```

Add two builder functions and rewrite the four functions that currently return raw `Doctor` objects:

```python
def build_public_out(doctor: Doctor) -> DoctorPublicOut:
    return DoctorPublicOut(
        id=doctor.id,
        first_name=doctor.first_name,
        last_name=doctor.last_name,
        specialty=doctor.specialty,
        practice_name=doctor.practice_name,
        city=doctor.city,
        consultation_fee=float(doctor.consultation_fee),
        photo_url=get_file_url(doctor.photo_file_key) if doctor.photo_file_key else None,
    )


def build_profile_out(doctor: Doctor) -> DoctorProfileOut:
    return DoctorProfileOut(
        **build_public_out(doctor).model_dump(),
        date_of_birth=doctor.date_of_birth,
        place_of_birth=doctor.place_of_birth,
        email=doctor.email,
        phone_number=doctor.phone_number,
        country_of_residence=doctor.country_of_residence,
        gender=doctor.gender,
        license_number=doctor.license_number,
    )


async def search_doctors(db: AsyncSession, specialty: str | None, city: str | None) -> list[DoctorPublicOut]:
    """Only returns doctors with status=validated, never pending/suspended/deleted ones."""
    query = select(Doctor).where(Doctor.status == DoctorStatus.VALIDATED)
    if specialty:
        query = query.where(Doctor.specialty.ilike(f"%{specialty}%"))
    if city:
        query = query.where(Doctor.city.ilike(f"%{city}%"))
    query = query.order_by(Doctor.last_name, Doctor.first_name)
    doctors = (await db.scalars(query)).all()
    return [build_public_out(d) for d in doctors]


async def get_doctor_profile(db: AsyncSession, doctor_id: int) -> DoctorPublicOut:
    """Public lookup of a single doctor. A patient must not be able to reach a
    doctor that was never validated, so anything but VALIDATED is a 404."""
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None or doctor.status != DoctorStatus.VALIDATED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    return build_public_out(doctor)


async def update_doctor_profile(db: AsyncSession, doctor: Doctor, data: DoctorProfileUpdateRequest) -> DoctorProfileOut:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(doctor, field, value)
    await db.commit()
    await db.refresh(doctor)
    return build_profile_out(doctor)


async def update_doctor_photo(db: AsyncSession, doctor: Doctor, file_key: str) -> DoctorProfileOut:
    doctor.photo_file_key = file_key
    await db.commit()
    await db.refresh(doctor)
    return build_profile_out(doctor)
```

(`get_doctor_dashboard` is unchanged — leave it as-is.)

- [ ] **Step 5: Update `routes.py`**

In `features/Doctors/routes.py`, add the import (`UploadFile`, `upload_file`) and the new route, and fix `get_my_profile`:

```python
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_doctor
from core.storage import upload_file
from features.Auth.models import Doctor
from features.Doctors import logic
from features.Doctors.schemas import (
    DoctorDashboardOut,
    DoctorProfileOut,
    DoctorProfileUpdateRequest,
    DoctorPublicOut,
)

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorPublicOut])
async def search_doctors(
    specialty: str | None = None, city: str | None = None, db: AsyncSession = Depends(get_db)
):
    return await logic.search_doctors(db, specialty, city)


@router.get("/me", response_model=DoctorProfileOut)
async def get_my_profile(current_doctor: Doctor = Depends(get_current_doctor)):
    return logic.build_profile_out(current_doctor)


@router.patch("/me", response_model=DoctorProfileOut)
async def update_my_profile(
    data: DoctorProfileUpdateRequest,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.update_doctor_profile(db, current_doctor, data)


@router.post("/me/photo", response_model=DoctorProfileOut)
async def upload_my_photo(
    photo: UploadFile,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    file_key = upload_file(await photo.read(), photo.filename, photo.content_type)
    return await logic.update_doctor_photo(db, current_doctor, file_key)


@router.get("/me/dashboard", response_model=DoctorDashboardOut)
async def get_my_dashboard(
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.get_doctor_dashboard(db, current_doctor.id)


# Kept last: a literal path like /me must be matched before this catch-all,
# otherwise "me" would be parsed as a doctor_id.
@router.get("/{doctor_id}", response_model=DoctorPublicOut)
async def get_doctor(doctor_id: int, db: AsyncSession = Depends(get_db)):
    return await logic.get_doctor_profile(db, doctor_id)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd Backend-API
uv run python -m pytest tests/test_profile_and_photos.py -v
uv run python -m pytest -q
```

Expected: all `test_profile_and_photos.py` tests pass (5 total), full suite `42 passed`.

- [ ] **Step 7: Commit**

```bash
git add Backend-API/features/Doctors/ Backend-API/tests/test_profile_and_photos.py
git commit -m "feat: add doctor profile photo upload, expose photo_url in doctor search"
```

### Task 6: `HealthRecordSummaryOut` gains `weight_kg`

**Files:**
- Modify: `Backend-API/features/HealthRecords/schemas.py`
- Modify: `Backend-API/features/HealthRecords/logic.py:69-75`
- Test: `Backend-API/tests/test_prescriptions_and_carnet.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `Backend-API/tests/test_prescriptions_and_carnet.py`:

```python
async def test_health_record_summary_includes_weight(client, patient):
    await client.patch("/patients/me", json={"weight_kg": 72.0}, headers=_auth(patient["token"]))
    resp = await client.get("/health-records/me", headers=_auth(patient["token"]))
    assert resp.status_code == 200
    assert resp.json()["weight_kg"] == 72.0
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd Backend-API
uv run python -m pytest tests/test_prescriptions_and_carnet.py -v -k weight
```

Expected: FAIL — `KeyError: 'weight_kg'`.

- [ ] **Step 3: Add the field**

In `features/HealthRecords/schemas.py`, find `HealthRecordSummaryOut` and add `weight_kg: float | None` next to `allergies`.

In `features/HealthRecords/logic.py`, in `get_health_record_summary` (line 69-75), add the field to the constructed object:

```python
    return HealthRecordSummaryOut(
        first_name=patient.first_name,
        last_name=patient.last_name,
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        weight_kg=float(patient.weight_kg) if patient.weight_kg is not None else None,
        document_count=document_count or 0,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd Backend-API
uv run python -m pytest tests/test_prescriptions_and_carnet.py -v
uv run python -m pytest -q
```

Expected: full suite `43 passed`.

- [ ] **Step 5: Commit**

```bash
git add Backend-API/features/HealthRecords/ Backend-API/tests/test_prescriptions_and_carnet.py
git commit -m "feat: expose patient weight in health record summary"
```

### Task 7: Messaging `ConversationOut` enrichment (name + photo, both sides)

**Files:**
- Modify: `Backend-API/features/Messaging/schemas.py`
- Modify: `Backend-API/features/Messaging/logic.py`
- Test: `Backend-API/tests/test_prescriptions_and_carnet.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `Backend-API/tests/test_prescriptions_and_carnet.py`:

```python
async def test_conversation_out_includes_names_and_photos(client, completed_appointment):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]
    await client.post(
        "/doctors/me/photo",
        files={"photo": ("doc.jpg", b"\xff\xd8\xfffake", "image/jpeg")},
        headers=_auth(doctor["token"]),
    )

    convo = await client.post(
        "/messaging/conversations", json={"doctor_id": doctor["id"]}, headers=_auth(patient["token"])
    )
    assert convo.status_code == 201, convo.text
    body = convo.json()
    assert body["patient_name"] == "Ada Lovelace"
    assert body["doctor_name"] == "Gregory House"
    assert body["doctor_photo_url"].startswith("https://fake-s3.local/")
    assert body["patient_photo_url"] is None

    listing = await client.get("/messaging/conversations", headers=_auth(doctor["token"]))
    assert listing.status_code == 200
    assert listing.json()[0]["patient_name"] == "Ada Lovelace"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd Backend-API
uv run python -m pytest tests/test_prescriptions_and_carnet.py -v -k conversation_out
```

Expected: FAIL — `KeyError: 'patient_name'`.

- [ ] **Step 3: Rewrite `ConversationOut`**

In `features/Messaging/schemas.py`, replace `ConversationOut`:

```python
class ConversationOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_photo_url: str | None
    doctor_id: int
    doctor_name: str
    doctor_photo_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Rewrite `logic.py`'s conversation functions**

In `features/Messaging/logic.py`, add imports:

```python
from core.storage import get_file_url
from features.Auth.models import Doctor, DoctorStatus, Patient
from features.Messaging.schemas import ConversationOut
```

(merge `Patient` into the existing `from features.Auth.models import Doctor, DoctorStatus` line.)

Add a helper and rewrite `get_or_create_conversation` and `list_my_conversations`:

```python
def _build_conversation_out(conversation: Conversation, patient: Patient, doctor: Doctor) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        patient_id=conversation.patient_id,
        patient_name=f"{patient.first_name} {patient.last_name}",
        patient_photo_url=get_file_url(patient.photo_file_key) if patient.photo_file_key else None,
        doctor_id=conversation.doctor_id,
        doctor_name=f"{doctor.first_name} {doctor.last_name}",
        doctor_photo_url=get_file_url(doctor.photo_file_key) if doctor.photo_file_key else None,
        created_at=conversation.created_at,
    )


async def get_or_create_conversation(db: AsyncSession, patient_id: int, doctor_id: int) -> ConversationOut:
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None or doctor.status != DoctorStatus.VALIDATED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    patient = await db.get(Patient, patient_id)

    existing = (
        await db.scalars(
            select(Conversation).where(
                Conversation.patient_id == patient_id, Conversation.doctor_id == doctor_id
            )
        )
    ).first()
    if existing is not None:
        return _build_conversation_out(existing, patient, doctor)

    conversation = Conversation(patient_id=patient_id, doctor_id=doctor_id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return _build_conversation_out(conversation, patient, doctor)


async def list_my_conversations(db: AsyncSession, user_type: str, user_id: int) -> list[ConversationOut]:
    column = Conversation.patient_id if user_type == "patient" else Conversation.doctor_id
    rows = (
        await db.execute(
            select(Conversation, Patient, Doctor)
            .join(Patient, Conversation.patient_id == Patient.id)
            .join(Doctor, Conversation.doctor_id == Doctor.id)
            .where(column == user_id)
            .order_by(Conversation.created_at.desc())
        )
    ).all()
    return [_build_conversation_out(conversation, patient, doctor) for conversation, patient, doctor in rows]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd Backend-API
uv run python -m pytest tests/test_prescriptions_and_carnet.py -v
uv run python -m pytest -q
```

Expected: full suite `44 passed`.

- [ ] **Step 6: Commit**

```bash
git add Backend-API/features/Messaging/ Backend-API/tests/test_prescriptions_and_carnet.py
git commit -m "feat: enrich ConversationOut with both participants' name and photo"
```

### Task 8: `app.js` — shared avatar-rendering helper

**Files:**
- Modify: `Backend-API/../frontend/app.js` (i.e. `frontend/app.js`)

- [ ] **Step 1: Add the helper**

At the end of `frontend/app.js`, add:

```javascript
// --- Avatar : remplace le fond initiales par la vraie photo si elle existe ---
// `el` est le div .avatar existant (initiales en texte + fond coloré inline).
// Ne touche à rien si photoUrl est absent/null : les initiales restent affichées.
function renderAvatar(el, photoUrl) {
  if (!el || !photoUrl) return;
  el.style.backgroundImage = 'url(' + photoUrl + ')';
  el.style.backgroundSize = 'cover';
  el.style.backgroundPosition = 'center';
  el.textContent = '';
}
```

- [ ] **Step 2: Manual verification**

No automated JS test in this project (only backend has pytest). Open the browser console on any page after this change and run `typeof renderAvatar` — expect `"function"`.

- [ ] **Step 3: Commit**

```bash
git add frontend/app.js
git commit -m "feat: add shared renderAvatar helper for real profile photos"
```

### Task 9: `patient/profil.html` — wire profile form + photo upload

**Files:**
- Modify: `frontend/patient/profil.html`

- [ ] **Step 1: Replace the banner + form markup**

Replace the block from `<div class="banner"` through the closing `</div>` of the form card (originally lines 97-136) with:

```html
        <div class="banner" style="padding:26px;display:flex;align-items:center;gap:18px;margin-bottom:20px;box-shadow:0 12px 28px rgba(13,148,136,.2);">
          <div id="profil-avatar" class="avatar avatar-round" style="width:72px;height:72px;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:26px;flex:none;cursor:pointer;" title="Cliquer pour changer la photo">--</div>
          <input type="file" id="profil-photo-input" accept="image/*" style="display:none;">
          <div>
            <div id="profil-name" style="font-size:23px;font-weight:800;"></div>
            <div id="profil-email" style="opacity:.85;font-size:14px;margin-top:3px;"></div>
          </div>
        </div>
        <p class="form-error hidden" id="profil-error"></p>
        <form id="profil-form" class="card card--pad" style="border-radius:18px;padding:24px;">
          <div style="font-weight:800;font-size:16px;margin-bottom:18px;">Informations personnelles</div>
          <div class="grid-2">
            <div>
              <label class="label" style="letter-spacing:0;">PRÉNOM</label>
              <input class="input" id="profil-first-name">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">NOM</label>
              <input class="input" id="profil-last-name">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">EMAIL</label>
              <input class="input" id="profil-email-field" disabled>
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">TÉLÉPHONE</label>
              <input class="input" id="profil-phone">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">PAYS DE RÉSIDENCE</label>
              <input class="input" id="profil-country">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">VILLE</label>
              <input class="input" id="profil-city">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">ADRESSE</label>
              <input class="input" id="profil-address">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">DATE DE NAISSANCE</label>
              <input class="input" id="profil-dob" disabled>
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">LIEU DE NAISSANCE</label>
              <input class="input" id="profil-pob" disabled>
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">GROUPE SANGUIN</label>
              <input class="input" id="profil-blood-type" placeholder="Ex. O+">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">POIDS (KG)</label>
              <input class="input" id="profil-weight" type="number" step="0.1" placeholder="Ex. 68.5">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">ALLERGIES</label>
              <input class="input" id="profil-allergies" placeholder="Ex. Pénicilline, poils d'animaux">
            </div>
          </div>
          <div class="row" style="gap:10px;margin-top:22px;">
            <button type="submit" class="btn btn--primary">Enregistrer</button>
            <button type="button" class="btn btn--ghost" id="profil-cancel">Annuler</button>
          </div>
        </form>
```

- [ ] **Step 2: Replace the closing `<script>` block**

Replace `  <script src="../app.js"></script>` (last line before `</body>`) with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('patient');
      var profile = null;

      function fillForm(p) {
        document.getElementById('profil-name').textContent = p.first_name + ' ' + p.last_name;
        document.getElementById('profil-email').textContent = p.email;
        document.getElementById('profil-first-name').value = p.first_name;
        document.getElementById('profil-last-name').value = p.last_name;
        document.getElementById('profil-email-field').value = p.email;
        document.getElementById('profil-phone').value = p.phone_number;
        document.getElementById('profil-country').value = p.country_of_residence;
        document.getElementById('profil-city').value = p.city;
        document.getElementById('profil-address').value = p.address;
        document.getElementById('profil-dob').value = p.date_of_birth;
        document.getElementById('profil-pob').value = p.place_of_birth;
        document.getElementById('profil-blood-type').value = p.blood_type || '';
        document.getElementById('profil-weight').value = p.weight_kg != null ? p.weight_kg : '';
        document.getElementById('profil-allergies').value = p.allergies || '';
        var avatar = document.getElementById('profil-avatar');
        avatar.textContent = (p.first_name[0] || '') + (p.last_name[0] || '');
        avatar.style.backgroundImage = '';
        renderAvatar(avatar, p.photo_url);
      }

      async function load() {
        profile = await apiGet('/patients/me');
        fillForm(profile);
      }
      load();

      document.getElementById('profil-avatar').addEventListener('click', function () {
        document.getElementById('profil-photo-input').click();
      });
      document.getElementById('profil-photo-input').addEventListener('change', async function (e) {
        var file = e.target.files[0];
        if (!file) return;
        var formData = new FormData();
        formData.append('photo', file);
        profile = await apiPostForm('/patients/me/photo', formData);
        fillForm(profile);
      });

      document.getElementById('profil-cancel').addEventListener('click', function () {
        fillForm(profile);
      });

      document.getElementById('profil-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        var errorEl = document.getElementById('profil-error');
        errorEl.classList.add('hidden');
        var weightRaw = document.getElementById('profil-weight').value;
        try {
          profile = await apiRequest('PATCH', '/patients/me', {
            json: {
              first_name: document.getElementById('profil-first-name').value,
              last_name: document.getElementById('profil-last-name').value,
              phone_number: document.getElementById('profil-phone').value,
              country_of_residence: document.getElementById('profil-country').value,
              city: document.getElementById('profil-city').value,
              address: document.getElementById('profil-address').value,
              blood_type: document.getElementById('profil-blood-type').value || null,
              weight_kg: weightRaw ? parseFloat(weightRaw) : null,
              allergies: document.getElementById('profil-allergies').value || null,
            },
          });
          fillForm(profile);
        } catch (err) {
          errorEl.textContent = 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
      });
    })();
  </script>
```

- [ ] **Step 3: Manual verification**

```bash
cd Backend-API
uv run uvicorn app:app --port 8010 --reload
```

In a second terminal, register and confirm a fresh patient, then note the credentials:

```bash
curl -s -X POST http://localhost:8010/auth/patients/register -H "Content-Type: application/json" -d '{"first_name":"Ada","last_name":"Lovelace","date_of_birth":"1990-05-10","place_of_birth":"London","address":"1 Analytical St","phone_number":"+33123456789","country_of_residence":"France","gender":"femme","city":"Paris","email":"ada@example.com","password":"supersecret1","password_confirmation":"supersecret1"}'
```

Get the confirmation token from the DB and confirm, then log in via the browser at `http://localhost:8010/index.html` with `ada@example.com` / `supersecret1`, navigate to `patient/profil.html`: verify the form is pre-filled, change groupe sanguin/poids, click Enregistrer, refresh the page, verify the values persisted. Click the avatar, pick an image file, verify it renders in place of the initials.

- [ ] **Step 4: Commit**

```bash
git add frontend/patient/profil.html
git commit -m "feat: wire patient profile page to the API (incl. weight and photo)"
```

### Task 10: `medecin/profil.html` — wire photo upload (+ existing fields)

**Files:**
- Modify: `frontend/medecin/profil.html`

- [ ] **Step 1: Replace the banner + form markup**

Replace the block from `<div class="banner"` through the closing `</div>` of the form card (originally lines 92-131). Note `DoctorProfileUpdateRequest` only allows editing `phone_number`, `practice_name`, `consultation_fee` — `first_name`/`last_name`/`country_of_residence`/`city` have no PATCH support in the API, so they stay read-only here (this mirrors what the backend actually allows; extending it further is out of scope for this plan):

```html
        <div class="banner" style="padding:26px;display:flex;align-items:center;gap:18px;margin-bottom:20px;box-shadow:0 12px 28px rgba(13,148,136,.2);">
          <div id="profil-avatar" class="avatar avatar-round" style="width:72px;height:72px;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:26px;flex:none;cursor:pointer;" title="Cliquer pour changer la photo">--</div>
          <input type="file" id="profil-photo-input" accept="image/*" style="display:none;">
          <div>
            <div id="profil-name" style="font-size:23px;font-weight:800;"></div>
            <div id="profil-email" style="opacity:.85;font-size:14px;margin-top:3px;"></div>
          </div>
        </div>
        <p class="form-error hidden" id="profil-error"></p>
        <form id="profil-form" class="card card--pad" style="border-radius:18px;padding:24px;">
          <div style="font-weight:800;font-size:16px;margin-bottom:18px;">Informations personnelles</div>
          <div class="grid-2">
            <div>
              <label class="label" style="letter-spacing:0;">NOM COMPLET</label>
              <input class="input" id="profil-name-field" disabled>
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">EMAIL</label>
              <input class="input" id="profil-email-field" disabled>
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">TÉLÉPHONE</label>
              <input class="input" id="profil-phone">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">ÉTABLISSEMENT / CABINET</label>
              <input class="input" id="profil-practice">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">TARIF DE CONSULTATION</label>
              <input class="input" id="profil-fee" type="number" step="0.01">
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">DATE DE NAISSANCE</label>
              <input class="input" id="profil-dob" disabled>
            </div>
            <div>
              <label class="label" style="letter-spacing:0;">LIEU DE NAISSANCE</label>
              <input class="input" id="profil-pob" disabled>
            </div>
          </div>
          <div class="row" style="gap:10px;margin-top:22px;">
            <button type="submit" class="btn btn--primary">Enregistrer</button>
            <button type="button" class="btn btn--ghost" id="profil-cancel">Annuler</button>
          </div>
        </form>
```

- [ ] **Step 2: Replace the closing `<script>` block**

Replace `  <script src="../app.js"></script>` with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('doctor');
      var profile = null;

      function fillForm(d) {
        document.getElementById('profil-name').textContent = 'Dr. ' + d.first_name + ' ' + d.last_name;
        document.getElementById('profil-email').textContent = d.email;
        document.getElementById('profil-name-field').value = 'Dr. ' + d.first_name + ' ' + d.last_name;
        document.getElementById('profil-email-field').value = d.email;
        document.getElementById('profil-phone').value = d.phone_number;
        document.getElementById('profil-practice').value = d.practice_name;
        document.getElementById('profil-fee').value = d.consultation_fee;
        document.getElementById('profil-dob').value = d.date_of_birth;
        document.getElementById('profil-pob').value = d.place_of_birth;
        var avatar = document.getElementById('profil-avatar');
        avatar.textContent = (d.first_name[0] || '') + (d.last_name[0] || '');
        avatar.style.backgroundImage = '';
        renderAvatar(avatar, d.photo_url);
      }

      async function load() {
        profile = await apiGet('/doctors/me');
        fillForm(profile);
      }
      load();

      document.getElementById('profil-avatar').addEventListener('click', function () {
        document.getElementById('profil-photo-input').click();
      });
      document.getElementById('profil-photo-input').addEventListener('change', async function (e) {
        var file = e.target.files[0];
        if (!file) return;
        var formData = new FormData();
        formData.append('photo', file);
        profile = await apiPostForm('/doctors/me/photo', formData);
        fillForm(profile);
      });

      document.getElementById('profil-cancel').addEventListener('click', function () {
        fillForm(profile);
      });

      document.getElementById('profil-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        var errorEl = document.getElementById('profil-error');
        errorEl.classList.add('hidden');
        try {
          profile = await apiRequest('PATCH', '/doctors/me', {
            json: {
              phone_number: document.getElementById('profil-phone').value,
              practice_name: document.getElementById('profil-practice').value,
              consultation_fee: parseFloat(document.getElementById('profil-fee').value),
            },
          });
          fillForm(profile);
        } catch (err) {
          errorEl.textContent = 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
      });
    })();
  </script>
```

- [ ] **Step 3: Manual verification**

With the server running, log in as a validated doctor (create one via the registration UI + admin validation, or reuse `Backend-API/scripts/seed_admin.py` login to validate one created through `inscription-medecin.html`). Open `medecin/profil.html`: verify fields are pre-filled, edit téléphone/tarif, save, refresh, verify persistence. Upload a photo, verify it displays.

- [ ] **Step 4: Commit**

```bash
git add frontend/medecin/profil.html
git commit -m "feat: wire doctor profile page to the API (incl. photo)"
```

### Task 11: `patient/carnet.html` — wire summary, documents, upload, download

**Files:**
- Modify: `frontend/patient/carnet.html`

- [ ] **Step 1: Replace the summary banner**

Replace the block from `<div style="background:var(--green-soft)` through its closing `</div>` (originally lines 106-126) with:

```html
        <div style="background:var(--green-soft);border:1px solid var(--green-soft-border);border-radius:16px;padding:20px 24px;display:flex;gap:40px;margin-bottom:22px;flex-wrap:wrap;">
          <div>
            <div style="color:var(--muted);font-size:13px;margin-bottom:4px;">Patient</div>
            <div id="carnet-name" style="font-weight:800;font-size:16px;"></div>
          </div>
          <div>
            <div style="color:var(--muted);font-size:13px;margin-bottom:4px;">Groupe sanguin</div>
            <div id="carnet-blood-type" style="font-weight:800;font-size:16px;">—</div>
          </div>
          <div>
            <div style="color:var(--muted);font-size:13px;margin-bottom:4px;">Poids</div>
            <div id="carnet-weight" style="font-weight:800;font-size:16px;">—</div>
          </div>
          <div>
            <div style="color:var(--muted);font-size:13px;margin-bottom:6px;">Allergies</div>
            <div id="carnet-allergies" class="row" style="gap:6px;"></div>
          </div>
          <div>
            <div style="color:var(--muted);font-size:13px;margin-bottom:4px;">Documents</div>
            <div id="carnet-doc-count" style="font-weight:800;font-size:16px;"></div>
          </div>
        </div>
```

- [ ] **Step 2: Replace the "Ajouter un document" button**

Replace the button (originally lines 100-104):

```html
          <button class="btn btn--primary" id="carnet-add-doc-btn" data-open="carnet-upload-modal">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>Ajouter un document
          </button>
```

- [ ] **Step 3: Replace the document grid and add the upload modal**

Replace the `<div class="grid-3">...</div>` block (originally lines 146-180) with an empty container the script fills, and add a modal right before `</div>` that closes `<main>` (i.e. right before `    </main>` originally at line 182):

```html
        <div class="grid-3" id="carnet-doc-grid"></div>
      </div>
    </main>
  </div>
  <div class="modal__backdrop" id="carnet-upload-modal" style="display:none;">
    <div class="modal" style="max-width:400px;">
      <div class="row" style="justify-content:space-between;margin-bottom:18px;">
        <div style="font-size:19px;font-weight:800;">Ajouter un document</div>
        <button class="modal__close" data-close>✕</button>
      </div>
      <input type="file" id="carnet-upload-input" style="margin-bottom:16px;">
      <p class="form-error hidden" id="carnet-upload-error"></p>
      <button class="btn btn--primary btn--block" id="carnet-upload-submit">Téléverser</button>
    </div>
  </div>
```

(This restructures the trailing markup: the original file had `</div>\n      </div>\n    </main>\n  </div>\n  <script...`; the `<div class="grid-3">` was inside the `.fade.container-lg` div. Keep that outer nesting — only the grid's *contents* and what comes after `</main></div>` change.)

- [ ] **Step 4: Replace the closing `<script>` block**

Replace `  <script src="../app.js"></script>` with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('patient');

      var SOURCE_LABELS = {
        manual_upload: 'Upload manuel',
        prescription: 'Ordonnance',
        message: 'Message',
        doctor_upload: 'Médecin',
      };

      function renderDocuments(docs) {
        var grid = document.getElementById('carnet-doc-grid');
        grid.innerHTML = '';
        docs.forEach(function (doc) {
          var card = document.createElement('div');
          card.className = 'card';
          card.innerHTML =
            '<div style="width:44px;height:44px;border-radius:12px;background:#5b6ef5;display:flex;align-items:center;justify-content:center;margin-bottom:14px;">' +
            '<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6" /></svg></div>' +
            '<div style="font-weight:700;font-size:14.5px;margin-bottom:4px;">' + doc.original_filename + '</div>' +
            '<div style="color:var(--muted);font-size:12.5px;">' + new Date(doc.created_at).toLocaleDateString('fr-FR') + '</div>' +
            '<span class="chip" style="display:inline-block;margin-top:12px;padding:4px 11px;border-radius:14px;font-size:11.5px;">' + (SOURCE_LABELS[doc.source_type] || doc.source_type) + '</span>' +
            '<button class="btn btn--ghost btn--sm" style="margin-top:10px;width:100%;" data-download="' + doc.id + '">Télécharger</button>';
          grid.appendChild(card);
        });
      }

      async function loadSummary() {
        var summary = await apiGet('/health-records/me');
        document.getElementById('carnet-name').textContent = summary.first_name + ' ' + summary.last_name;
        document.getElementById('carnet-blood-type').textContent = summary.blood_type || '—';
        document.getElementById('carnet-weight').textContent = summary.weight_kg != null ? summary.weight_kg + ' kg' : '—';
        document.getElementById('carnet-doc-count').textContent = summary.document_count + ' fichier' + (summary.document_count > 1 ? 's' : '');
        var allergiesEl = document.getElementById('carnet-allergies');
        allergiesEl.innerHTML = '';
        (summary.allergies ? summary.allergies.split(',') : []).forEach(function (a) {
          var span = document.createElement('span');
          span.style.cssText = 'background:#fee2e2;color:#dc2626;font-weight:600;font-size:12.5px;padding:4px 11px;border-radius:20px;';
          span.textContent = a.trim();
          allergiesEl.appendChild(span);
        });
      }

      async function loadDocuments() {
        var docs = await apiGet('/health-records/me/documents');
        renderDocuments(docs);
      }

      loadSummary();
      loadDocuments();

      document.getElementById('carnet-upload-submit').addEventListener('click', async function () {
        var input = document.getElementById('carnet-upload-input');
        var errorEl = document.getElementById('carnet-upload-error');
        errorEl.classList.add('hidden');
        var file = input.files[0];
        if (!file) {
          errorEl.textContent = 'Choisissez un fichier.';
          errorEl.classList.remove('hidden');
          return;
        }
        try {
          var formData = new FormData();
          formData.append('file', file);
          await apiPostForm('/health-records/me/documents', formData);
          document.getElementById('carnet-upload-modal').style.display = 'none';
          input.value = '';
          await loadSummary();
          await loadDocuments();
        } catch (err) {
          errorEl.textContent = 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
      });

      document.addEventListener('click', async function (e) {
        var btn = e.target.closest('[data-download]');
        if (!btn) return;
        var result = await apiGet('/health-records/me/documents/' + btn.getAttribute('data-download') + '/download');
        window.open(result.download_url, '_blank');
      });
    })();
  </script>
```

- [ ] **Step 5: Manual verification**

With the server running and logged in as a patient, open `patient/carnet.html`: verify the summary shows real name/blood type/weight/allergies/count (initially 0 documents). Click "Ajouter un document", pick a file, submit — verify it appears in the grid and the count updates. Click "Télécharger" on a card — verify a new tab opens with a presigned MinIO URL.

- [ ] **Step 6: Commit**

```bash
git add frontend/patient/carnet.html
git commit -m "feat: wire patient carnet page to the API (summary, documents, upload, download)"
```

---

## Tranche 3 — Créneaux (médecin) + Consultations (patient)

No backend changes needed — `POST /appointments/availabilities`, `GET /doctors/{id}/availabilities`, `POST /appointments`, and `GET /doctors` already exist and are tested.

### Task 12: `medecin/calendrier.html` — add "Publier un créneau"

**Files:**
- Modify: `frontend/medecin/calendrier.html`

- [ ] **Step 1: Add a button and a modal**

After the `<p class="subtitle">Gérez vos consultations et disponibilités.</p>` line, add:

```html
        <div class="row mb-20">
          <button class="btn btn--primary" data-open="add-availability-modal">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>Ajouter une disponibilité
          </button>
        </div>
```

Before the closing `</div>` of `<main>` (i.e. right before `    </main>`), add the modal:

```html
  <div class="modal__backdrop" id="add-availability-modal" style="display:none;">
    <div class="modal" style="max-width:400px;">
      <div class="row" style="justify-content:space-between;margin-bottom:18px;">
        <div style="font-size:19px;font-weight:800;">Ajouter une disponibilité</div>
        <button class="modal__close" data-close>✕</button>
      </div>
      <label class="label">DATE</label>
      <input class="input" type="date" id="avail-date" style="margin-bottom:14px;">
      <label class="label">HEURE DE DÉBUT</label>
      <input class="input" type="time" id="avail-start" style="margin-bottom:14px;">
      <label class="label">HEURE DE FIN</label>
      <input class="input" type="time" id="avail-end" style="margin-bottom:16px;">
      <p class="form-error hidden" id="avail-error"></p>
      <button class="btn btn--primary btn--block" id="avail-submit">Publier le créneau</button>
    </div>
  </div>
```

- [ ] **Step 2: Add the inline script**

Replace `  <script src="../app.js"></script>` with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('doctor');

      document.getElementById('avail-submit').addEventListener('click', async function () {
        var errorEl = document.getElementById('avail-error');
        errorEl.classList.add('hidden');
        var date = document.getElementById('avail-date').value;
        var start = document.getElementById('avail-start').value;
        var end = document.getElementById('avail-end').value;
        if (!date || !start || !end) {
          errorEl.textContent = 'Tous les champs sont obligatoires.';
          errorEl.classList.remove('hidden');
          return;
        }
        try {
          await apiPost('/appointments/availabilities', {
            date: date,
            start_time: start + ':00',
            end_time: end + ':00',
          });
          document.getElementById('add-availability-modal').style.display = 'none';
        } catch (err) {
          errorEl.textContent = err.status === 409
            ? 'Ce créneau chevauche une disponibilité existante.'
            : 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
      });
    })();
  </script>
```

- [ ] **Step 3: Manual verification**

Log in as a validated doctor, open `medecin/calendrier.html`, click "Ajouter une disponibilité", fill a future date/time range, submit. Verify via curl the slot exists:

```bash
curl -s "http://localhost:8010/appointments/doctors/<doctor_id>/availabilities?from_date=2026-08-02"
```

- [ ] **Step 4: Commit**

```bash
git add frontend/medecin/calendrier.html
git commit -m "feat: let doctors publish availability slots from the calendar page"
```

### Task 13: `patient/consultations.html` — real doctor list + slot booking

**Files:**
- Modify: `frontend/patient/consultations.html`

- [ ] **Step 1: Replace the search row's specialty select with an id, and the doctor grid**

Replace the `<select class="select" ...>` (originally lines 105-111) — add `id="doctor-specialty-filter"`:

```html
          <select class="select" id="doctor-specialty-filter" style="border-color:var(--border);border-radius:13px;font-weight:600;color:var(--slate);min-width:180px;width:auto;background:#fff;">
            <option value="">Toutes spécialités</option>
            <option value="Médecine générale">Médecine générale</option>
            <option value="Cardiologie">Cardiologie</option>
            <option value="Gynécologie">Gynécologie</option>
            <option value="Psychiatrie">Psychiatrie</option>
          </select>
```

Also add `id="doctor-search-input"` to the text input (originally line 103):

```html
            <input id="doctor-search-input" placeholder="Rechercher un médecin…" style="padding:14px 0;">
```

Replace the entire `<div class="grid-2">...</div>` block (originally lines 113-240, the six hardcoded doctor cards) with an empty container:

```html
        <div class="grid-2" id="doctor-grid"></div>
```

- [ ] **Step 2: Replace the RDV modal's body (keep the two backdrop divs, rewrite their inner content)**

Replace the whole `<div class="modal__backdrop" id="rdv-modal" ...>...</div>` block (originally lines 244-278) with:

```html
  <div class="modal__backdrop" id="rdv-modal" style="display:none;">
    <div class="modal">
      <div class="row" style="justify-content:space-between;margin-bottom:18px;">
        <div style="font-size:19px;font-weight:800;">Prendre rendez-vous</div>
        <button class="modal__close" data-close>✕</button>
      </div>
      <div class="row" id="rdv-doctor-summary" style="gap:14px;background:var(--green-soft);border-radius:14px;padding:15px;margin-bottom:18px;"></div>
      <label class="label" style="margin-bottom:8px;display:block;">CRÉNEAU</label>
      <select class="select" id="rdv-availability-select" style="margin-bottom:16px;"></select>
      <label class="label" style="margin-bottom:8px;display:block;">MODE</label>
      <div class="col" style="gap:10px;margin-bottom:16px;">
        <div class="mode-opt" data-modeopt data-c="#8b5cf6" data-mode="message">
          <div class="mode-dot" style="border-color:#8b5cf6;"></div>
          <div class="mode-tag" style="background:#8b5cf618;color:#8b5cf6;">M</div>
          <div style="font-weight:700;font-size:15px;">Message</div>
        </div>
        <div class="mode-opt" data-modeopt data-c="#0d9488" data-mode="presentiel">
          <div class="mode-dot"></div>
          <div class="mode-tag" style="background:#0d948818;color:#0d9488;">P</div>
          <div style="font-weight:700;font-size:15px;">Présentiel</div>
        </div>
      </div>
      <label class="label" style="margin-bottom:8px;display:block;">MOTIF (OPTIONNEL)</label>
      <input class="input" id="rdv-reason" style="margin-bottom:16px;" placeholder="Ex. Douleurs thoraciques">
      <p class="form-error hidden" id="rdv-error"></p>
      <button class="btn btn--primary btn--block" data-rdvconfirm>Confirmer le rendez-vous <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </button>
    </div>
  </div>
  <div class="modal__backdrop" id="rdv-sent-modal" style="display:none;">
    <div class="modal" style="max-width:390px;text-align:center;">
      <div style="width:60px;height:60px;border-radius:16px;background:var(--green-soft);display:flex;align-items:center;justify-content:center;margin:0 auto 18px;">
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 2 11 13" />
          <path d="M22 2 15 22l-4-9-9-4Z" />
        </svg>
      </div>
      <div style="font-size:19px;font-weight:800;margin-bottom:8px;">Demande envoyée</div>
      <p style="color:var(--muted);font-size:14px;margin:0 0 20px;line-height:1.55;">Votre demande de rendez-vous a bien été transmise au médecin. Vous recevrez une confirmation dès qu'il l'aura acceptée.</p>
      <button class="btn btn--primary btn--block" data-close>J'ai compris</button>
    </div>
  </div>
```

Note: this drops the old `data-rdvconfirm` handler's reliance on `app.js`'s hardcoded close/open of `rdv-modal`/`rdv-sent-modal` for the *success* transition — `app.js`'s existing `[data-rdvconfirm]` listener still does that part (close rdv-modal, open rdv-sent-modal) unconditionally on click. We need the actual booking API call to happen first and only then let that visual transition occur. Since `app.js`'s listener has no way to fail the transition, this page's own script (registered after `app.js`) intercepts the same click, calls `e.stopImmediatePropagation()` on failure to prevent `app.js`'s handler from also firing and showing the false-success modal.

- [ ] **Step 3: Add the inline script**

Replace `  <script src="../app.js"></script>` with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('patient');
      var allDoctors = [];
      var selectedDoctor = null;
      var selectedMode = null;

      function doctorInitials(d) {
        return (d.first_name[0] || '') + (d.last_name[0] || '');
      }

      function renderDoctors(doctors) {
        var grid = document.getElementById('doctor-grid');
        grid.innerHTML = '';
        doctors.forEach(function (d) {
          var card = document.createElement('div');
          card.className = 'card col';
          card.innerHTML =
            '<div class="row" style="gap:13px;margin-bottom:12px;">' +
            '<div class="avatar avatar-48" data-avatar style="background:#10b981;">' + doctorInitials(d) + '</div>' +
            '<div style="flex:1;min-width:0;"><div style="font-weight:700;font-size:15.5px;">Dr. ' + d.first_name + ' ' + d.last_name + '</div>' +
            '<div style="color:var(--green-text);font-size:13px;font-weight:600;">' + d.specialty + '</div></div></div>' +
            '<div style="font-weight:800;font-size:16px;margin-bottom:8px;">' + d.consultation_fee + ' FCFA</div>' +
            '<div style="color:var(--muted);font-size:13.5px;line-height:1.5;margin-bottom:12px;flex:1;">' + d.practice_name + ' · ' + d.city + '</div>' +
            '<button class="btn btn--primary" style="width:100%;padding:12px;" data-book="' + d.id + '">Prendre RDV</button>';
          renderAvatar(card.querySelector('[data-avatar]'), d.photo_url);
          grid.appendChild(card);
        });
      }

      function applyFilters() {
        var text = document.getElementById('doctor-search-input').value.trim().toLowerCase();
        var filtered = allDoctors.filter(function (d) {
          return !text || (d.first_name + ' ' + d.last_name).toLowerCase().indexOf(text) !== -1;
        });
        renderDoctors(filtered);
      }

      async function loadDoctors() {
        var specialty = document.getElementById('doctor-specialty-filter').value;
        allDoctors = await apiGet('/doctors' + (specialty ? '?specialty=' + encodeURIComponent(specialty) : ''));
        applyFilters();
      }

      document.getElementById('doctor-specialty-filter').addEventListener('change', loadDoctors);
      document.getElementById('doctor-search-input').addEventListener('input', applyFilters);
      loadDoctors();

      document.addEventListener('click', async function (e) {
        var bookBtn = e.target.closest('[data-book]');
        if (!bookBtn) return;
        var doctorId = bookBtn.getAttribute('data-book');
        selectedDoctor = allDoctors.find(function (d) { return String(d.id) === doctorId; });
        selectedMode = null;
        document.getElementById('rdv-doctor-summary').innerHTML =
          '<div class="avatar avatar-46" style="background:#10b981;">' + doctorInitials(selectedDoctor) + '</div>' +
          '<div><div style="font-weight:700;font-size:15px;">Dr. ' + selectedDoctor.first_name + ' ' + selectedDoctor.last_name + '</div>' +
          '<div style="color:var(--green-text);font-size:13px;font-weight:600;">' + selectedDoctor.specialty + ' · ' + selectedDoctor.consultation_fee + ' FCFA</div></div>';
        document.getElementById('rdv-reason').value = '';
        var select = document.getElementById('rdv-availability-select');
        select.innerHTML = '<option>Chargement…</option>';
        var today = new Date().toISOString().slice(0, 10);
        var slots = await apiGet('/doctors/' + doctorId + '/availabilities?from_date=' + today);
        if (slots.length === 0) {
          select.innerHTML = '<option value="">Aucun créneau disponible</option>';
        } else {
          select.innerHTML = slots.map(function (s) {
            return '<option value="' + s.id + '">' + s.date + ' · ' + s.start_time.slice(0, 5) + '-' + s.end_time.slice(0, 5) + '</option>';
          }).join('');
        }
      });

      document.addEventListener('click', function (e) {
        var opt = e.target.closest('[data-modeopt]');
        if (opt) selectedMode = opt.getAttribute('data-mode') === 'message' ? 'message' : 'in_person';
      });

      document.addEventListener('click', async function (e) {
        var confirmBtn = e.target.closest('[data-rdvconfirm]');
        if (!confirmBtn) return;
        var errorEl = document.getElementById('rdv-error');
        errorEl.classList.add('hidden');
        var availabilityId = document.getElementById('rdv-availability-select').value;
        if (!availabilityId || !selectedMode) {
          errorEl.textContent = 'Choisissez un créneau et un mode de consultation.';
          errorEl.classList.remove('hidden');
          e.stopImmediatePropagation();
          return;
        }
        try {
          await apiPost('/appointments', {
            availability_id: parseInt(availabilityId, 10),
            mode: selectedMode,
            reason: document.getElementById('rdv-reason').value || null,
          });
        } catch (err) {
          errorEl.textContent = 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
          e.stopImmediatePropagation();
        }
      }, true);
    })();
  </script>
```

Note the last listener is registered with `useCapture: true` and calls `e.stopImmediatePropagation()` on failure — this runs *before* `app.js`'s bubble-phase `[data-rdvconfirm]` listener and stops it from firing when the booking failed, so the false "Demande envoyée" success modal doesn't show on error. On success, propagation continues and `app.js`'s existing handler performs the modal swap as before.

- [ ] **Step 4: Manual verification**

With at least one validated doctor with a published slot (from Task 12), log in as a patient, open `patient/consultations.html`: verify real doctors appear, filter by specialty, search by name. Click "Prendre RDV", pick the slot, pick a mode, type a motif, confirm — verify "Demande envoyée" shows, and `GET /appointments/pending` (as the doctor, via curl) shows the new pending appointment.

- [ ] **Step 5: Commit**

```bash
git add frontend/patient/consultations.html
git commit -m "feat: wire patient consultations page to real doctors and slot booking"
```

---

## Tranche 4 — Accepter/Refuser RDV + Calendrier (médecin)

### Task 14: Enrich `GET /appointments/pending` with patient name/reason/mode

**Files:**
- Modify: `Backend-API/features/Appointments/schemas.py`
- Modify: `Backend-API/features/Appointments/logic.py:150-159`
- Modify: `Backend-API/features/Appointments/routes.py:66-71`
- Test: `Backend-API/tests/test_appointments_flow.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `Backend-API/tests/test_appointments_flow.py` (check the file's existing imports first — it already imports `_auth` from `tests.conftest`, following the same pattern as other test files):

```python
async def test_pending_list_includes_patient_name_and_reason(client, patient, validated_doctor):
    from datetime import date

    doctor_headers = _auth(validated_doctor["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={"date": date.today().isoformat(), "start_time": "10:00:00", "end_time": "10:30:00"},
        headers=doctor_headers,
    )
    await client.post(
        "/appointments",
        json={"availability_id": slot.json()["id"], "mode": "in_person", "reason": "Douleurs thoraciques"},
        headers=_auth(patient["token"]),
    )

    pending = await client.get("/appointments/pending", headers=doctor_headers)
    assert pending.status_code == 200
    entry = pending.json()[0]
    assert entry["patient_name"] == "Ada Lovelace"
    assert entry["reason"] == "Douleurs thoraciques"
    assert entry["mode"] == "in_person"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd Backend-API
uv run python -m pytest tests/test_appointments_flow.py -v -k pending_list
```

Expected: FAIL — `KeyError: 'patient_name'`.

- [ ] **Step 3: Add `PendingAppointmentOut`**

In `features/Appointments/schemas.py`, change the datetime import at the top:

```python
from datetime import date, datetime, time
```

Add the new schema after `AppointmentOut`:

```python
class PendingAppointmentOut(BaseModel):
    """A pending request as shown on the doctor's dashboard — needs the
    patient's name, which a raw AppointmentOut can't carry without a join."""

    appointment_id: int
    patient_name: str
    reason: str | None
    mode: AppointmentMode
    created_at: datetime
```

- [ ] **Step 4: Rewrite `list_pending_appointments`**

In `features/Appointments/logic.py`, `Patient` is already imported (`from features.Auth.models import Doctor, Patient`) — only add `PendingAppointmentOut` to the existing `from features.Appointments.schemas import (...)` block. Replace `list_pending_appointments`:

```python
async def list_pending_appointments(db: AsyncSession, doctor_id: int) -> list[PendingAppointmentOut]:
    rows = (
        await db.execute(
            select(Appointment, Patient.first_name, Patient.last_name)
            .join(Patient, Appointment.patient_id == Patient.id)
            .where(Appointment.doctor_id == doctor_id, Appointment.status == AppointmentStatus.PENDING)
            .order_by(Appointment.created_at)
        )
    ).all()
    return [
        PendingAppointmentOut(
            appointment_id=appointment.id,
            patient_name=f"{first_name} {last_name}",
            reason=appointment.reason,
            mode=appointment.mode,
            created_at=appointment.created_at,
        )
        for appointment, first_name, last_name in rows
    ]
```

- [ ] **Step 5: Update the route's `response_model`**

In `features/Appointments/routes.py`, add `PendingAppointmentOut` to the schemas import and change:

```python
@router.get("/pending", response_model=list[PendingAppointmentOut])
async def list_pending_appointments(
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_pending_appointments(db, current_doctor.id)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd Backend-API
uv run python -m pytest tests/test_appointments_flow.py -v
uv run python -m pytest -q
```

Expected: full suite `45 passed`.

- [ ] **Step 7: Commit**

```bash
git add Backend-API/features/Appointments/ Backend-API/tests/test_appointments_flow.py
git commit -m "feat: enrich pending appointments with patient name and reason"
```

### Task 15: `medecin/dashboard.html` — wire "Demandes en attente"

**Files:**
- Modify: `frontend/medecin/dashboard.html`

- [ ] **Step 1: Replace the pending-requests block**

Replace the block from `<div class="section-title">Demandes en attente</div>` through the closing `</div>` of that card's `.col` list (originally lines 148-171, keeping the outer `<div class="card card--pad" ...>` wrapper — only its title's badge and the `.col` list contents change):

```html
            <div class="section-title">Demandes en attente</div>
              <span class="badge badge--amber" id="pending-count" style="margin-left:auto;font-weight:800;font-size:13px;padding:3px 11px;">0</span>
            </div>
            <div class="col" style="gap:10px;" id="pending-list"></div>
```

- [ ] **Step 2: Replace the closing `<script>` block**

Replace `  <script src="../app.js"></script>` with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('doctor');

      function initialsFromName(name) {
        var parts = name.split(' ');
        return (parts[0][0] || '') + (parts[parts.length - 1][0] || '');
      }

      function renderPending(list) {
        var container = document.getElementById('pending-list');
        container.innerHTML = '';
        document.getElementById('pending-count').textContent = list.length;
        list.forEach(function (item) {
          var row = document.createElement('div');
          row.className = 'mini-row';
          row.innerHTML =
            '<div class="avatar avatar-42" style="background:#5b6ef5;">' + initialsFromName(item.patient_name) + '</div>' +
            '<div style="flex:1;min-width:0;"><div style="font-weight:700;font-size:14.5px;">' + item.patient_name + '</div>' +
            '<div style="color:var(--muted);font-size:13px;">' + (item.reason || 'Consultation') + '</div></div>' +
            '<span class="chip">' + (item.mode === 'message' ? 'Message' : 'Présentiel') + '</span>' +
            '<button class="btn btn--primary btn--sm" data-accept="' + item.appointment_id + '">Accepter</button>' +
            '<button class="btn btn--ghost btn--sm" data-refuse="' + item.appointment_id + '">Refuser</button>';
          container.appendChild(row);
        });
      }

      async function loadPending() {
        var list = await apiGet('/appointments/pending');
        renderPending(list);
      }
      loadPending();

      document.addEventListener('click', async function (e) {
        var acceptBtn = e.target.closest('[data-accept]');
        if (acceptBtn) {
          await apiPost('/appointments/' + acceptBtn.getAttribute('data-accept') + '/decision', { approve: true });
          await loadPending();
          return;
        }
        var refuseBtn = e.target.closest('[data-refuse]');
        if (refuseBtn) {
          await apiPost('/appointments/' + refuseBtn.getAttribute('data-refuse') + '/decision', { approve: false });
          await loadPending();
        }
      });
    })();
  </script>
```

(`app.js`'s existing `[data-accept]` listener still fires independently and shows `accept-modal` — that's fine, it's a purely visual success notice with no data dependency.)

- [ ] **Step 3: Manual verification**

With a pending appointment created (from Task 13's manual test, or via curl), log in as the doctor, open `medecin/dashboard.html`: verify the request shows with the real patient name/reason/mode. Click "Accepter" — verify the row disappears and the success modal shows. Create another pending request and click "Refuser" — verify it disappears and `GET /appointments/doctors/{id}/availabilities` shows the slot `FREE` again.

- [ ] **Step 4: Commit**

```bash
git add frontend/medecin/dashboard.html
git commit -m "feat: wire doctor dashboard pending-requests to the API"
```

### Task 16: `medecin/calendrier.html` — real day view + "Terminer la consultation"

**Files:**
- Modify: `frontend/medecin/calendrier.html`

- [ ] **Step 1: Add a day list container**

After the availability-publishing button row added in Task 12, add:

```html
        <div class="card card--pad" style="border-radius:18px;">
          <div class="row" style="justify-content:space-between;margin-bottom:16px;">
            <div class="section-title">Consultations du jour</div>
            <input type="date" class="input" id="calendar-day-picker" style="width:auto;">
          </div>
          <div class="col" style="gap:9px;" id="calendar-day-list"></div>
        </div>
```

- [ ] **Step 2: Extend the inline script from Task 12**

Add to the same `<script>` block added in Task 12 (inside the IIFE, after the `avail-submit` listener):

```javascript
      function todayIso() {
        return new Date().toISOString().slice(0, 10);
      }

      async function loadDay(day) {
        var entries = await apiGet('/appointments/calendar?day=' + day);
        var list = document.getElementById('calendar-day-list');
        list.innerHTML = '';
        var today = todayIso();
        entries.forEach(function (entry) {
          var row = document.createElement('div');
          row.className = 'row';
          row.style.cssText = 'gap:12px;padding:9px 0;border-bottom:1px solid #f4f6f7;';
          var canComplete = entry.status === 'confirmed' && entry.date <= today;
          row.innerHTML =
            '<div style="font-weight:800;font-size:14px;color:var(--green-text);width:46px;flex:none;">' + entry.start_time.slice(0, 5) + '</div>' +
            '<div style="flex:1;min-width:0;"><div style="font-weight:700;font-size:14px;">' + entry.patient_name + '</div></div>' +
            '<span class="chip" style="font-size:11.5px;padding:4px 9px;border-radius:14px;">' + (entry.mode === 'message' ? 'Message' : 'Présentiel') + '</span>' +
            (canComplete ? '<button class="btn btn--primary btn--sm" data-complete="' + entry.appointment_id + '">Terminer</button>' : '');
          list.appendChild(row);
        });
      }

      var dayPicker = document.getElementById('calendar-day-picker');
      dayPicker.value = todayIso();
      dayPicker.addEventListener('change', function () { loadDay(dayPicker.value); });
      loadDay(dayPicker.value);

      document.addEventListener('click', async function (e) {
        var completeBtn = e.target.closest('[data-complete]');
        if (!completeBtn) return;
        await apiPost('/appointments/' + completeBtn.getAttribute('data-complete') + '/complete', {});
        await loadDay(dayPicker.value);
      });
```

- [ ] **Step 3: Manual verification**

Book, accept, and check-in a full flow: patient books a slot for today, doctor accepts it (Task 15), doctor opens `medecin/calendrier.html`, verifies the confirmed appointment shows with a "Terminer" button, clicks it, verifies the button disappears afterward (status no longer `confirmed`).

- [ ] **Step 4: Commit**

```bash
git add frontend/medecin/calendrier.html
git commit -m "feat: show real day calendar and let doctors complete consultations"
```

---

## Tranche 5 — Ordonnance (médecin) + Mes ordonnances (patient)

### Task 17: `PrescriptionOut` enrichment (doctor name + treatments)

**Files:**
- Modify: `Backend-API/features/Prescriptions/schemas.py`
- Modify: `Backend-API/features/Prescriptions/logic.py`
- Test: `Backend-API/tests/test_prescriptions_and_carnet.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `Backend-API/tests/test_prescriptions_and_carnet.py`:

```python
async def test_prescription_out_includes_doctor_name_and_treatments(client, completed_appointment):
    patient = completed_appointment["patient"]
    resp = await _prescribe(client, completed_appointment)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["doctor_name"] == "Gregory House"
    assert body["treatments"][0]["medication_name"] == "Aspirin"
    assert body["treatments"][0]["dosage"] == "500mg"

    listing = await client.get("/prescriptions", headers=_auth(patient["token"]))
    listed = listing.json()[0]
    assert listed["doctor_name"] == "Gregory House"
    assert listed["treatments"][0]["medication_name"] == "Aspirin"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd Backend-API
uv run python -m pytest tests/test_prescriptions_and_carnet.py -v -k doctor_name_and_treatments
```

Expected: FAIL — `KeyError: 'doctor_name'`.

- [ ] **Step 3: Add `TreatmentLineOut` and enrich `PrescriptionOut`**

In `features/Prescriptions/schemas.py`, add after `TreatmentLineRequest`:

```python
class TreatmentLineOut(BaseModel):
    medication_name: str
    dosage: str
    start_date: date
    end_date: date
```

Replace `PrescriptionOut`:

```python
class PrescriptionOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    doctor_name: str
    appointment_id: int
    notes: str | None
    created_at: datetime
    treatments: list[TreatmentLineOut]
```

- [ ] **Step 4: Rewrite `create_prescription` and `list_patient_prescriptions`**

In `features/Prescriptions/logic.py`, add `from collections import defaultdict` at the top, and import `PrescriptionOut, TreatmentLineOut` alongside the existing schema import.

Change `create_prescription`'s return type and final return statement — replace the last two lines (`await db.refresh(prescription)` / `return prescription`):

```python
    await db.commit()
    await db.refresh(prescription)
    return PrescriptionOut(
        id=prescription.id,
        patient_id=prescription.patient_id,
        doctor_id=prescription.doctor_id,
        doctor_name=f"{doctor.first_name} {doctor.last_name}",
        appointment_id=prescription.appointment_id,
        notes=prescription.notes,
        created_at=prescription.created_at,
        treatments=[
            TreatmentLineOut(
                medication_name=line.medication_name,
                dosage=line.dosage,
                start_date=line.start_date,
                end_date=line.end_date,
            )
            for line in data.treatments
        ],
    )
```

And change the function signature line from `-> Prescription:` to `-> PrescriptionOut:`.

Replace `list_patient_prescriptions`:

```python
async def list_patient_prescriptions(db: AsyncSession, patient_id: int) -> list[PrescriptionOut]:
    rows = (
        await db.execute(
            select(Prescription, Doctor)
            .join(Doctor, Prescription.doctor_id == Doctor.id)
            .where(Prescription.patient_id == patient_id)
            .order_by(Prescription.created_at.desc())
        )
    ).all()
    prescriptions = [p for p, _ in rows]
    prescription_ids = [p.id for p in prescriptions]

    treatment_rows: list[Treatment] = []
    if prescription_ids:
        treatment_rows = list(
            (await db.scalars(select(Treatment).where(Treatment.prescription_id.in_(prescription_ids)))).all()
        )
    treatments_by_prescription: dict[int, list[TreatmentLineOut]] = defaultdict(list)
    for t in treatment_rows:
        treatments_by_prescription[t.prescription_id].append(
            TreatmentLineOut(
                medication_name=t.medication_name,
                dosage=t.dosage,
                start_date=t.start_date,
                end_date=t.end_date,
            )
        )

    return [
        PrescriptionOut(
            id=p.id,
            patient_id=p.patient_id,
            doctor_id=p.doctor_id,
            doctor_name=f"{doctor.first_name} {doctor.last_name}",
            appointment_id=p.appointment_id,
            notes=p.notes,
            created_at=p.created_at,
            treatments=treatments_by_prescription.get(p.id, []),
        )
        for p, doctor in rows
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd Backend-API
uv run python -m pytest tests/test_prescriptions_and_carnet.py -v
uv run python -m pytest -q
```

Expected: full suite `46 passed`.

- [ ] **Step 6: Commit**

```bash
git add Backend-API/features/Prescriptions/ Backend-API/tests/test_prescriptions_and_carnet.py
git commit -m "feat: enrich PrescriptionOut with doctor name and treatment lines"
```

### Task 18: New endpoint `GET /appointments/completed-awaiting-prescription`

**Files:**
- Modify: `Backend-API/features/Appointments/schemas.py`
- Modify: `Backend-API/features/Appointments/logic.py`
- Modify: `Backend-API/features/Appointments/routes.py`
- Test: `Backend-API/tests/test_appointments_flow.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `Backend-API/tests/test_appointments_flow.py`:

```python
async def test_completed_awaiting_prescription_excludes_already_prescribed(client, completed_appointment):
    doctor = completed_appointment["doctor"]
    doctor_headers = _auth(doctor["token"])

    awaiting = await client.get("/appointments/completed-awaiting-prescription", headers=doctor_headers)
    assert awaiting.status_code == 200
    assert len(awaiting.json()) == 1
    assert awaiting.json()[0]["appointment_id"] == completed_appointment["appointment_id"]
    assert awaiting.json()[0]["patient_name"] == "Ada Lovelace"

    await client.post(
        "/prescriptions",
        json={"appointment_id": completed_appointment["appointment_id"], "notes": None, "treatments": []},
        headers=doctor_headers,
    )

    awaiting_after = await client.get("/appointments/completed-awaiting-prescription", headers=doctor_headers)
    assert awaiting_after.json() == []
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd Backend-API
uv run python -m pytest tests/test_appointments_flow.py -v -k awaiting_prescription
```

Expected: FAIL — 404 (route doesn't exist).

- [ ] **Step 3: Add `AwaitingPrescriptionOut`**

In `features/Appointments/schemas.py`, add:

```python
class AwaitingPrescriptionOut(BaseModel):
    """A completed consultation with no prescription yet — what the doctor
    picks from on the "créer une ordonnance" page."""

    appointment_id: int
    patient_id: int
    patient_name: str
    date: date
    start_time: time
```

- [ ] **Step 4: Add the logic function**

In `features/Appointments/logic.py`, add the import `from features.Prescriptions.models import Prescription` and `AwaitingPrescriptionOut` to the schemas import. Add:

```python
async def list_completed_awaiting_prescription(db: AsyncSession, doctor_id: int) -> list[AwaitingPrescriptionOut]:
    rows = (
        await db.execute(
            select(
                Appointment.id,
                Appointment.patient_id,
                Patient.first_name,
                Patient.last_name,
                Availability.date,
                Availability.start_time,
            )
            .join(Availability, Appointment.availability_id == Availability.id)
            .join(Patient, Appointment.patient_id == Patient.id)
            .outerjoin(Prescription, Prescription.appointment_id == Appointment.id)
            .where(
                Appointment.doctor_id == doctor_id,
                Appointment.status == AppointmentStatus.COMPLETED,
                Prescription.id.is_(None),
            )
            .order_by(Availability.date.desc(), Availability.start_time.desc())
        )
    ).all()
    return [
        AwaitingPrescriptionOut(
            appointment_id=appt_id,
            patient_id=patient_id,
            patient_name=f"{first_name} {last_name}",
            date=appt_date,
            start_time=start_time,
        )
        for appt_id, patient_id, first_name, last_name, appt_date, start_time in rows
    ]
```

- [ ] **Step 5: Add the route**

In `features/Appointments/routes.py`, add `AwaitingPrescriptionOut` to the schemas import and add, after `/pending`:

```python
@router.get("/completed-awaiting-prescription", response_model=list[AwaitingPrescriptionOut])
async def list_completed_awaiting_prescription(
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_completed_awaiting_prescription(db, current_doctor.id)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd Backend-API
uv run python -m pytest tests/test_appointments_flow.py -v
uv run python -m pytest -q
```

Expected: full suite `47 passed`.

- [ ] **Step 7: Commit**

```bash
git add Backend-API/features/Appointments/ Backend-API/tests/test_appointments_flow.py
git commit -m "feat: add endpoint listing completed appointments awaiting a prescription"
```

### Task 19: `medecin/creer-ordonnance.html` — wire patient list + prescription form

**Files:**
- Modify: `frontend/medecin/creer-ordonnance.html`

- [ ] **Step 1: Replace the patient-selection list**

Replace the `<div class="col" style="gap:10px;margin-bottom:26px;">...</div>` block (originally lines 93-124, the three hardcoded `.select-row` divs) with an empty container:

```html
        <div class="col" style="gap:10px;margin-bottom:26px;" id="awaiting-list"></div>
```

- [ ] **Step 2: Give the medication template a stable structure and the generate button an id**

Change `<div class="med-row" data-index="0">` to also have `id="med-row-template"` isn't necessary (the existing `data-addmed`/`data-removemed`/`renumberMeds()` logic in `app.js` already clones the last `.med-row`, unchanged). Only change the final button (originally line 155):

```html
            <button class="btn btn--primary" id="generate-prescription-btn" style="margin-top:12px;padding:14px;width:100%;box-shadow:0 6px 16px rgba(13,148,136,.25);">Générer l'ordonnance</button>
```

- [ ] **Step 3: Add the inline script**

Replace `  <script src="../app.js"></script>` with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('doctor');
      var selectedAppointmentId = null;

      function initialsFromName(name) {
        var parts = name.split(' ');
        return (parts[0][0] || '') + (parts[parts.length - 1][0] || '');
      }

      async function loadAwaiting() {
        var list = await apiGet('/appointments/completed-awaiting-prescription');
        var container = document.getElementById('awaiting-list');
        container.innerHTML = '';
        list.forEach(function (item) {
          var row = document.createElement('div');
          row.className = 'select-row';
          row.setAttribute('data-selectord', '');
          row.setAttribute('data-appointment-id', item.appointment_id);
          row.innerHTML =
            '<div class="avatar avatar-44" style="background:#10b981;">' + initialsFromName(item.patient_name) + '</div>' +
            '<div style="flex:1;"><div style="font-weight:700;font-size:15px;">' + item.patient_name + '</div>' +
            '<div style="color:var(--muted);font-size:13px;">' + item.date + ' · ' + item.start_time.slice(0, 5) + '</div></div>' +
            '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6" /></svg>';
          container.appendChild(row);
        });
      }
      loadAwaiting();

      // app.js's existing [data-selectord] handler shows step 2 and highlights the
      // row; this listener (registered after it, same click) just remembers which
      // appointment was picked.
      document.addEventListener('click', function (e) {
        var row = e.target.closest('[data-selectord]');
        if (row) selectedAppointmentId = parseInt(row.getAttribute('data-appointment-id'), 10);
      });

      document.getElementById('generate-prescription-btn').addEventListener('click', async function () {
        if (!selectedAppointmentId) return;
        var rows = document.querySelectorAll('#med-list .med-row');
        var treatments = [];
        rows.forEach(function (row) {
          var inputs = row.querySelectorAll('.med-input');
          var name = inputs[0].value;
          var dosage = inputs[1].value;
          if (!name) return;
          var today = new Date().toISOString().slice(0, 10);
          var durationDays = parseInt(inputs[2].value, 10) || 7;
          var end = new Date();
          end.setDate(end.getDate() + durationDays);
          treatments.push({
            medication_name: name,
            dosage: dosage,
            start_date: today,
            end_date: end.toISOString().slice(0, 10),
            intake_times: ['08:00:00'],
          });
        });
        try {
          await apiPost('/prescriptions', {
            appointment_id: selectedAppointmentId,
            notes: null,
            treatments: treatments,
          });
          window.location.reload();
        } catch (err) {
          window.alert('Une erreur est survenue, réessayez.');
        }
      });
    })();
  </script>
```

Note: the "DURÉE" input in the mock is a free-text field (placeholder `"7 jours"`); this script parses it as a plain integer number of days via `parseInt`, defaulting to 7 if not a number. Intake time defaults to a single daily dose at 08:00 — the mock UI has no per-dose time picker, and adding one is out of scope for this plan (the backend requires at least one `intake_times` entry per treatment, so a sensible default is used).

- [ ] **Step 4: Manual verification**

With a `completed` appointment (book → accept → complete, from Tasks 13/15/16), open `medecin/creer-ordonnance.html` as that doctor: verify the real patient shows in the list. Click it, fill a medication, click "Générer l'ordonnance", verify the page reloads and the patient no longer appears in the list (already prescribed).

- [ ] **Step 5: Commit**

```bash
git add frontend/medecin/creer-ordonnance.html
git commit -m "feat: wire creer-ordonnance page to real completed appointments and the API"
```

### Task 20: `patient/ordonnances.html` — wire prescription list + download

**Files:**
- Modify: `frontend/patient/ordonnances.html`

- [ ] **Step 1: Replace the prescription list**

Replace the `<div class="col" style="gap:14px;">...</div>` block (originally lines 97-137, the two hardcoded cards) with an empty container:

```html
        <div class="col" style="gap:14px;" id="prescription-list"></div>
```

- [ ] **Step 2: Add the inline script**

Replace `  <script src="../app.js"></script>` with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('patient');

      function isActive(prescription) {
        var today = new Date().toISOString().slice(0, 10);
        return prescription.treatments.some(function (t) { return t.end_date >= today; });
      }

      async function load() {
        var prescriptions = await apiGet('/prescriptions');
        var container = document.getElementById('prescription-list');
        container.innerHTML = '';
        prescriptions.forEach(function (p) {
          var title = p.treatments.length ? p.treatments.map(function (t) { return t.medication_name; }).join(', ') : 'Ordonnance';
          var posology = p.treatments.length ? p.treatments.map(function (t) { return t.medication_name + ' (' + t.dosage + ')'; }).join(' · ') : '';
          var active = isActive(p);
          var card = document.createElement('div');
          card.className = 'card';
          card.innerHTML =
            '<div class="row" style="justify-content:space-between;align-items:flex-start;margin-bottom:12px;">' +
            '<div class="row" style="gap:12px;">' +
            '<div style="width:44px;height:44px;border-radius:12px;background:var(--green-soft);display:flex;align-items:center;justify-content:center;flex:none;">' +
            '<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m10.5 20.5-7-7a5 5 0 0 1 7-7l7 7a5 5 0 0 1-7 7Z" /><path d="m8.5 8.5 7 7" /></svg></div>' +
            '<div><div style="font-weight:700;font-size:15.5px;">' + title + '</div>' +
            '<div style="color:var(--muted);font-size:13px;">Dr. ' + p.doctor_name + ' · ' + new Date(p.created_at).toLocaleDateString('fr-FR') + '</div></div></div>' +
            '<span class="badge ' + (active ? 'badge--green' : 'badge--muted') + '">' + (active ? 'Active' : 'Terminée') + '</span></div>' +
            (posology ? '<div style="color:var(--slate);font-size:13.5px;background:var(--field);border-radius:11px;padding:12px 14px;">' + posology + '</div>' : '') +
            '<div class="row" style="gap:10px;margin-top:14px;">' +
            '<button class="btn btn--ghost btn--sm" style="padding:10px 16px;" data-download="' + p.id + '">Télécharger PDF</button></div>';
          container.appendChild(card);
        });
      }
      load();

      document.addEventListener('click', async function (e) {
        var btn = e.target.closest('[data-download]');
        if (!btn) return;
        var result = await apiGet('/prescriptions/' + btn.getAttribute('data-download') + '/download');
        window.open(result.download_url, '_blank');
      });
    })();
  </script>
```

Note: the mock's "Envoyer à la pharmacie" button is dropped entirely (per the spec's explicit out-of-scope list — no backend feature exists for it).

- [ ] **Step 3: Manual verification**

With a prescription created for a patient (Task 19), log in as that patient, open `patient/ordonnances.html`: verify the real prescription shows with medication name(s), doctor name, date, and posology. Click "Télécharger PDF" — verify a new tab opens showing the presigned MinIO URL for the generated PDF.

- [ ] **Step 4: Commit**

```bash
git add frontend/patient/ordonnances.html
git commit -m "feat: wire patient ordonnances page to the API"
```

---

## Tranche 6 — Messagerie (patient + médecin)

Backend already covers this fully (`ConversationOut` was enriched with name+photo in Task 7).

### Task 21: `patient/messages.html` — conversations, thread, send, new conversation

**Files:**
- Modify: `frontend/patient/messages.html`

- [ ] **Step 1: Replace the conversation list and the empty-state pane**

Replace the `<div style="flex:1;overflow-y:auto;...">...</div>` block holding the two hardcoded `.conv-item`s (originally lines 107-123) with an empty container:

```html
            <div style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:6px;min-height:0;" id="conversation-list"></div>
```

Replace the second `<div class="card" style="padding:0;...">...</div>` pane (originally lines 125-133, the "Sélectionnez une conversation" placeholder) so it can switch to a thread view:

```html
          <div class="card" style="padding:0;display:flex;flex-direction:column;min-height:0;overflow:hidden;" id="thread-pane">
            <div id="thread-empty" style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--muted-2);padding:40px;text-align:center;">
              <svg width="54" height="54" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
              </svg>
              <div style="font-size:16px;font-weight:700;color:var(--muted);margin-top:14px;">Sélectionnez une conversation</div>
              <div style="font-size:14px;margin-top:4px;">Choisissez un contact dans la liste pour commencer à discuter.</div>
            </div>
            <div id="thread-active" style="display:none;flex-direction:column;flex:1;min-height:0;">
              <div class="row" id="thread-header" style="gap:12px;padding:16px;border-bottom:1px solid #f4f6f7;"></div>
              <div id="thread-messages" style="flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;"></div>
              <form id="thread-send-form" class="row" style="gap:8px;padding:12px 16px;border-top:1px solid #f4f6f7;">
                <input class="input" id="thread-content" placeholder="Écrire un message…" style="flex:1;">
                <input type="file" id="thread-file" style="display:none;">
                <button type="button" class="btn btn--ghost btn--sm" id="thread-attach">📎</button>
                <button type="submit" class="btn btn--primary btn--sm">Envoyer</button>
              </form>
            </div>
          </div>
```

- [ ] **Step 2: Add the "Nouveau" modal (patient picks a doctor)**

Before `  <script src="../app.js"></script>`, add:

```html
  <div class="modal__backdrop" id="new-conversation-modal" style="display:none;">
    <div class="modal">
      <div class="row" style="justify-content:space-between;margin-bottom:18px;">
        <div style="font-size:19px;font-weight:800;">Nouvelle conversation</div>
        <button class="modal__close" data-close>✕</button>
      </div>
      <input class="input" id="new-conv-search" placeholder="Rechercher un médecin…" style="margin-bottom:14px;">
      <div class="col" style="gap:8px;max-height:320px;overflow-y:auto;" id="new-conv-doctor-list"></div>
    </div>
  </div>
```

Give the "Nouveau" button (originally lines 101-105) `data-open="new-conversation-modal"` and an id:

```html
              <button class="btn btn--primary btn--pill" id="new-conversation-btn" data-open="new-conversation-modal">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 5v14M5 12h14" />
                </svg>Nouveau
              </button>
```

- [ ] **Step 3: Add the inline script**

Replace `  <script src="../app.js"></script>` with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('patient');
      var activeConversationId = null;
      var pollTimer = null;

      function initials(name) {
        var parts = name.split(' ');
        return (parts[0][0] || '') + (parts[parts.length - 1][0] || '');
      }

      async function loadConversations() {
        var conversations = await apiGet('/messaging/conversations');
        var list = document.getElementById('conversation-list');
        list.innerHTML = '';
        conversations.forEach(function (c) {
          var item = document.createElement('div');
          item.className = 'conv-item';
          item.setAttribute('data-id', c.id);
          item.innerHTML =
            '<div class="avatar avatar-42" data-avatar style="background:#0ea5e9;">' + initials(c.doctor_name) + '</div>' +
            '<div style="flex:1;min-width:0;"><div class="name">Dr. ' + c.doctor_name + '</div></div>';
          renderAvatar(item.querySelector('[data-avatar]'), c.doctor_photo_url);
          item.addEventListener('click', function () { openThread(c); });
          list.appendChild(item);
        });
      }

      async function openThread(conversation) {
        activeConversationId = conversation.id;
        document.getElementById('thread-empty').style.display = 'none';
        document.getElementById('thread-active').style.display = 'flex';
        var header = document.getElementById('thread-header');
        header.innerHTML = '<div class="avatar avatar-42" data-avatar style="background:#0ea5e9;">' + initials(conversation.doctor_name) + '</div>' +
          '<div style="font-weight:700;">Dr. ' + conversation.doctor_name + '</div>';
        renderAvatar(header.querySelector('[data-avatar]'), conversation.doctor_photo_url);
        await refreshMessages();
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(refreshMessages, 4000);
      }

      async function refreshMessages() {
        if (!activeConversationId) return;
        var messages = await apiGet('/messaging/conversations/' + activeConversationId + '/messages');
        var container = document.getElementById('thread-messages');
        container.innerHTML = '';
        messages.forEach(function (m) {
          var bubble = document.createElement('div');
          var mine = m.sender_type === 'patient';
          bubble.style.cssText = 'max-width:70%;padding:10px 14px;border-radius:14px;' +
            (mine ? 'align-self:flex-end;background:var(--green-soft);' : 'align-self:flex-start;background:var(--field);');
          bubble.textContent = m.content || '(pièce jointe)';
          if (m.file_key) {
            var link = document.createElement('a');
            link.href = '#';
            link.textContent = ' [voir la pièce jointe]';
            link.addEventListener('click', async function (e) {
              e.preventDefault();
              var result = await apiGet('/messaging/conversations/' + activeConversationId + '/messages/' + m.id + '/attachment');
              window.open(result.download_url, '_blank');
            });
            bubble.appendChild(link);
          }
          container.appendChild(bubble);
        });
        container.scrollTop = container.scrollHeight;
      }

      document.getElementById('thread-attach').addEventListener('click', function () {
        document.getElementById('thread-file').click();
      });

      document.getElementById('thread-send-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        if (!activeConversationId) return;
        var contentInput = document.getElementById('thread-content');
        var fileInput = document.getElementById('thread-file');
        var formData = new FormData();
        formData.append('content', contentInput.value);
        if (fileInput.files[0]) formData.append('file', fileInput.files[0]);
        await apiPostForm('/messaging/conversations/' + activeConversationId + '/messages', formData);
        contentInput.value = '';
        fileInput.value = '';
        await refreshMessages();
      });

      document.getElementById('new-conv-search').addEventListener('input', loadDoctorsForNewConversation);
      async function loadDoctorsForNewConversation() {
        var text = document.getElementById('new-conv-search').value;
        var doctors = await apiGet('/doctors' + (text ? '' : ''));
        var filtered = doctors.filter(function (d) {
          return !text || (d.first_name + ' ' + d.last_name).toLowerCase().indexOf(text.toLowerCase()) !== -1;
        });
        var list = document.getElementById('new-conv-doctor-list');
        list.innerHTML = '';
        filtered.forEach(function (d) {
          var row = document.createElement('div');
          row.className = 'select-row';
          row.innerHTML = '<div class="avatar avatar-44" data-avatar style="background:#10b981;">' + initials(d.first_name + ' ' + d.last_name) + '</div>' +
            '<div style="flex:1;"><div style="font-weight:700;">Dr. ' + d.first_name + ' ' + d.last_name + '</div>' +
            '<div style="color:var(--muted);font-size:13px;">' + d.specialty + '</div></div>';
          renderAvatar(row.querySelector('[data-avatar]'), d.photo_url);
          row.addEventListener('click', async function () {
            var conversation = await apiPost('/messaging/conversations', { doctor_id: d.id });
            document.getElementById('new-conversation-modal').style.display = 'none';
            await loadConversations();
            openThread(conversation);
          });
          list.appendChild(row);
        });
      }

      document.getElementById('new-conversation-btn').addEventListener('click', loadDoctorsForNewConversation);

      loadConversations();
    })();
  </script>
```

- [ ] **Step 4: Manual verification**

Log in as a patient with at least one validated doctor available. Open `patient/messages.html`, click "Nouveau", pick a doctor, verify the thread opens empty. Type a message, send it, verify it appears as a bubble. Log in as that doctor in a second browser/incognito window, open `medecin/messages.html` (once Task 22 is done) or verify via curl that `GET /messaging/conversations` for the doctor shows the new conversation with `patient_name` set.

- [ ] **Step 5: Commit**

```bash
git add frontend/patient/messages.html
git commit -m "feat: wire patient messaging page to the API (conversations, thread, new conversation)"
```

### Task 22: `medecin/messages.html` — conversations + thread (no "Nouveau")

**Files:**
- Modify: `frontend/medecin/messages.html`

- [ ] **Step 1: Replace the conversation list and empty-state pane**

Same structural replacement as Task 21 Step 1, applied to `medecin/messages.html`'s equivalent blocks (originally lines 102-118 for the list, 125-133 for the empty-state pane) — identical markup, since the page layout is shared:

```html
            <div style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:6px;min-height:0;" id="conversation-list"></div>
```

```html
          <div class="card" style="padding:0;display:flex;flex-direction:column;min-height:0;overflow:hidden;" id="thread-pane">
            <div id="thread-empty" style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--muted-2);padding:40px;text-align:center;">
              <svg width="54" height="54" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
              </svg>
              <div style="font-size:16px;font-weight:700;color:var(--muted);margin-top:14px;">Sélectionnez une conversation</div>
              <div style="font-size:14px;margin-top:4px;">Choisissez un contact dans la liste pour commencer à discuter.</div>
            </div>
            <div id="thread-active" style="display:none;flex-direction:column;flex:1;min-height:0;">
              <div class="row" id="thread-header" style="gap:12px;padding:16px;border-bottom:1px solid #f4f6f7;"></div>
              <div id="thread-messages" style="flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;"></div>
              <form id="thread-send-form" class="row" style="gap:8px;padding:12px 16px;border-top:1px solid #f4f6f7;">
                <input class="input" id="thread-content" placeholder="Écrire un message…" style="flex:1;">
                <input type="file" id="thread-file" style="display:none;">
                <button type="button" class="btn btn--ghost btn--sm" id="thread-attach">📎</button>
                <button type="submit" class="btn btn--primary btn--sm">Envoyer</button>
              </form>
            </div>
          </div>
```

Remove the "Nouveau" button entirely (originally lines 96-100) — a doctor cannot initiate a conversation (`POST /messaging/conversations` requires `get_current_patient`). Replace:

```html
            <div class="row" style="justify-content:space-between;margin-bottom:14px;">
              <div style="font-weight:800;font-size:15px;">Conversations</div>
            </div>
```

- [ ] **Step 2: Add the inline script**

Replace `  <script src="../app.js"></script>` with:

```html
  <script src="../auth.js"></script>
  <script src="../api.js"></script>
  <script src="../app.js"></script>
  <script>
    (function () {
      CarnetAuth.requireAuth('doctor');
      var activeConversationId = null;
      var pollTimer = null;

      function initials(name) {
        var parts = name.split(' ');
        return (parts[0][0] || '') + (parts[parts.length - 1][0] || '');
      }

      async function loadConversations() {
        var conversations = await apiGet('/messaging/conversations');
        var list = document.getElementById('conversation-list');
        list.innerHTML = '';
        conversations.forEach(function (c) {
          var item = document.createElement('div');
          item.className = 'conv-item';
          item.setAttribute('data-id', c.id);
          item.innerHTML =
            '<div class="avatar avatar-42" data-avatar style="background:#5b6ef5;">' + initials(c.patient_name) + '</div>' +
            '<div style="flex:1;min-width:0;"><div class="name">' + c.patient_name + '</div></div>';
          renderAvatar(item.querySelector('[data-avatar]'), c.patient_photo_url);
          item.addEventListener('click', function () { openThread(c); });
          list.appendChild(item);
        });
      }

      async function openThread(conversation) {
        activeConversationId = conversation.id;
        document.getElementById('thread-empty').style.display = 'none';
        document.getElementById('thread-active').style.display = 'flex';
        var header = document.getElementById('thread-header');
        header.innerHTML = '<div class="avatar avatar-42" data-avatar style="background:#5b6ef5;">' + initials(conversation.patient_name) + '</div>' +
          '<div style="font-weight:700;">' + conversation.patient_name + '</div>';
        renderAvatar(header.querySelector('[data-avatar]'), conversation.patient_photo_url);
        await refreshMessages();
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(refreshMessages, 4000);
      }

      async function refreshMessages() {
        if (!activeConversationId) return;
        var messages = await apiGet('/messaging/conversations/' + activeConversationId + '/messages');
        var container = document.getElementById('thread-messages');
        container.innerHTML = '';
        messages.forEach(function (m) {
          var bubble = document.createElement('div');
          var mine = m.sender_type === 'doctor';
          bubble.style.cssText = 'max-width:70%;padding:10px 14px;border-radius:14px;' +
            (mine ? 'align-self:flex-end;background:var(--green-soft);' : 'align-self:flex-start;background:var(--field);');
          bubble.textContent = m.content || '(pièce jointe)';
          if (m.file_key) {
            var link = document.createElement('a');
            link.href = '#';
            link.textContent = ' [voir la pièce jointe]';
            link.addEventListener('click', async function (e) {
              e.preventDefault();
              var result = await apiGet('/messaging/conversations/' + activeConversationId + '/messages/' + m.id + '/attachment');
              window.open(result.download_url, '_blank');
            });
            bubble.appendChild(link);
          }
          container.appendChild(bubble);
        });
        container.scrollTop = container.scrollHeight;
      }

      document.getElementById('thread-attach').addEventListener('click', function () {
        document.getElementById('thread-file').click();
      });

      document.getElementById('thread-send-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        if (!activeConversationId) return;
        var contentInput = document.getElementById('thread-content');
        var fileInput = document.getElementById('thread-file');
        var formData = new FormData();
        formData.append('content', contentInput.value);
        if (fileInput.files[0]) formData.append('file', fileInput.files[0]);
        await apiPostForm('/messaging/conversations/' + activeConversationId + '/messages', formData);
        contentInput.value = '';
        fileInput.value = '';
        await refreshMessages();
      });

      loadConversations();
    })();
  </script>
```

- [ ] **Step 3: Manual verification**

With the conversation created in Task 21's manual test, log in as that doctor, open `medecin/messages.html`: verify the conversation shows with the real patient name/photo. Open it, verify the patient's earlier message shows, send a reply, verify it appears. Back on the patient side, verify the reply shows up within ~4s (polling).

- [ ] **Step 4: Commit**

```bash
git add frontend/medecin/messages.html
git commit -m "feat: wire doctor messaging page to the API"
```

---

## Final check

- [ ] **Run the full backend suite one more time**

```bash
cd Backend-API
uv run python -m pytest -q
```

Expected: `47 passed` (37 original + 10 new across Tasks 4, 5, 6, 7, 14, 17, 18).

- [ ] **Update `README.md` / `docs/fonctionnement-application.md`**

Both currently state "les autres pages... affichent encore des données d'exemple codées en dur." Update the "État d'avancement" section of `README.md` and the "Ce qui n'est pas encore branché" section of `docs/fonctionnement-application.md` to reflect that the patient space and the covered doctor pages are now wired, keeping only `evaluations.html` and `patients-chroniques.html` (untouched by this plan) listed as still-mocked. Commit as `docs: update wiring status after patient/doctor frontend plan`.

---

## Explicitly out of scope (carried over from the spec)

- Sitewide sidebar avatar (every page's small logged-in-user avatar in the bottom-left) is not updated with the real photo — only the pages this plan touches (profil, carnet's summary has no avatar, messages, creer-ordonnance's patient list, dashboard's pending list) render real photos. Updating every other page's sidebar would require fetching the profile on pages this plan doesn't otherwise touch (`dashboard.html`, `evaluations.html`, `patients-chroniques.html`).
- Recurrence/bulk-generation of availability slots.
- Manual document categorization in the carnet (no backend field).
- "Envoyer à la pharmacie".
- WebSocket/real-time messaging (polling only, per the existing architecture decision).
- Pagination/sorting/advanced filters on any list.
- The symptom-checker chatbot (Mistral) — separate spec/plan.

"""End-to-end test harness.

Runs the real FastAPI app against an async SQLite database, with the two
external side-effects (S3 storage and Resend email) stubbed at a single point
each so nothing touches the network:
  - core.storage._s3_client -> a fake client (upload_file/get_file_url read this
    module global at call time, so every caller is covered by one patch).
  - features.Notifications.logic.send_email -> a no-op (all notify_* go through it).
"""

import os
import tempfile

# Settings are read at import time and have no defaults, so the environment must
# be populated before anything under core/ or features/ is imported.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-32b"
os.environ["S3_ENDPOINT_URL"] = "http://localhost:9000"
os.environ["S3_ACCESS_KEY"] = "test"
os.environ["S3_SECRET_KEY"] = "test"
os.environ["S3_BUCKET_NAME"] = "test-bucket"
os.environ["RESEND_API_KEY"] = "test"
os.environ["EMAIL_FROM_ADDRESS"] = "noreply@example.com"
os.environ["FRONTEND_BASE_URL"] = "http://localhost:3000"

from datetime import date, timedelta  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

import core.storage as storage  # noqa: E402
import features.Notifications.logic as notifications  # noqa: E402
from app import app  # noqa: E402
from core.database import Base, async_session_factory, engine  # noqa: E402
from core.security import hash_password  # noqa: E402
from features.Auth.models import Admin, EmailVerificationToken  # noqa: E402


class _FakeS3Client:
    """Records nothing; just satisfies the calls core.storage makes."""

    def head_bucket(self, **kwargs):
        return {}  # pretend the bucket exists so ensure_bucket_exists is a no-op

    def put_object(self, **kwargs):
        return {}

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"https://fake-s3.local/{Params['Key']}?expires={ExpiresIn}"

    def delete_object(self, **kwargs):
        return {}


storage._s3_client = _FakeS3Client()
notifications.send_email = lambda *args, **kwargs: None


@pytest_asyncio.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _patient_payload(email: str) -> dict:
    return {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "date_of_birth": "1990-05-10",
        "place_of_birth": "London",
        "address": "1 Analytical St",
        "phone_number": "+33123456789",
        "country_of_residence": "France",
        "gender": "femme",
        "city": "Paris",
        "email": email,
        "password": "supersecret1",
        "password_confirmation": "supersecret1",
    }


def _doctor_payload(email: str, fee: float = 50.0) -> dict:
    return {
        "first_name": "Gregory",
        "last_name": "House",
        "date_of_birth": "1975-03-15",
        "place_of_birth": "Princeton",
        "email": email,
        "phone_number": "+33111111111",
        "country_of_residence": "France",
        "gender": "homme",
        "city": "Paris",
        "password": "diagnostics1",
        "password_confirmation": "diagnostics1",
        "specialty": "Cardiology",
        "license_number": f"LIC-{email}",
        "practice_name": "City Clinic",
        "consultation_fee": fee,
    }


async def register_and_login_patient(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/patients/register", json=_patient_payload(email))
    assert resp.status_code == 201, resp.text
    patient_id = resp.json()["id"]

    async with async_session_factory() as session:
        token_row = (
            await session.scalars(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.user_id == patient_id
                )
            )
        ).first()
    confirm = await client.post(
        "/auth/patients/confirm-email", json={"token": token_row.token}
    )
    assert confirm.status_code == 200, confirm.text

    login = await client.post(
        "/auth/patients/login", json={"email": email, "password": "supersecret1"}
    )
    assert login.status_code == 200, login.text
    return {"id": patient_id, "token": login.json()["access_token"], "email": email}


@pytest.fixture
def auth():
    return _auth


@pytest_asyncio.fixture
async def admin_token(client):
    async with async_session_factory() as session:
        session.add(
            Admin(
                first_name="Root",
                last_name="Admin",
                email="admin@example.com",
                password_hash=hash_password("adminpassword1"),
            )
        )
        await session.commit()
    login = await client.post(
        "/auth/admin/login",
        json={"email": "admin@example.com", "password": "adminpassword1"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest_asyncio.fixture
async def patient(client):
    return await register_and_login_patient(client, "patient@example.com")


@pytest_asyncio.fixture
async def validated_doctor(client, admin_token):
    email = "doctor@example.com"
    reg = await client.post(
        "/auth/doctors/register", json=_doctor_payload(email, fee=50.0)
    )
    assert reg.status_code == 201, reg.text
    doctor_id = reg.json()["id"]

    login = await client.post(
        "/auth/doctors/login", json={"email": email, "password": "diagnostics1"}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    diploma = await client.post(
        "/auth/doctors/me/diploma",
        files={"diploma_file": ("diploma.pdf", b"%PDF-fake", "application/pdf")},
        headers=_auth(token),
    )
    assert diploma.status_code == 200, diploma.text

    decision = await client.post(
        f"/admin/doctors/{doctor_id}/validate",
        json={"approve": True},
        headers=_auth(admin_token),
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "validated"

    return {"id": doctor_id, "token": token, "email": email, "fee": 50.0}


@pytest_asyncio.fixture
async def completed_appointment(client, patient, validated_doctor):
    """A full booked -> confirmed -> completed appointment, the precondition for
    prescriptions and reviews. Returns the appointment id plus the actors."""
    doctor_headers = _auth(validated_doctor["token"])
    patient_headers = _auth(patient["token"])

    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "09:00:00",
            "end_time": "09:30:00",
        },
        headers=doctor_headers,
    )
    assert slot.status_code == 201, slot.text
    availability_id = slot.json()["id"]

    booking = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=patient_headers,
    )
    assert booking.status_code == 201, booking.text
    appointment_id = booking.json()["id"]

    confirm = await client.post(
        f"/appointments/{appointment_id}/decision",
        json={"approve": True},
        headers=doctor_headers,
    )
    assert confirm.status_code == 200, confirm.text

    complete = await client.post(
        f"/appointments/{appointment_id}/complete", headers=doctor_headers
    )
    assert complete.status_code == 200, complete.text

    return {
        "appointment_id": appointment_id,
        "availability_id": availability_id,
        "patient": patient,
        "doctor": validated_doctor,
    }

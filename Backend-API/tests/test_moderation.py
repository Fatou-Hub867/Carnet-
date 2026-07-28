"""Reviews, complaint-driven suspension, and lazy reactivation at login."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from core.database import async_session_factory
from features.Auth.models import Doctor, DoctorStatus
from tests.conftest import _auth


async def _doctor_status(doctor_id: int) -> DoctorStatus:
    async with async_session_factory() as session:
        doctor = await session.get(Doctor, doctor_id)
        return doctor.status


async def test_review_requires_completed_and_is_unique(client, completed_appointment):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]
    payload = {
        "doctor_id": doctor["id"],
        "appointment_id": completed_appointment["appointment_id"],
        "rating": 5,
        "comment": "Excellent",
    }
    first = await client.post(
        f"/doctors/{doctor['id']}/reviews", json=payload, headers=_auth(patient["token"])
    )
    assert first.status_code == 201

    duplicate = await client.post(
        f"/doctors/{doctor['id']}/reviews", json=payload, headers=_auth(patient["token"])
    )
    assert duplicate.status_code == 409


async def test_path_body_doctor_mismatch_rejected(client, completed_appointment):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]
    resp = await client.post(
        f"/doctors/{doctor['id']}/reviews",
        json={
            "doctor_id": doctor["id"] + 999,
            "appointment_id": completed_appointment["appointment_id"],
            "rating": 4,
        },
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 400


async def test_fifth_complaint_suspends_doctor(client, patient, validated_doctor):
    doctor_id = validated_doctor["id"]
    payload = {"doctor_id": doctor_id, "reason": "late", "description": "always late"}

    for _ in range(4):
        resp = await client.post(
            f"/doctors/{doctor_id}/complaints", json=payload, headers=_auth(patient["token"])
        )
        assert resp.status_code == 201
    assert await _doctor_status(doctor_id) == DoctorStatus.VALIDATED  # not yet

    fifth = await client.post(
        f"/doctors/{doctor_id}/complaints", json=payload, headers=_auth(patient["token"])
    )
    assert fifth.status_code == 201
    assert await _doctor_status(doctor_id) == DoctorStatus.SUSPENDED


async def test_expired_suspension_reactivates_on_login(client, patient, validated_doctor):
    doctor_id = validated_doctor["id"]
    payload = {"doctor_id": doctor_id, "reason": "x", "description": "y"}
    for _ in range(5):
        await client.post(
            f"/doctors/{doctor_id}/complaints", json=payload, headers=_auth(patient["token"])
        )
    assert await _doctor_status(doctor_id) == DoctorStatus.SUSPENDED

    # Force the suspension window into the past.
    async with async_session_factory() as session:
        doctor = await session.get(Doctor, doctor_id)
        doctor.suspended_until = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()

    # Logging in triggers the lazy reactivation sweep.
    login = await client.post(
        "/auth/doctors/login", json={"email": validated_doctor["email"], "password": "diagnostics1"}
    )
    assert login.status_code == 200
    assert await _doctor_status(doctor_id) == DoctorStatus.VALIDATED


async def test_reactivated_doctor_needs_a_fresh_batch_to_resuspend(client, patient, validated_doctor):
    doctor_id = validated_doctor["id"]
    payload = {"doctor_id": doctor_id, "reason": "x", "description": "y"}

    # First cycle: 5 complaints -> suspended.
    for _ in range(5):
        await client.post(
            f"/doctors/{doctor_id}/complaints", json=payload, headers=_auth(patient["token"])
        )
    assert await _doctor_status(doctor_id) == DoctorStatus.SUSPENDED

    # Expire the suspension and reactivate via login.
    async with async_session_factory() as session:
        doctor = await session.get(Doctor, doctor_id)
        doctor.suspended_until = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()
    await client.post(
        "/auth/doctors/login", json={"email": validated_doctor["email"], "password": "diagnostics1"}
    )
    assert await _doctor_status(doctor_id) == DoctorStatus.VALIDATED

    # The old batch is now RESOLVED: one new complaint must NOT re-suspend.
    await client.post(f"/doctors/{doctor_id}/complaints", json=payload, headers=_auth(patient["token"]))
    assert await _doctor_status(doctor_id) == DoctorStatus.VALIDATED

    # A fresh set of 5 active complaints is required again.
    for _ in range(4):
        await client.post(
            f"/doctors/{doctor_id}/complaints", json=payload, headers=_auth(patient["token"])
        )
    assert await _doctor_status(doctor_id) == DoctorStatus.SUSPENDED


async def test_admin_soft_deletes_patient(client, admin_token, patient):
    resp = await client.request(
        "DELETE",
        f"/admin/patient/{patient['id']}",
        json={"reason": "user request"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 204

    # Soft-deleted patient can no longer authenticate.
    login = await client.post(
        "/auth/patients/login", json={"email": patient["email"], "password": "supersecret1"}
    )
    assert login.status_code == 401

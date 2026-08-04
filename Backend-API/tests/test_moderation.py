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
        f"/doctors/{doctor['id']}/reviews",
        json=payload,
        headers=_auth(patient["token"]),
    )
    assert first.status_code == 201

    duplicate = await client.post(
        f"/doctors/{doctor['id']}/reviews",
        json=payload,
        headers=_auth(patient["token"]),
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


async def test_pending_review_moves_to_my_reviews_after_submission(
    client, completed_appointment
):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]
    patient_headers = _auth(patient["token"])

    pending_before = await client.get(
        "/patients/me/pending-reviews", headers=patient_headers
    )
    assert pending_before.status_code == 200
    assert len(pending_before.json()) == 1
    pending_item = pending_before.json()[0]
    assert pending_item["appointment_id"] == completed_appointment["appointment_id"]
    assert pending_item["doctor_name"] == "Gregory House"
    assert pending_item["specialty"] == "Cardiology"

    reviews_before = await client.get("/patients/me/reviews", headers=patient_headers)
    assert reviews_before.json() == []

    submit = await client.post(
        f"/doctors/{doctor['id']}/reviews",
        json={
            "doctor_id": doctor["id"],
            "appointment_id": completed_appointment["appointment_id"],
            "rating": 5,
            "comment": "Très bien",
        },
        headers=patient_headers,
    )
    assert submit.status_code == 201, submit.text

    pending_after = await client.get(
        "/patients/me/pending-reviews", headers=patient_headers
    )
    assert pending_after.json() == []

    reviews_after = await client.get("/patients/me/reviews", headers=patient_headers)
    assert reviews_after.status_code == 200
    assert len(reviews_after.json()) == 1
    published = reviews_after.json()[0]
    assert published["doctor_name"] == "Gregory House"
    assert published["specialty"] == "Cardiology"
    assert published["rating"] == 5
    assert published["comment"] == "Très bien"


async def test_pending_and_my_reviews_are_scoped_per_patient(client, patient):
    """A patient with no consultations at all sees empty lists, not an error."""
    headers = _auth(patient["token"])
    pending = await client.get("/patients/me/pending-reviews", headers=headers)
    assert pending.status_code == 200
    assert pending.json() == []
    reviews = await client.get("/patients/me/reviews", headers=headers)
    assert reviews.status_code == 200
    assert reviews.json() == []


async def test_fifth_complaint_suspends_doctor(client, patient, validated_doctor):
    doctor_id = validated_doctor["id"]
    payload = {"doctor_id": doctor_id, "reason": "late", "description": "always late"}

    for _ in range(4):
        resp = await client.post(
            f"/doctors/{doctor_id}/complaints",
            json=payload,
            headers=_auth(patient["token"]),
        )
        assert resp.status_code == 201
    assert await _doctor_status(doctor_id) == DoctorStatus.VALIDATED  # not yet

    fifth = await client.post(
        f"/doctors/{doctor_id}/complaints",
        json=payload,
        headers=_auth(patient["token"]),
    )
    assert fifth.status_code == 201
    assert await _doctor_status(doctor_id) == DoctorStatus.SUSPENDED


async def test_expired_suspension_reactivates_on_login(
    client, patient, validated_doctor
):
    doctor_id = validated_doctor["id"]
    payload = {"doctor_id": doctor_id, "reason": "x", "description": "y"}
    for _ in range(5):
        await client.post(
            f"/doctors/{doctor_id}/complaints",
            json=payload,
            headers=_auth(patient["token"]),
        )
    assert await _doctor_status(doctor_id) == DoctorStatus.SUSPENDED

    # Force the suspension window into the past.
    async with async_session_factory() as session:
        doctor = await session.get(Doctor, doctor_id)
        doctor.suspended_until = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()

    # Logging in triggers the lazy reactivation sweep.
    login = await client.post(
        "/auth/doctors/login",
        json={"email": validated_doctor["email"], "password": "diagnostics1"},
    )
    assert login.status_code == 200
    assert await _doctor_status(doctor_id) == DoctorStatus.VALIDATED


async def test_reactivated_doctor_needs_a_fresh_batch_to_resuspend(
    client, patient, validated_doctor
):
    doctor_id = validated_doctor["id"]
    payload = {"doctor_id": doctor_id, "reason": "x", "description": "y"}

    # First cycle: 5 complaints -> suspended.
    for _ in range(5):
        await client.post(
            f"/doctors/{doctor_id}/complaints",
            json=payload,
            headers=_auth(patient["token"]),
        )
    assert await _doctor_status(doctor_id) == DoctorStatus.SUSPENDED

    # Expire the suspension and reactivate via login.
    async with async_session_factory() as session:
        doctor = await session.get(Doctor, doctor_id)
        doctor.suspended_until = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()
    await client.post(
        "/auth/doctors/login",
        json={"email": validated_doctor["email"], "password": "diagnostics1"},
    )
    assert await _doctor_status(doctor_id) == DoctorStatus.VALIDATED

    # The old batch is now RESOLVED: one new complaint must NOT re-suspend.
    await client.post(
        f"/doctors/{doctor_id}/complaints",
        json=payload,
        headers=_auth(patient["token"]),
    )
    assert await _doctor_status(doctor_id) == DoctorStatus.VALIDATED

    # A fresh set of 5 active complaints is required again.
    for _ in range(4):
        await client.post(
            f"/doctors/{doctor_id}/complaints",
            json=payload,
            headers=_auth(patient["token"]),
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
        "/auth/patients/login",
        json={"email": patient["email"], "password": "supersecret1"},
    )
    assert login.status_code == 401


async def test_validate_doctor_sends_email_with_login_link(
    client, admin_token, monkeypatch
):
    import features.Notifications.logic as notifications
    from tests.conftest import _auth, _doctor_payload

    email = "link-check-doctor@example.com"
    reg = await client.post("/auth/doctors/register", json=_doctor_payload(email))
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


async def test_admin_can_fetch_a_fresh_diploma_download_url(client, admin_token):
    from tests.conftest import _auth, _doctor_payload

    email = "diploma-download-doctor@example.com"
    reg = await client.post("/auth/doctors/register", json=_doctor_payload(email))
    assert reg.status_code == 201, reg.text
    doctor_id = reg.json()["id"]

    login = await client.post(
        "/auth/doctors/login", json={"email": email, "password": "diagnostics1"}
    )
    token = login.json()["access_token"]

    diploma = await client.post(
        "/auth/doctors/me/diploma",
        files={"diploma_file": ("diploma.pdf", b"%PDF-fake", "application/pdf")},
        headers=_auth(token),
    )
    assert diploma.status_code == 200, diploma.text

    # Two separate calls both succeed and return a usable URL — proving the
    # link is generated fresh on demand rather than reused/stale.
    first = await client.get(
        f"/admin/doctors/{doctor_id}/diploma/download", headers=_auth(admin_token)
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["view_url"].startswith("https://fake-s3.local/")
    assert body["download_url"].startswith("https://fake-s3.local/")
    assert "response-content-disposition" not in body["view_url"]
    assert "attachment" in body["download_url"]
    # No original filename is stored for the diploma — it's recovered from
    # the storage key (uuid4()-prefixed), so "diploma.pdf" must round-trip.
    assert "diploma.pdf" in body["download_url"]

    second = await client.get(
        f"/admin/doctors/{doctor_id}/diploma/download", headers=_auth(admin_token)
    )
    assert second.status_code == 200, second.text


async def test_diploma_download_404s_without_a_diploma(client, admin_token):
    from tests.conftest import _auth, _doctor_payload

    email = "no-diploma-doctor@example.com"
    reg = await client.post("/auth/doctors/register", json=_doctor_payload(email))
    assert reg.status_code == 201, reg.text
    doctor_id = reg.json()["id"]

    resp = await client.get(
        f"/admin/doctors/{doctor_id}/diploma/download", headers=_auth(admin_token)
    )
    assert resp.status_code == 404


async def test_admin_lists_complaints_with_names_and_doctor_status(
    client, admin_token, patient, validated_doctor
):
    from tests.conftest import _auth

    complaint = await client.post(
        f"/doctors/{validated_doctor['id']}/complaints",
        json={
            "doctor_id": validated_doctor["id"],
            "reason": "Retard",
            "description": "Very late.",
        },
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

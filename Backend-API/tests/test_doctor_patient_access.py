"""A doctor may read a patient's carnet (summary, documents, vitals,
vaccinations) once they have a confirmed or completed appointment together —
a merely pending appointment, or no relationship at all, must not grant
access. The same rule gates a doctor depositing a document into a patient's
carnet (POST .../documents), previously ungated."""

from datetime import date

from tests.conftest import _auth


async def test_doctor_can_read_carnet_with_confirmed_but_not_yet_completed_appointment(
    client, patient, validated_doctor
):
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
    booking = await client.post(
        "/appointments",
        json={"availability_id": slot.json()["id"], "mode": "in_person"},
        headers=patient_headers,
    )
    confirm = await client.post(
        f"/appointments/{booking.json()['id']}/decision",
        json={"approve": True},
        headers=doctor_headers,
    )
    assert confirm.status_code == 200, confirm.text

    resp = await client.get(
        f"/health-records/patients/{patient['id']}", headers=doctor_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["first_name"] == "Ada"


async def test_pending_appointment_does_not_grant_access(
    client, patient, validated_doctor
):
    doctor_headers = _auth(validated_doctor["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "10:00:00",
            "end_time": "10:30:00",
        },
        headers=doctor_headers,
    )
    await client.post(
        "/appointments",
        json={"availability_id": slot.json()["id"], "mode": "in_person"},
        headers=_auth(patient["token"]),
    )
    # Never confirmed — still pending.
    resp = await client.get(
        f"/health-records/patients/{patient['id']}", headers=doctor_headers
    )
    assert resp.status_code == 404


async def test_doctor_without_any_relationship_gets_404(
    client, patient, validated_doctor
):
    resp = await client.get(
        f"/health-records/patients/{patient['id']}",
        headers=_auth(validated_doctor["token"]),
    )
    assert resp.status_code == 404


async def test_doctor_reads_documents_vitals_and_vaccinations(
    client, completed_appointment
):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]
    doctor_headers = _auth(doctor["token"])
    patient_headers = _auth(patient["token"])

    await client.post(
        "/health-records/me/documents",
        files={"file": ("scan.pdf", b"%PDF-scan", "application/pdf")},
        headers=patient_headers,
    )
    await client.post(
        "/health-records/me/vitals",
        json={"heart_rate_bpm": 71},
        headers=patient_headers,
    )
    await client.post(
        "/health-records/me/vaccinations",
        json={
            "vaccine_name": "Tétanos",
            "dose_number": 1,
            "administered_at": "2023-05-01",
        },
        headers=patient_headers,
    )

    docs = await client.get(
        f"/health-records/patients/{patient['id']}/documents", headers=doctor_headers
    )
    assert docs.status_code == 200
    assert len(docs.json()) == 1
    document_id = docs.json()[0]["id"]

    download = await client.get(
        f"/health-records/patients/{patient['id']}/documents/{document_id}/download",
        headers=doctor_headers,
    )
    assert download.status_code == 200
    body = download.json()
    assert body["view_url"].startswith("https://fake-s3.local/")
    assert body["download_url"].startswith("https://fake-s3.local/")
    # The download variant carries a forced-attachment disposition with the
    # original filename; the view variant renders inline (no override).
    assert "response-content-disposition" not in body["view_url"]
    assert "attachment" in body["download_url"]
    assert "scan.pdf" in body["download_url"]

    vitals = await client.get(
        f"/health-records/patients/{patient['id']}/vitals", headers=doctor_headers
    )
    assert vitals.status_code == 200
    assert vitals.json()["heart_rate"]["value"] == 71.0

    vaccinations = await client.get(
        f"/health-records/patients/{patient['id']}/vaccinations",
        headers=doctor_headers,
    )
    assert vaccinations.status_code == 200
    assert vaccinations.json()[0]["vaccine_name"] == "Tétanos"


async def test_document_download_also_requires_the_relationship(
    client, admin_token, completed_appointment
):
    """A second, validated-but-unrelated doctor must not be able to read the
    same patient's documents even by guessing the patient_id — proving the
    authorization check is applied on every doctor-facing route, not just
    the summary one."""
    from tests.conftest import _doctor_payload

    patient = completed_appointment["patient"]

    email = "unrelated-doctor@example.com"
    reg = await client.post("/auth/doctors/register", json=_doctor_payload(email))
    other_doctor_id = reg.json()["id"]
    login = await client.post(
        "/auth/doctors/login", json={"email": email, "password": "diagnostics1"}
    )
    other_doctor_token = login.json()["access_token"]
    await client.post(
        "/auth/doctors/me/diploma",
        files={"diploma_file": ("diploma.pdf", b"%PDF-fake", "application/pdf")},
        headers=_auth(other_doctor_token),
    )
    await client.post(
        f"/admin/doctors/{other_doctor_id}/validate",
        json={"approve": True},
        headers=_auth(admin_token),
    )

    resp = await client.get(
        f"/health-records/patients/{patient['id']}/vitals",
        headers=_auth(other_doctor_token),
    )
    assert resp.status_code == 404


async def test_doctor_can_upload_a_document_for_a_patient_they_treat(
    client, completed_appointment
):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]

    resp = await client.post(
        f"/health-records/patients/{patient['id']}/documents",
        files={"file": ("labs.pdf", b"%PDF-labs", "application/pdf")},
        headers=_auth(doctor["token"]),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["source_type"] == "doctor_upload"


async def test_unrelated_doctor_cannot_upload_a_document_for_a_patient(
    client, admin_token, completed_appointment
):
    """Previously ungated: any authenticated doctor could deposit a document
    into any patient's carnet regardless of ever having treated them."""
    from tests.conftest import _doctor_payload

    patient = completed_appointment["patient"]

    email = "no-relationship-doctor@example.com"
    reg = await client.post("/auth/doctors/register", json=_doctor_payload(email))
    other_doctor_id = reg.json()["id"]
    login = await client.post(
        "/auth/doctors/login", json={"email": email, "password": "diagnostics1"}
    )
    other_doctor_token = login.json()["access_token"]
    await client.post(
        "/auth/doctors/me/diploma",
        files={"diploma_file": ("diploma.pdf", b"%PDF-fake", "application/pdf")},
        headers=_auth(other_doctor_token),
    )
    await client.post(
        f"/admin/doctors/{other_doctor_id}/validate",
        json={"approve": True},
        headers=_auth(admin_token),
    )

    resp = await client.post(
        f"/health-records/patients/{patient['id']}/documents",
        files={"file": ("labs.pdf", b"%PDF-labs", "application/pdf")},
        headers=_auth(other_doctor_token),
    )
    assert resp.status_code == 404


async def test_my_patients_lists_confirmed_relationship_without_a_conversation(
    client, patient, validated_doctor
):
    """GET /doctors/me/patients must not require a messaging conversation —
    it's used to populate pickers (e.g. chronic-care follow-up creation) for
    any patient the doctor has an accepted appointment with."""
    doctor_headers = _auth(validated_doctor["token"])
    patient_headers = _auth(patient["token"])

    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "10:00:00",
            "end_time": "10:30:00",
        },
        headers=doctor_headers,
    )
    booking = await client.post(
        "/appointments",
        json={"availability_id": slot.json()["id"], "mode": "in_person"},
        headers=patient_headers,
    )
    confirm = await client.post(
        f"/appointments/{booking.json()['id']}/decision",
        json={"approve": True},
        headers=doctor_headers,
    )
    assert confirm.status_code == 200, confirm.text

    resp = await client.get("/doctors/me/patients", headers=doctor_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == [
        {"patient_id": patient["id"], "patient_name": "Ada Lovelace"}
    ]


async def test_my_patients_excludes_pending_only_relationship(
    client, patient, validated_doctor
):
    doctor_headers = _auth(validated_doctor["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "11:00:00",
            "end_time": "11:30:00",
        },
        headers=doctor_headers,
    )
    await client.post(
        "/appointments",
        json={"availability_id": slot.json()["id"], "mode": "in_person"},
        headers=_auth(patient["token"]),
    )

    resp = await client.get("/doctors/me/patients", headers=doctor_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == []

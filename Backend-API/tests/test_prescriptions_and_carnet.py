"""Prescription creation drives PDF generation, treatment rows, and the
automatic health-record entry; messaging attachments from a doctor do too."""

from datetime import date, timedelta

from tests.conftest import _auth


async def _prescribe(client, completed_appointment):
    doctor = completed_appointment["doctor"]
    payload = {
        "appointment_id": completed_appointment["appointment_id"],
        "notes": "Rest and hydrate. Café ☕ (non-latin-1 on purpose)",
        "treatments": [
            {
                "medication_name": "Aspirin",
                "dosage": "500mg",
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=5)).isoformat(),
                "intake_times": ["08:00:00", "20:00:00"],
            }
        ],
    }
    return await client.post(
        "/prescriptions", json=payload, headers=_auth(doctor["token"])
    )


async def test_prescription_requires_completed_appointment(
    client, patient, validated_doctor
):
    from datetime import date as _date

    doctor_headers = _auth(validated_doctor["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": _date.today().isoformat(),
            "start_time": "09:00:00",
            "end_time": "09:30:00",
        },
        headers=doctor_headers,
    )
    booking = await client.post(
        "/appointments",
        json={"availability_id": slot.json()["id"], "mode": "in_person"},
        headers=_auth(patient["token"]),
    )
    # Still pending, not completed -> prescribing is refused.
    resp = await client.post(
        "/prescriptions",
        json={"appointment_id": booking.json()["id"], "notes": None, "treatments": []},
        headers=doctor_headers,
    )
    assert resp.status_code == 409


async def test_prescription_creates_pdf_and_files_it_in_carnet(
    client, completed_appointment
):
    patient = completed_appointment["patient"]

    before = await client.get("/health-records/me", headers=_auth(patient["token"]))
    count_before = before.json()["document_count"]

    resp = await _prescribe(client, completed_appointment)
    assert resp.status_code == 201, resp.text

    # Patient sees the prescription and can get a (fake) presigned download URL.
    listing = await client.get("/prescriptions", headers=_auth(patient["token"]))
    assert len(listing.json()) == 1
    prescription_id = listing.json()[0]["id"]
    download = await client.get(
        f"/prescriptions/{prescription_id}/download", headers=_auth(patient["token"])
    )
    assert download.status_code == 200
    assert download.json()["download_url"].startswith("https://fake-s3.local/")

    # The prescription PDF was auto-filed in the health record.
    after = await client.get("/health-records/me", headers=_auth(patient["token"]))
    assert after.json()["document_count"] == count_before + 1
    docs = await client.get(
        "/health-records/me/documents", headers=_auth(patient["token"])
    )
    sources = [d["source_type"] for d in docs.json()]
    assert "prescription" in sources


async def test_patient_can_confirm_a_dose(client, completed_appointment):
    patient = completed_appointment["patient"]
    await _prescribe(client, completed_appointment)

    dashboard = await client.get(
        "/patients/me/dashboard", headers=_auth(patient["token"])
    )
    assert dashboard.status_code == 200
    doses = dashboard.json()["today_doses"]
    assert len(doses) == 2  # two intake times
    assert dashboard.json()["active_treatments"][0]["medication_name"] == "Aspirin"


async def test_doctor_message_attachment_lands_in_carnet(client, completed_appointment):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]

    convo = await client.post(
        "/messaging/conversations",
        json={"doctor_id": doctor["id"]},
        headers=_auth(patient["token"]),
    )
    assert convo.status_code == 201
    conversation_id = convo.json()["id"]

    before = (
        await client.get("/health-records/me", headers=_auth(patient["token"]))
    ).json()["document_count"]

    # Doctor sends an attachment -> auto-filed in the patient's carnet.
    sent = await client.post(
        f"/messaging/conversations/{conversation_id}/messages",
        data={"content": "Here is your lab result"},
        files={"file": ("labs.pdf", b"%PDF-labs", "application/pdf")},
        headers=_auth(doctor["token"]),
    )
    assert sent.status_code == 201

    after = (
        await client.get("/health-records/me", headers=_auth(patient["token"]))
    ).json()["document_count"]
    assert after == before + 1
    docs = await client.get(
        "/health-records/me/documents", headers=_auth(patient["token"])
    )
    assert any(d["source_type"] == "message" for d in docs.json())


async def test_patient_message_attachment_not_filed(client, completed_appointment):
    # Only doctor attachments are auto-filed; a patient's attachment is not.
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]
    convo = await client.post(
        "/messaging/conversations",
        json={"doctor_id": doctor["id"]},
        headers=_auth(patient["token"]),
    )
    conversation_id = convo.json()["id"]
    before = (
        await client.get("/health-records/me", headers=_auth(patient["token"]))
    ).json()["document_count"]

    await client.post(
        f"/messaging/conversations/{conversation_id}/messages",
        data={"content": "my own scan"},
        files={"file": ("scan.pdf", b"%PDF-scan", "application/pdf")},
        headers=_auth(patient["token"]),
    )
    after = (
        await client.get("/health-records/me", headers=_auth(patient["token"]))
    ).json()["document_count"]
    assert after == before


async def test_messages_marked_read_on_fetch(client, completed_appointment):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]
    convo = await client.post(
        "/messaging/conversations",
        json={"doctor_id": doctor["id"]},
        headers=_auth(patient["token"]),
    )
    conversation_id = convo.json()["id"]

    await client.post(
        f"/messaging/conversations/{conversation_id}/messages",
        data={"content": "hello doctor"},
        headers=_auth(patient["token"]),
    )
    # Doctor fetches the thread -> the patient's message is marked read.
    fetched = await client.get(
        f"/messaging/conversations/{conversation_id}/messages",
        headers=_auth(doctor["token"]),
    )
    assert fetched.status_code == 200
    # Re-fetch to observe the persisted read_at (the first fetch set it).
    again = await client.get(
        f"/messaging/conversations/{conversation_id}/messages",
        headers=_auth(doctor["token"]),
    )
    assert again.json()[0]["read_at"] is not None


async def test_health_record_summary_includes_weight(client, patient):
    await client.patch(
        "/patients/me", json={"weight_kg": 72.0}, headers=_auth(patient["token"])
    )
    resp = await client.get("/health-records/me", headers=_auth(patient["token"]))
    assert resp.status_code == 200
    assert resp.json()["weight_kg"] == 72.0


async def test_conversation_out_includes_names_and_photos(
    client, completed_appointment
):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]
    await client.post(
        "/doctors/me/photo",
        files={"photo": ("doc.jpg", b"\xff\xd8\xfffake", "image/jpeg")},
        headers=_auth(doctor["token"]),
    )

    convo = await client.post(
        "/messaging/conversations",
        json={"doctor_id": doctor["id"]},
        headers=_auth(patient["token"]),
    )
    assert convo.status_code == 201, convo.text
    body = convo.json()
    assert body["patient_name"] == "Ada Lovelace"
    assert body["doctor_name"] == "Gregory House"
    assert body["doctor_photo_url"].startswith("https://fake-s3.local/")
    assert body["patient_photo_url"] is None

    listing = await client.get(
        "/messaging/conversations", headers=_auth(doctor["token"])
    )
    assert listing.status_code == 200
    assert listing.json()[0]["patient_name"] == "Ada Lovelace"


async def test_get_or_create_conversation_is_idempotent(client, completed_appointment):
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]

    first = await client.post(
        "/messaging/conversations",
        json={"doctor_id": doctor["id"]},
        headers=_auth(patient["token"]),
    )
    assert first.status_code == 201, first.text
    first_body = first.json()

    second = await client.post(
        "/messaging/conversations",
        json={"doctor_id": doctor["id"]},
        headers=_auth(patient["token"]),
    )
    assert second.status_code == 201, second.text
    second_body = second.json()

    assert second_body["id"] == first_body["id"]
    assert second_body["patient_name"] == "Ada Lovelace"
    assert second_body["doctor_name"] == "Gregory House"

"""Booking workflow: availability, double-booking guard, fee snapshot, calendar."""

from datetime import date

from tests.conftest import _auth, register_and_login_patient


async def test_search_only_returns_validated_doctor(client, validated_doctor):
    resp = await client.get("/doctors", params={"specialty": "Cardio"})
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert validated_doctor["id"] in ids


async def test_pending_doctor_hidden_from_search(client, admin_token):
    # Register a doctor but never validate it.
    from tests.conftest import _doctor_payload

    reg = await client.post(
        "/auth/doctors/register", json=_doctor_payload("pending@example.com")
    )
    assert reg.status_code == 201
    resp = await client.get("/doctors")
    assert reg.json()["id"] not in [d["id"] for d in resp.json()]


async def test_fee_is_snapshotted_on_confirmation(client, patient, validated_doctor):
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
    availability_id = slot.json()["id"]

    booking = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=patient_headers,
    )
    assert booking.status_code == 201
    body = booking.json()
    assert body["status"] == "pending"
    assert body["amount"] is None  # not billed until confirmed

    confirm = await client.post(
        f"/appointments/{body['id']}/decision",
        json={"approve": True},
        headers=doctor_headers,
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"
    assert confirm.json()["amount"] == validated_doctor["fee"]


async def test_double_booking_is_rejected(client, patient, validated_doctor):
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
    availability_id = slot.json()["id"]

    first = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=_auth(patient["token"]),
    )
    assert first.status_code == 201

    other_patient = await register_and_login_patient(client, "other@example.com")
    second = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=_auth(other_patient["token"]),
    )
    assert second.status_code == 409


async def test_refusal_frees_the_slot(client, patient, validated_doctor):
    doctor_headers = _auth(validated_doctor["token"])
    patient_headers = _auth(patient["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "12:00:00",
            "end_time": "12:30:00",
        },
        headers=doctor_headers,
    )
    availability_id = slot.json()["id"]

    booking = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=patient_headers,
    )
    await client.post(
        f"/appointments/{booking.json()['id']}/decision",
        json={"approve": False},
        headers=doctor_headers,
    )

    # The slot is bookable again after refusal.
    avail = await client.get(
        f"/appointments/doctors/{validated_doctor['id']}/availabilities",
        params={"from_date": date.today().isoformat()},
    )
    assert availability_id in [a["id"] for a in avail.json()]


async def test_overlapping_availability_rejected(client, validated_doctor):
    doctor_headers = _auth(validated_doctor["token"])
    base = {
        "date": date.today().isoformat(),
        "start_time": "14:00:00",
        "end_time": "15:00:00",
    }
    first = await client.post(
        "/appointments/availabilities", json=base, headers=doctor_headers
    )
    assert first.status_code == 201
    overlap = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "14:30:00",
            "end_time": "15:30:00",
        },
        headers=doctor_headers,
    )
    assert overlap.status_code == 409


async def test_calendar_shows_confirmed_visit(client, patient, validated_doctor):
    # The calendar lists confirmed consultations for a day.
    doctor_headers = _auth(validated_doctor["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "16:00:00",
            "end_time": "16:30:00",
        },
        headers=doctor_headers,
    )
    booking = await client.post(
        "/appointments",
        json={"availability_id": slot.json()["id"], "mode": "in_person"},
        headers=_auth(patient["token"]),
    )
    await client.post(
        f"/appointments/{booking.json()['id']}/decision",
        json={"approve": True},
        headers=doctor_headers,
    )

    resp = await client.get(
        "/appointments/calendar",
        params={"day": date.today().isoformat()},
        headers=doctor_headers,
    )
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["patient_name"] == "Ada Lovelace"


async def test_calendar_still_shows_completed_visit(client, completed_appointment):
    # A visit stays visible on its day after being marked completed, so the
    # doctor doesn't lose track of the day's history (and doesn't accidentally
    # re-publish an availability that overlaps an invisible past booking).
    doctor_headers = _auth(completed_appointment["doctor"]["token"])
    resp = await client.get(
        "/appointments/calendar",
        params={"day": date.today().isoformat()},
        headers=doctor_headers,
    )
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["status"] == "completed"


async def test_calendar_also_shows_pending_and_refused(
    client, patient, validated_doctor
):
    doctor_headers = _auth(validated_doctor["token"])

    async def _book(start_time):
        slot = await client.post(
            "/appointments/availabilities",
            json={
                "date": date.today().isoformat(),
                "start_time": start_time,
                "end_time": "10:30:00" if start_time == "10:00:00" else "11:30:00",
            },
            headers=doctor_headers,
        )
        booking = await client.post(
            "/appointments",
            json={"availability_id": slot.json()["id"], "mode": "in_person"},
            headers=_auth(patient["token"]),
        )
        return booking.json()["id"]

    pending_id = await _book("10:00:00")
    refused_id = await _book("11:00:00")
    await client.post(
        f"/appointments/{refused_id}/decision",
        json={"approve": False},
        headers=doctor_headers,
    )

    resp = await client.get(
        "/appointments/calendar",
        params={"day": date.today().isoformat()},
        headers=doctor_headers,
    )
    assert resp.status_code == 200
    statuses_by_id = {e["appointment_id"]: e["status"] for e in resp.json()}
    assert statuses_by_id[pending_id] == "pending"
    assert statuses_by_id[refused_id] == "refused"


async def test_list_confirmed_appointments_spans_all_days(
    client, completed_appointment
):
    # completed_appointment is CONFIRMED then COMPLETED, so it must not appear
    # here (this list is confirmed-only, across every day).
    doctor = completed_appointment["doctor"]
    doctor_headers = _auth(doctor["token"])

    from datetime import timedelta

    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": (date.today() + timedelta(days=1)).isoformat(),
            "start_time": "09:00:00",
            "end_time": "09:30:00",
        },
        headers=doctor_headers,
    )
    other_patient = await register_and_login_patient(
        client, "other-confirmed@example.com"
    )
    booking = await client.post(
        "/appointments",
        json={"availability_id": slot.json()["id"], "mode": "in_person"},
        headers=_auth(other_patient["token"]),
    )
    await client.post(
        f"/appointments/{booking.json()['id']}/decision",
        json={"approve": True},
        headers=doctor_headers,
    )

    resp = await client.get("/appointments/confirmed", headers=doctor_headers)
    assert resp.status_code == 200
    ids = [e["appointment_id"] for e in resp.json()]
    assert booking.json()["id"] in ids
    assert completed_appointment["appointment_id"] not in ids


async def test_pending_list_includes_patient_name_and_reason(
    client, patient, validated_doctor
):
    from datetime import date

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
        json={
            "availability_id": slot.json()["id"],
            "mode": "in_person",
            "reason": "Douleurs thoraciques",
        },
        headers=_auth(patient["token"]),
    )

    pending = await client.get("/appointments/pending", headers=doctor_headers)
    assert pending.status_code == 200
    entry = pending.json()[0]
    assert entry["patient_name"] == "Ada Lovelace"
    assert entry["reason"] == "Douleurs thoraciques"
    assert entry["mode"] == "in_person"


async def test_completed_awaiting_prescription_excludes_already_prescribed(
    client, completed_appointment
):
    doctor = completed_appointment["doctor"]
    doctor_headers = _auth(doctor["token"])

    awaiting = await client.get(
        "/appointments/completed-awaiting-prescription", headers=doctor_headers
    )
    assert awaiting.status_code == 200
    assert len(awaiting.json()) == 1
    assert (
        awaiting.json()[0]["appointment_id"] == completed_appointment["appointment_id"]
    )
    assert awaiting.json()[0]["patient_name"] == "Ada Lovelace"

    await client.post(
        "/prescriptions",
        json={
            "appointment_id": completed_appointment["appointment_id"],
            "notes": None,
            "treatments": [],
        },
        headers=doctor_headers,
    )

    awaiting_after = await client.get(
        "/appointments/completed-awaiting-prescription", headers=doctor_headers
    )
    assert awaiting_after.json() == []


async def test_doctor_defaults_available_in_search(client, validated_doctor):
    resp = await client.get("/doctors", params={"specialty": "Cardio"})
    assert resp.status_code == 200
    doctor = next(d for d in resp.json() if d["id"] == validated_doctor["id"])
    assert doctor["is_available"] is True


async def test_doctor_can_toggle_availability(client, validated_doctor):
    patch = await client.patch(
        "/doctors/me",
        json={"is_available": False},
        headers=_auth(validated_doctor["token"]),
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["is_available"] is False

    resp = await client.get(f"/doctors/{validated_doctor['id']}")
    assert resp.status_code == 200
    assert resp.json()["is_available"] is False


async def test_booking_rejected_when_doctor_unavailable(
    client, patient, validated_doctor
):
    doctor_headers = _auth(validated_doctor["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "13:00:00",
            "end_time": "13:30:00",
        },
        headers=doctor_headers,
    )
    assert slot.status_code == 201, slot.text
    availability_id = slot.json()["id"]

    toggle = await client.patch(
        "/doctors/me", json={"is_available": False}, headers=doctor_headers
    )
    assert toggle.status_code == 200, toggle.text

    booking = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=_auth(patient["token"]),
    )
    assert booking.status_code == 409, booking.text

    # The rejected attempt must not have partially mutated the slot: it should
    # still be bookable once the doctor is available again.
    toggle_back = await client.patch(
        "/doctors/me", json={"is_available": True}, headers=doctor_headers
    )
    assert toggle_back.status_code == 200, toggle_back.text
    retry = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=_auth(patient["token"]),
    )
    assert retry.status_code == 201, retry.text


async def test_doctor_can_delete_an_unbooked_slot(client, validated_doctor):
    doctor_headers = _auth(validated_doctor["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "15:00:00",
            "end_time": "15:30:00",
        },
        headers=doctor_headers,
    )
    assert slot.status_code == 201, slot.text
    availability_id = slot.json()["id"]

    delete = await client.delete(
        f"/appointments/availabilities/{availability_id}", headers=doctor_headers
    )
    assert delete.status_code == 204, delete.text

    remaining = await client.get(
        f"/appointments/doctors/{validated_doctor['id']}/availabilities",
        params={"from_date": date.today().isoformat()},
    )
    assert remaining.json() == []


async def test_doctor_cannot_delete_a_booked_slot(client, patient, validated_doctor):
    doctor_headers = _auth(validated_doctor["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "16:00:00",
            "end_time": "16:30:00",
        },
        headers=doctor_headers,
    )
    availability_id = slot.json()["id"]
    booking = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=_auth(patient["token"]),
    )
    assert booking.status_code == 201, booking.text

    delete = await client.delete(
        f"/appointments/availabilities/{availability_id}", headers=doctor_headers
    )
    assert delete.status_code == 409, delete.text


async def test_doctor_cannot_delete_another_doctors_slot(client, validated_doctor):
    from tests.conftest import _doctor_payload

    other_email = "other-doctor@example.com"
    reg = await client.post("/auth/doctors/register", json=_doctor_payload(other_email))
    assert reg.status_code == 201, reg.text
    other_login = await client.post(
        "/auth/doctors/login",
        json={"email": other_email, "password": "diagnostics1"},
    )
    other_headers = _auth(other_login.json()["access_token"])

    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "17:00:00",
            "end_time": "17:30:00",
        },
        headers=_auth(validated_doctor["token"]),
    )
    availability_id = slot.json()["id"]

    delete = await client.delete(
        f"/appointments/availabilities/{availability_id}", headers=other_headers
    )
    assert delete.status_code == 404, delete.text

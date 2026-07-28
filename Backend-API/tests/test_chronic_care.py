"""Chronic follow-ups, care plans, and the combined alert (manual + passive
missed-dose computation)."""

from datetime import date, timedelta

from tests.conftest import _auth


async def _create_follow_up(client, doctor, patient_id, condition="Diabetes"):
    return await client.post(
        "/chronic-care/follow-ups",
        json={
            "patient_id": patient_id,
            "condition_name": condition,
            "start_date": date.today().isoformat(),
        },
        headers=_auth(doctor["token"]),
    )


async def test_follow_up_and_dashboard(client, patient, validated_doctor):
    resp = await _create_follow_up(client, validated_doctor, patient["id"])
    assert resp.status_code == 201

    dashboard = await client.get("/chronic-care/dashboard", headers=_auth(validated_doctor["token"]))
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["followed_patients"] == 1
    assert body["patients_in_alert"] == 0
    assert body["active_care_plans"] == 0

    patients = await client.get("/chronic-care/patients", headers=_auth(validated_doctor["token"]))
    assert len(patients.json()) == 1
    item = patients.json()[0]
    assert item["patient_id"] == patient["id"]
    assert item["is_in_alert"] is False
    assert item["care_plan_active"] is False


async def test_manual_alert_flows_into_list_and_dashboard(client, patient, validated_doctor):
    follow_up = await _create_follow_up(client, validated_doctor, patient["id"])
    follow_up_id = follow_up.json()["id"]

    alert = await client.post(
        f"/chronic-care/follow-ups/{follow_up_id}/alert",
        json={"alert": True, "reason": "Blood sugar spike"},
        headers=_auth(validated_doctor["token"]),
    )
    assert alert.status_code == 200

    patients = await client.get("/chronic-care/patients", headers=_auth(validated_doctor["token"]))
    assert patients.json()[0]["is_in_alert"] is True

    dashboard = await client.get("/chronic-care/dashboard", headers=_auth(validated_doctor["token"]))
    assert dashboard.json()["patients_in_alert"] == 1


async def test_care_plan_upsert_is_idempotent(client, patient, validated_doctor):
    follow_up = await _create_follow_up(client, validated_doctor, patient["id"])
    follow_up_id = follow_up.json()["id"]
    headers = _auth(validated_doctor["token"])

    created = await client.put(
        f"/chronic-care/follow-ups/{follow_up_id}/care-plan",
        json={"description": "Weekly monitoring", "status": "active"},
        headers=headers,
    )
    assert created.status_code == 200
    plan_id = created.json()["id"]

    updated = await client.put(
        f"/chronic-care/follow-ups/{follow_up_id}/care-plan",
        json={"description": "Daily monitoring", "status": "active"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == plan_id  # same plan updated, not a new one

    dashboard = await client.get("/chronic-care/dashboard", headers=headers)
    assert dashboard.json()["active_care_plans"] == 1

    patients = await client.get("/chronic-care/patients", headers=headers)
    assert patients.json()[0]["care_plan_active"] is True


async def test_missed_doses_trigger_automatic_alert(client, completed_appointment):
    """A treatment active over the past week with no confirmed intakes yields
    missed doses above the threshold -> automatic alert, no manual flag."""
    patient = completed_appointment["patient"]
    doctor = completed_appointment["doctor"]

    prescription = await client.post(
        "/prescriptions",
        json={
            "appointment_id": completed_appointment["appointment_id"],
            "notes": None,
            "treatments": [
                {
                    "medication_name": "Metformin",
                    "dosage": "1000mg",
                    "start_date": (date.today() - timedelta(days=6)).isoformat(),
                    "end_date": (date.today() + timedelta(days=10)).isoformat(),
                    "intake_times": ["08:00:00"],
                }
            ],
        },
        headers=_auth(doctor["token"]),
    )
    assert prescription.status_code == 201

    await _create_follow_up(client, doctor, patient["id"], condition="Diabetes")

    patients = await client.get("/chronic-care/patients", headers=_auth(doctor["token"]))
    # 6 expected doses over the window, 0 confirmed -> above the 3-miss threshold.
    assert patients.json()[0]["is_in_alert"] is True

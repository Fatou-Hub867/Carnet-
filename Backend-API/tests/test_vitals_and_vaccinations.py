"""Vital-sign bilans and vaccinations: patient-entered carnet data, plus the
inline weight snapshot written by Patients.logic on profile update."""

from tests.conftest import _auth


async def test_vitals_summary_is_empty_by_default(client, patient):
    resp = await client.get(
        "/health-records/me/vitals", headers=_auth(patient["token"])
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "tension": None,
        "glycemia": None,
        "heart_rate": None,
        "weight": None,
    }


async def test_create_vital_bilan_updates_summary(client, patient):
    resp = await client.post(
        "/health-records/me/vitals",
        json={
            "systolic": 12,
            "diastolic": 8,
            "glycemia_g_l": 0.9,
            "heart_rate_bpm": 72,
        },
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["tension"] == {
        "systolic": 12,
        "diastolic": 8,
        "recorded_at": body["tension"]["recorded_at"],
    }
    assert body["glycemia"]["value"] == 0.9
    assert body["heart_rate"]["value"] == 72.0
    assert body["weight"] is None

    summary = await client.get(
        "/health-records/me/vitals", headers=_auth(patient["token"])
    )
    assert summary.json() == body


async def test_create_vital_bilan_allows_partial_fields(client, patient):
    resp = await client.post(
        "/health-records/me/vitals",
        json={"heart_rate_bpm": 65},
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["tension"] is None
    assert body["glycemia"] is None
    assert body["heart_rate"]["value"] == 65.0


async def test_create_vital_bilan_rejects_lone_systolic(client, patient):
    resp = await client.post(
        "/health-records/me/vitals",
        json={"systolic": 12},
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 422


async def test_create_vital_bilan_rejects_empty_body(client, patient):
    resp = await client.post(
        "/health-records/me/vitals", json={}, headers=_auth(patient["token"])
    )
    assert resp.status_code == 422


async def test_create_vital_bilan_rejects_weight_field(client, patient):
    resp = await client.post(
        "/health-records/me/vitals",
        json={"heart_rate_bpm": 70, "weight_kg": 80},
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 422


async def test_update_latest_bilan_without_existing_one_404s(client, patient):
    resp = await client.patch(
        "/health-records/me/vitals/latest",
        json={"heart_rate_bpm": 80},
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 404


async def test_delete_latest_bilan_without_existing_one_404s(client, patient):
    resp = await client.delete(
        "/health-records/me/vitals/latest", headers=_auth(patient["token"])
    )
    assert resp.status_code == 404


async def test_update_latest_bilan(client, patient):
    await client.post(
        "/health-records/me/vitals",
        json={"heart_rate_bpm": 70},
        headers=_auth(patient["token"]),
    )
    resp = await client.patch(
        "/health-records/me/vitals/latest",
        json={"heart_rate_bpm": 75, "glycemia_g_l": 1.1},
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["heart_rate"]["value"] == 75.0
    assert body["glycemia"]["value"] == 1.1


async def test_update_latest_bilan_rejects_nulling_all_fields(client, patient):
    await client.post(
        "/health-records/me/vitals",
        json={"heart_rate_bpm": 70},
        headers=_auth(patient["token"]),
    )
    resp = await client.patch(
        "/health-records/me/vitals/latest",
        json={"heart_rate_bpm": None},
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 400, resp.text

    summary = await client.get(
        "/health-records/me/vitals", headers=_auth(patient["token"])
    )
    assert summary.json()["heart_rate"]["value"] == 70.0


async def test_delete_latest_bilan_falls_back_to_previous_value(client, patient):
    await client.post(
        "/health-records/me/vitals",
        json={"heart_rate_bpm": 70},
        headers=_auth(patient["token"]),
    )
    await client.post(
        "/health-records/me/vitals",
        json={"heart_rate_bpm": 75},
        headers=_auth(patient["token"]),
    )
    resp = await client.delete(
        "/health-records/me/vitals/latest", headers=_auth(patient["token"])
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["heart_rate"]["value"] == 70.0


async def test_profile_weight_change_creates_a_weight_snapshot(client, patient):
    resp = await client.patch(
        "/patients/me", json={"weight_kg": 68.5}, headers=_auth(patient["token"])
    )
    assert resp.status_code == 200, resp.text

    vitals = await client.get(
        "/health-records/me/vitals", headers=_auth(patient["token"])
    )
    assert vitals.json()["weight"]["value"] == 68.5


async def test_profile_weight_unchanged_does_not_duplicate_snapshot(client, patient):
    await client.patch(
        "/patients/me", json={"weight_kg": 68.5}, headers=_auth(patient["token"])
    )
    first = await client.get(
        "/health-records/me/vitals", headers=_auth(patient["token"])
    )
    first_recorded_at = first.json()["weight"]["recorded_at"]

    # Re-submitting the exact same weight must not create a new row (the
    # recorded_at timestamp should be unchanged).
    await client.patch(
        "/patients/me", json={"weight_kg": 68.5}, headers=_auth(patient["token"])
    )
    second = await client.get(
        "/health-records/me/vitals", headers=_auth(patient["token"])
    )
    assert second.json()["weight"]["recorded_at"] == first_recorded_at


async def test_profile_update_without_weight_does_not_create_snapshot(client, patient):
    await client.patch(
        "/patients/me", json={"city": "Brazzaville"}, headers=_auth(patient["token"])
    )
    vitals = await client.get(
        "/health-records/me/vitals", headers=_auth(patient["token"])
    )
    assert vitals.json()["weight"] is None

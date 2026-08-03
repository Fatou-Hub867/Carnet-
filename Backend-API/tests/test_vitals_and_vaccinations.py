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

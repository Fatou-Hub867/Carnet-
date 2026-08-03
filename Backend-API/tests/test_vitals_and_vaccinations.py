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

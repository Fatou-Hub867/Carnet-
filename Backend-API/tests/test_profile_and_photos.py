"""Patient/doctor profile extras: weight, and profile photo upload+display."""

from tests.conftest import _auth


async def test_patient_can_set_weight_and_it_persists(client, patient):
    resp = await client.patch(
        "/patients/me", json={"weight_kg": 68.5}, headers=_auth(patient["token"])
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["weight_kg"] == 68.5

    again = await client.get("/patients/me", headers=_auth(patient["token"]))
    assert again.json()["weight_kg"] == 68.5


async def test_patient_profile_has_no_photo_by_default(client, patient):
    resp = await client.get("/patients/me", headers=_auth(patient["token"]))
    assert resp.status_code == 200
    assert resp.json()["photo_url"] is None


async def test_patient_can_upload_a_photo(client, patient):
    resp = await client.post(
        "/patients/me/photo",
        files={"photo": ("me.jpg", b"\xff\xd8\xfffake-jpeg", "image/jpeg")},
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["photo_url"].startswith("https://fake-s3.local/")

    again = await client.get("/patients/me", headers=_auth(patient["token"]))
    assert again.json()["photo_url"].startswith("https://fake-s3.local/")

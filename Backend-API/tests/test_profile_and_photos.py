"""Patient/doctor profile extras: weight, and profile photo upload+display."""

from tests.conftest import _auth, _doctor_payload


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


async def test_doctor_can_upload_a_photo(client, validated_doctor):
    resp = await client.post(
        "/doctors/me/photo",
        files={"photo": ("me.jpg", b"\xff\xd8\xfffake-jpeg", "image/jpeg")},
        headers=_auth(validated_doctor["token"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["photo_url"].startswith("https://fake-s3.local/")


async def test_doctor_photo_visible_in_public_search(client, validated_doctor):
    await client.post(
        "/doctors/me/photo",
        files={"photo": ("me.jpg", b"\xff\xd8\xfffake-jpeg", "image/jpeg")},
        headers=_auth(validated_doctor["token"]),
    )
    search = await client.get("/doctors")
    assert search.status_code == 200
    assert search.json()[0]["photo_url"].startswith("https://fake-s3.local/")

    single = await client.get(f"/doctors/{validated_doctor['id']}")
    assert single.json()["photo_url"].startswith("https://fake-s3.local/")


async def test_doctor_me_exposes_status_so_frontend_can_gate_pending_accounts(
    client, validated_doctor
):
    resp = await client.get("/doctors/me", headers=_auth(validated_doctor["token"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "validated"
    assert resp.json()["suspended_until"] is None
    assert resp.json()["has_diploma"] is True


async def test_pending_doctor_me_status_is_pending_validation(client):
    email = "pending-doctor@example.com"
    reg = await client.post("/auth/doctors/register", json=_doctor_payload(email))
    assert reg.status_code == 201, reg.text

    login = await client.post(
        "/auth/doctors/login", json={"email": email, "password": "diagnostics1"}
    )
    assert login.status_code == 200, login.text

    resp = await client.get("/doctors/me", headers=_auth(login.json()["access_token"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pending_validation"
    # Registration never uploaded a diploma in this test -> the "missing
    # diploma" re-upload prompt (en-attente.html) must trigger for this doctor.
    assert resp.json()["has_diploma"] is False

async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_protected_route_requires_auth(client):
    # No token -> the OAuth2 scheme rejects before reaching the handler.
    resp = await client.get("/patients/me")
    assert resp.status_code == 401


async def test_patient_register_and_profile(client):
    from tests.conftest import _auth, register_and_login_patient

    patient = await register_and_login_patient(client, "smoke@example.com")
    resp = await client.get("/patients/me", headers=_auth(patient["token"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "smoke@example.com"
    assert body["first_name"] == "Ada"


async def test_duplicate_email_conflicts(client):
    from tests.conftest import _patient_payload

    first = await client.post("/auth/patients/register", json=_patient_payload("dup@example.com"))
    assert first.status_code == 201
    second = await client.post("/auth/patients/register", json=_patient_payload("dup@example.com"))
    assert second.status_code == 409

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

    first = await client.post(
        "/auth/patients/register", json=_patient_payload("dup@example.com")
    )
    assert first.status_code == 201
    second = await client.post(
        "/auth/patients/register", json=_patient_payload("dup@example.com")
    )
    assert second.status_code == 409


async def test_unverified_patient_cannot_login(client):
    from tests.conftest import _patient_payload

    email = "unverified@example.com"
    resp = await client.post("/auth/patients/register", json=_patient_payload(email))
    assert resp.status_code == 201

    login = await client.post(
        "/auth/patients/login", json={"email": email, "password": "supersecret1"}
    )
    assert login.status_code == 403


async def test_confirm_email_then_login_succeeds(client):
    from sqlalchemy import select

    from core.database import async_session_factory
    from features.Auth.models import EmailVerificationToken
    from tests.conftest import _patient_payload

    email = "confirmable@example.com"
    resp = await client.post("/auth/patients/register", json=_patient_payload(email))
    assert resp.status_code == 201
    patient_id = resp.json()["id"]

    async with async_session_factory() as session:
        token_row = (
            await session.scalars(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.user_id == patient_id
                )
            )
        ).first()

    confirm = await client.post(
        "/auth/patients/confirm-email", json={"token": token_row.token}
    )
    assert confirm.status_code == 200

    login = await client.post(
        "/auth/patients/login", json={"email": email, "password": "supersecret1"}
    )
    assert login.status_code == 200


async def test_confirm_email_invalid_token_returns_400(client):
    resp = await client.post(
        "/auth/patients/confirm-email", json={"token": "not-a-real-token"}
    )
    assert resp.status_code == 400


async def test_register_patient_sends_confirmation_link(client, monkeypatch):
    import features.Notifications.logic as notifications
    from tests.conftest import _patient_payload

    captured = {}

    def fake_send_email(to, subject, html):
        captured["to"] = to
        captured["html"] = html

    monkeypatch.setattr(notifications, "send_email", fake_send_email)

    email = "confirm-link-check@example.com"
    resp = await client.post("/auth/patients/register", json=_patient_payload(email))
    assert resp.status_code == 201

    assert captured["to"] == email
    assert "confirmer-email.html?token=" in captured["html"]

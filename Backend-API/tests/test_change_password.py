"""Changing your own password while already logged in — the only prior path
was the logged-out 'forgot password' email flow."""

from tests.conftest import _auth


async def test_patient_can_change_password_and_login_with_new_one(client, patient):
    resp = await client.post(
        "/auth/patients/change-password",
        json={
            "current_password": "supersecret1",
            "new_password": "brandnewpass1",
            "new_password_confirmation": "brandnewpass1",
        },
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 200, resp.text

    old_login = await client.post(
        "/auth/patients/login",
        json={"email": patient["email"], "password": "supersecret1"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/auth/patients/login",
        json={"email": patient["email"], "password": "brandnewpass1"},
    )
    assert new_login.status_code == 200, new_login.text


async def test_patient_change_password_rejects_wrong_current_password(client, patient):
    resp = await client.post(
        "/auth/patients/change-password",
        json={
            "current_password": "wrong-password",
            "new_password": "brandnewpass1",
            "new_password_confirmation": "brandnewpass1",
        },
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 401


async def test_patient_change_password_rejects_mismatched_confirmation(client, patient):
    resp = await client.post(
        "/auth/patients/change-password",
        json={
            "current_password": "supersecret1",
            "new_password": "brandnewpass1",
            "new_password_confirmation": "somethingelse1",
        },
        headers=_auth(patient["token"]),
    )
    assert resp.status_code == 422


async def test_doctor_can_change_password_and_login_with_new_one(
    client, validated_doctor
):
    resp = await client.post(
        "/auth/doctors/change-password",
        json={
            "current_password": "diagnostics1",
            "new_password": "brandnewpass1",
            "new_password_confirmation": "brandnewpass1",
        },
        headers=_auth(validated_doctor["token"]),
    )
    assert resp.status_code == 200, resp.text

    old_login = await client.post(
        "/auth/doctors/login",
        json={"email": validated_doctor["email"], "password": "diagnostics1"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/auth/doctors/login",
        json={"email": validated_doctor["email"], "password": "brandnewpass1"},
    )
    assert new_login.status_code == 200, new_login.text

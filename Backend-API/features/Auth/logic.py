"""Registration, authentication and password reset for patients, doctors and admins."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import hash_password, verify_password
from features.Auth.models import (
    DOCTOR_LOGIN_ALLOWED_STATUSES,
    Admin,
    Doctor,
    Patient,
    PatientStatus,
    PasswordResetToken,
    UserType,
)
from features.Auth.schemas import DoctorRegisterRequest, PatientRegisterRequest
from features.Notifications import logic as notifications

_PASSWORD_RESET_TOKEN_BYTES = 32


def _is_expired(expires_at: datetime) -> bool:
    # Some drivers (e.g. SQLite, used in tests) drop tzinfo on round-trip even
    # for a timezone-aware column; Postgres/asyncpg does not. Normalize to UTC
    # before comparing so this works with either.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


async def register_patient(
    db: AsyncSession, data: PatientRegisterRequest, background_tasks: BackgroundTasks
) -> Patient:
    patient = Patient(
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        place_of_birth=data.place_of_birth,
        address=data.address,
        phone_number=data.phone_number,
        country_of_residence=data.country_of_residence,
        gender=data.gender,
        city=data.city,
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(patient)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from exc
    await db.refresh(patient)

    background_tasks.add_task(notifications.notify_patient_welcome, patient.email, patient.first_name)
    return patient


async def register_doctor(db: AsyncSession, data: DoctorRegisterRequest) -> Doctor:
    # No admin notification here: it fires once the diploma is actually
    # uploaded (upload_doctor_diploma), since the request isn't reviewable
    # before that.
    doctor = Doctor(
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        place_of_birth=data.place_of_birth,
        email=data.email,
        phone_number=data.phone_number,
        country_of_residence=data.country_of_residence,
        gender=data.gender,
        city=data.city,
        password_hash=hash_password(data.password),
        specialty=data.specialty,
        license_number=data.license_number,
        practice_name=data.practice_name,
        consultation_fee=data.consultation_fee,
    )
    db.add(doctor)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email or license number already exists"
        ) from exc
    await db.refresh(doctor)
    return doctor


async def upload_doctor_diploma(
    db: AsyncSession, doctor: Doctor, diploma_file_key: str, background_tasks: BackgroundTasks
) -> Doctor:
    doctor.diploma_file_key = diploma_file_key
    await db.commit()
    await db.refresh(doctor)

    admin_emails = (await db.scalars(select(Admin.email))).all()
    for admin_email in admin_emails:
        background_tasks.add_task(
            notifications.notify_admin_new_doctor_request,
            admin_email,
            f"{doctor.first_name} {doctor.last_name}",
        )
    return doctor


async def authenticate_patient(db: AsyncSession, email: str, password: str) -> Patient:
    patient = (await db.scalars(select(Patient).where(Patient.email == email))).first()
    if (
        patient is None
        or patient.status != PatientStatus.ACTIVE
        or not verify_password(password, patient.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return patient


async def authenticate_doctor(db: AsyncSession, email: str, password: str) -> Doctor:
    # No scheduler in the V1: an elapsed suspension is lifted lazily here, so a
    # doctor whose month is up is validated again the moment they log back in.
    # Local import keeps Auth free of any import-time dependency on Admin.
    from features.Admin.logic import reactivate_expired_suspensions

    await reactivate_expired_suspensions(db)

    doctor = (await db.scalars(select(Doctor).where(Doctor.email == email))).first()
    if doctor is None or not verify_password(password, doctor.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if doctor.status not in DOCTOR_LOGIN_ALLOWED_STATUSES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account cannot log in")
    return doctor


async def authenticate_admin(db: AsyncSession, email: str, password: str) -> Admin:
    admin = (await db.scalars(select(Admin).where(Admin.email == email))).first()
    if admin is None or not verify_password(password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return admin


async def request_password_reset(db: AsyncSession, email: str, background_tasks: BackgroundTasks) -> None:
    """Always returns silently, even for an unknown email, so this endpoint
    can't be used to enumerate registered accounts."""
    patient = (await db.scalars(select(Patient).where(Patient.email == email))).first()
    doctor = None if patient else (await db.scalars(select(Doctor).where(Doctor.email == email))).first()
    if patient is None and doctor is None:
        return

    user_type = UserType.PATIENT if patient else UserType.DOCTOR
    user_id = patient.id if patient else doctor.id
    target_email = patient.email if patient else doctor.email

    token = secrets.token_urlsafe(_PASSWORD_RESET_TOKEN_BYTES)
    db.add(
        PasswordResetToken(
            user_type=user_type,
            user_id=user_id,
            token=token,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.password_reset_token_expire_minutes),
        )
    )
    await db.commit()

    reset_link = f"{settings.frontend_base_url}/reset-password?token={token}"
    background_tasks.add_task(notifications.notify_password_reset, target_email, reset_link)


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    reset_token = (await db.scalars(select(PasswordResetToken).where(PasswordResetToken.token == token))).first()
    if reset_token is None or reset_token.used or _is_expired(reset_token.expires_at):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    model = Patient if reset_token.user_type == UserType.PATIENT else Doctor
    user = await db.get(model, reset_token.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    user.password_hash = hash_password(new_password)
    reset_token.used = True
    await db.commit()

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import decode_access_token
from features.Auth.models import DOCTOR_LOGIN_ALLOWED_STATUSES, Admin, Doctor, Patient, PatientStatus

# tokenUrl only documents where to get a token in the OpenAPI UI; patients,
# doctors and admins each have their own login endpoint (see Auth/routes.py).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/patients/login", auto_error=True)


async def _decode(token: str) -> tuple[int, str]:
    try:
        payload = decode_access_token(token)
        return int(payload["sub"]), payload["role"]
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


async def get_current_patient(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> Patient:
    user_id, role = await _decode(token)
    if role != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Patient account required")
    patient = await db.get(Patient, user_id)
    if patient is None or patient.status != PatientStatus.ACTIVE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or inactive")
    return patient


async def get_current_doctor(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> Doctor:
    user_id, role = await _decode(token)
    if role != "doctor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Doctor account required")
    doctor = await db.get(Doctor, user_id)
    if doctor is None or doctor.status not in DOCTOR_LOGIN_ALLOWED_STATUSES:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or inactive")
    return doctor


async def get_current_admin(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> Admin:
    user_id, role = await _decode(token)
    if role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin account required")
    admin = await db.get(Admin, user_id)
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    return admin


async def get_current_participant(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> tuple[str, int]:
    """Messaging is used by both patients and doctors, so its endpoints resolve
    either role and return (user_type, user_id). Admins are not participants."""
    user_id, role = await _decode(token)
    if role == "patient":
        patient = await db.get(Patient, user_id)
        if patient is None or patient.status != PatientStatus.ACTIVE:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or inactive")
    elif role == "doctor":
        doctor = await db.get(Doctor, user_id)
        if doctor is None or doctor.status not in DOCTOR_LOGIN_ALLOWED_STATUSES:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or inactive")
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only patients and doctors can use messaging")
    return role, user_id

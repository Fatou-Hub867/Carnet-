"""Auth endpoints: registration, login, password reset.

Doctor registration is split in two calls (register, then upload-diploma)
because FastAPI cannot mix a JSON body with a multipart file upload in a
single request. The diploma endpoint takes no doctor_id in the path — it
always acts on the authenticated doctor resolved from the token, so a
doctor can never upload a diploma to someone else's account.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_doctor
from core.security import create_access_token
from core.storage import upload_file
from features.Auth import logic
from features.Auth.models import Doctor
from features.Auth.schemas import (
    ConfirmEmailRequest,
    DoctorRegisterRequest,
    DoctorRegisterResponse,
    ForgotPasswordRequest,
    LoginRequest,
    PatientOut,
    PatientRegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/patients/register", response_model=PatientOut, status_code=status.HTTP_201_CREATED
)
async def register_patient(
    data: PatientRegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    return await logic.register_patient(db, data, background_tasks)


@router.post(
    "/doctors/register",
    response_model=DoctorRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_doctor(
    data: DoctorRegisterRequest, db: AsyncSession = Depends(get_db)
):
    doctor = await logic.register_doctor(db, data)
    return DoctorRegisterResponse(id=doctor.id, status=doctor.status.value)


@router.post("/doctors/me/diploma")
async def upload_doctor_diploma(
    diploma_file: UploadFile,
    background_tasks: BackgroundTasks,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    file_key = upload_file(
        await diploma_file.read(), diploma_file.filename, diploma_file.content_type
    )
    await logic.upload_doctor_diploma(db, current_doctor, file_key, background_tasks)
    return {"status": "diploma received, awaiting admin validation"}


@router.post("/patients/login", response_model=TokenResponse)
async def login_patient(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    patient = await logic.authenticate_patient(db, data.email, data.password)
    return TokenResponse(access_token=create_access_token(str(patient.id), "patient"))


@router.post("/doctors/login", response_model=TokenResponse)
async def login_doctor(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    doctor = await logic.authenticate_doctor(db, data.email, data.password)
    return TokenResponse(access_token=create_access_token(str(doctor.id), "doctor"))


@router.post("/admin/login", response_model=TokenResponse)
async def login_admin(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    admin = await logic.authenticate_admin(db, data.email, data.password)
    return TokenResponse(access_token=create_access_token(str(admin.id), "admin"))


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    await logic.request_password_reset(db, data.email, background_tasks)
    return {"status": "if this email is registered, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
):
    await logic.reset_password(db, data.token, data.new_password)
    return {"status": "password updated"}


@router.post("/patients/confirm-email")
async def confirm_patient_email(
    data: ConfirmEmailRequest, db: AsyncSession = Depends(get_db)
):
    await logic.confirm_patient_email(db, data.token)
    return {"status": "email confirmed"}
